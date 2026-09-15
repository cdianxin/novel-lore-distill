#!/usr/bin/env python3
"""Audit a novel-lore-distill output directory.

The audit is read-only except for the JSON report path.  Use ``--strict`` in
CI or before delivery; a strict audit exits with status 1 when a required
coverage or provenance check fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit


DEFAULT_CONFIG: dict[str, Any] = {
    "expected_chunks": None,
    "chunks": {
        "text": {"folder": "分块文本", "prefix": "chunk", "suffix": ".txt"},
        "extracted": {"folder": "分块提取", "prefix": "chunk", "suffix": ".md"},
    },
    "merge": {
        "folder": "合并",
        "prefix": "merge",
        "suffix": ".md",
        "required_sections": 8,
        "section_pattern": r"^#{1,3}\s*(?:[一二三四五六七八九十]+、|\d+[.)、．])\s*\S+",
    },
    "categories": [
        {
            "name": "角色",
            "card_folder": "角色",
            "index_files": ["角色索引.md", "角色/角色索引.md"],
            "terminal_input": "角色-一级合并汇总.md",
            "required_fields": ["实体状态", "实体 ID", "证据", "来源"],
        },
        {
            "name": "事件",
            "card_folder": "事件",
            "index_files": ["事件索引.md", "事件/事件索引.md"],
            "terminal_input": "事件-一级合并汇总.md",
            "required_fields": ["实体状态", "实体 ID", "证据", "来源"],
        },
        {
            "name": "地点",
            "card_folder": "地点",
            "index_files": ["地点索引.md", "地点/地点索引.md"],
            "terminal_input": "地点-一级合并汇总.md",
            "required_fields": ["实体状态", "实体 ID", "证据", "来源"],
        },
        {
            "name": "势力",
            "card_folder": "势力",
            "index_files": ["势力索引.md", "势力/势力索引.md"],
            "terminal_input": "势力-一级合并汇总.md",
            "required_fields": ["实体状态", "实体 ID", "证据", "来源"],
        },
        {
            "name": "物品",
            "card_folder": "物品",
            "index_files": ["物品索引.md", "物品/物品索引.md"],
            "terminal_input": "物品-一级合并汇总.md",
            "required_fields": ["实体状态", "实体 ID", "证据", "来源"],
        },
        {
            "name": "能力",
            "card_folder": "能力",
            "index_files": ["能力索引.md", "能力/能力索引.md"],
            "terminal_input": "能力-一级合并汇总.md",
            "required_fields": ["实体状态", "实体 ID", "证据", "来源"],
        },
        {
            "name": "术语",
            "card_folder": None,
            "index_files": [],
            "terminal_input": "术语-一级合并汇总.md",
            "required_fields": [],
        },
        {
            "name": "大事记",
            "card_folder": None,
            "index_files": [],
            "terminal_input": "大事记-一级合并汇总.md",
            "required_fields": [],
        },
    ],
    "card_checks": {
        "status_labels": ["实体状态", "卡片状态"],
        "entity_id_labels": ["实体 ID", "实体ID", "entity_id"],
        "evidence_heading": "证据",
        "source_headings": ["来源", "Sources"],
        "placeholder_patterns": ["输入未提供"],
        "evidence_fields": {
            "source_file": ["source_file", "来源文件"],
            "source_chunk": ["source_chunk", "来源分块"],
            "source_chapter": ["source_chapter", "来源章节", "章节或场景范围"],
            "locator": ["locator", "定位", "原文位置"],
            "evidence_type": ["evidence_type", "证据类型"],
            "confidence": ["confidence", "置信度"],
            "fact_status": ["fact_status", "evidence_status", "事实状态", "信息状态"],
        },
    },
    "chapters": {
        "candidates": [
            "大事年表.md",
            "时间线.md",
            "chronology.md",
            "修复/暂存/大事记-R/大事年表.md",
        ],
        "patterns": [
            {"regex": r"第\s*(?P<number>\d+)\s*[章节回]", "group": "number"},
            {
                "regex": r"第\s*(?P<number_cn>[零〇○一二两三四五六七八九十百千万亿]+)\s*[章节回]",
                "group": "number_cn",
                "number_type": "chinese",
            },
            {
                "regex": r"\bchapter\s*(?P<number>\d+)\b",
                "group": "number",
                "flags": ["IGNORECASE"],
            },
        ],
        "markers": ["序章", "楔子", "终章", "尾声", "prologue", "epilogue"],
        "first": None,
        "last": None,
    },
    "manifest_file": "manifest.json",
    "state_file": "PIPELINE_STATE.md",
    "output": {
        "report_file": "修复/audit-report.json"
    },
    "state_required_headings": [
        "当前阶段",
        "处理范围",
        "产物统计",
        "来源与证据",
        "并发与重试",
        "备份与恢复",
        "待复核",
        "最后更新",
    ],
}

LINK_RE = re.compile(r"\]\(\s*(?:<(?P<angle>[^>\n]+)>|(?P<bare>[^)\n]+))\s*\)")
EVIDENCE_ID_RE = re.compile(
    r"^\s*[-*]\s*(?:evidence_id|证据\s*(?:ID|编号))\s*[:：]\s*(\S+)\s*$",
    re.I,
)
HEADING_RE = re.compile(r"^\s*#{1,6}\s*(.*?)\s*#*\s*$")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return deep_merge(DEFAULT_CONFIG, data)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def numbered_files(folder: Path, prefix: str, suffix: str) -> dict[int, Path]:
    result: dict[int, Path] = {}
    if not folder.is_dir():
        return result
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+){re.escape(suffix)}$")
    for path in folder.iterdir():
        match = pattern.match(path.name)
        if match and path.is_file():
            result[int(match.group(1))] = path
    return result


def check_numbered(
    folder: Path, prefix: str, suffix: str, expected: int | None
) -> dict[str, Any]:
    files = numbered_files(folder, prefix, suffix)
    actual_numbers = sorted(files)
    inferred = expected is None
    expected_value = expected if expected is not None else max(actual_numbers, default=0)
    missing = [i for i in range(1, expected_value + 1) if i not in files]
    extras = sorted(i for i in files if i < 1 or i > expected_value)
    complete = bool(files) and not missing and not extras
    return {
        "folder": str(folder),
        "expected": expected_value,
        "expected_source": "highest_actual_number" if inferred else "argument_or_config",
        "actual": len(files),
        "actual_numbers": actual_numbers,
        "missing": missing,
        "extras": extras,
        "complete": complete,
        "trailing_range_unverified": inferred,
    }


def card_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        p
        for p in folder.glob("*.md")
        if "索引" not in p.name and "index" not in p.name.lower()
    )


def labels_pattern(labels: Iterable[str]) -> str:
    return "|".join(re.escape(str(label)) for label in labels if str(label).strip())


def has_heading_or_label(text: str, labels: Iterable[str]) -> bool:
    alternatives = labels_pattern(labels)
    if not alternatives:
        return False
    pattern = re.compile(
        rf"^\s*(?:#{{1,6}}\s*)?(?:[-*]\s*)?(?:\*\*)?(?:{alternatives})(?:\*\*)?\s*(?:$|[:：])",
        re.I | re.M,
    )
    return bool(pattern.search(text))


def entity_status(text: str, config: dict[str, Any]) -> str | None:
    labels = config["card_checks"].get("status_labels", ["实体状态"])
    alternatives = labels_pattern(labels)
    pattern = re.compile(
        rf"^\s*(?:#{{1,6}}\s*)?(?:[-*]\s*)?(?:\*\*)?(?:{alternatives})(?:\*\*)?\s*(?:[:：]|$)\s*\n?\s*(?:[-*]\s*)?(.+?)\s*$",
        re.I | re.M,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def source_details(text: str, config: dict[str, Any]) -> dict[str, bool]:
    headings = config["card_checks"].get("source_headings", ["来源"])
    heading_present = has_heading_or_label(text, headings)
    fields = config["card_checks"].get("evidence_fields", {})
    source_file = has_heading_or_label(text, fields.get("source_file", ["source_file", "来源文件"]))
    source_locator = any(
        has_heading_or_label(text, fields.get(name, []))
        for name in ("source_chunk", "source_chapter", "locator")
    )
    return {
        "heading_present": heading_present,
        "source_file_present": source_file,
        "locator_present": source_locator,
        "complete": heading_present and source_file and source_locator,
    }


def evidence_entries(text: str, config: dict[str, Any]) -> dict[str, Any]:
    checks = config["card_checks"]
    heading = str(checks.get("evidence_heading", "证据"))
    heading_match = re.search(rf"^##\s*{re.escape(heading)}\s*$", text, re.I | re.M)
    if not heading_match:
        return {
            "heading_present": False,
            "count": 0,
            "missing_fields": [],
        }

    block = text[heading_match.end() :]
    next_heading = re.search(r"^##\s+", block, re.M)
    if next_heading:
        block = block[: next_heading.start()]
    lines = block.splitlines()
    starts = [index for index, line in enumerate(lines) if EVIDENCE_ID_RE.match(line)]
    fields = checks.get("evidence_fields", {})
    required = [
        "source_file",
        "source_chunk",
        "source_chapter",
        "locator",
        "evidence_type",
        "confidence",
        "fact_status",
    ]
    missing: list[dict[str, Any]] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        entry = "\n".join(lines[start:end])
        missing_fields = [
            field
            for field in required
            if not has_heading_or_label(entry, fields.get(field, [field]))
        ]
        evidence_id = EVIDENCE_ID_RE.match(lines[start]).group(1)  # type: ignore[union-attr]
        if missing_fields:
            missing.append({"evidence_id": evidence_id, "fields": missing_fields})
    return {
        "heading_present": True,
        "count": len(starts),
        "missing_fields": missing,
    }


def normalize_name(name: str) -> str:
    name = re.sub(r"（[^）]*）|\([^)]*\)", "", name)
    name = re.sub(r"__重复-\d+|__修复重复\d+", "", name)
    return name.strip()


def relative_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def audit_cards(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    default_fields = ["实体状态", "实体 ID", "证据", "来源"]
    for spec in config.get("categories", []):
        folder_name = spec.get("card_folder")
        if not folder_name:
            continue
        category = str(spec["name"])
        folder = root / str(folder_name)
        cards = card_files(folder)
        statuses: dict[str, int] = {}
        missing_status: list[str] = []
        missing_source: list[str] = []
        missing_entity_id: list[str] = []
        missing_evidence: list[str] = []
        evidence_field_gaps: dict[str, list[dict[str, Any]]] = {}
        missing_fields: dict[str, list[str]] = {}
        placeholders: list[str] = []
        short_cards: list[str] = []
        normalized: dict[str, list[str]] = {}
        for path in cards:
            text = read_text(path)
            status = entity_status(text, config)
            if status is None:
                missing_status.append(path.name)
                status = "未标注"
            statuses[status] = statuses.get(status, 0) + 1
            source = source_details(text, config)
            if not source["complete"]:
                missing_source.append(path.name)
            if not has_heading_or_label(
                text, config["card_checks"].get("entity_id_labels", ["实体 ID", "实体ID", "entity_id"])
            ):
                missing_entity_id.append(path.name)
            evidence = evidence_entries(text, config)
            if not evidence["heading_present"] or evidence["count"] == 0:
                missing_evidence.append(path.name)
            if evidence["missing_fields"]:
                evidence_field_gaps[path.name] = evidence["missing_fields"]
            required_fields = spec.get("required_fields", default_fields)
            gaps = [field for field in required_fields if not has_heading_or_label(text, [field])]
            if gaps:
                missing_fields[path.name] = gaps
            if any(pattern in text for pattern in config["card_checks"].get("placeholder_patterns", [])):
                placeholders.append(path.name)
            if path.stat().st_size < 300:
                short_cards.append(path.name)
            normalized.setdefault(normalize_name(path.stem), []).append(path.name)
        duplicates = {key: value for key, value in normalized.items() if key and len(value) > 1}
        result[category] = {
            "folder": str(folder),
            "count": len(cards),
            "empty": [p.name for p in cards if p.stat().st_size == 0],
            "short_lt300_bytes": short_cards,
            "statuses": statuses,
            "missing_status": missing_status,
            "missing_source": missing_source,
            "missing_entity_id": missing_entity_id,
            "missing_evidence": missing_evidence,
            "evidence_field_gaps": evidence_field_gaps,
            "missing_fields": missing_fields,
            "placeholder_input_missing": placeholders,
            "normalized_name_duplicates": duplicates,
        }
    return result


def parse_link_destination(raw: str, angle: bool) -> str:
    value = raw.strip()
    if angle:
        return value
    if value.startswith(("<", '"', "'")):
        value = value[1:]
    value = re.sub(r"\s+(?:\"[^\"]*\"|'[^']*')\s*$", "", value)
    return value.strip()


def local_link_target(index: Path, raw: str, angle: bool) -> tuple[Path | None, str | None]:
    destination = unquote(parse_link_destination(raw, angle))
    parsed = urlsplit(destination)
    if parsed.scheme or destination.startswith(("//", "mailto:")):
        return None, None
    path_part = parsed.path.replace("/", "\\")
    target = (index.parent / path_part).resolve() if path_part else index.resolve()
    return target, unquote(parsed.fragment)


def markdown_slug(value: str) -> str:
    value = re.sub(r"!?\[([^]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[`*_~]", "", value).strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", value, flags=re.UNICODE)
    return re.sub(r"\s+", "-", value).strip("-")


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in read_text(path).splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            slug = markdown_slug(heading.group(1))
            if slug:
                suffix = counts.get(slug, 0)
                anchors.add(slug if suffix == 0 else f"{slug}-{suffix}")
                counts[slug] = suffix + 1
        for match in re.finditer(r"(?:id|name)=[\"']([^\"']+)[\"']", line, re.I):
            anchors.add(unquote(match.group(1)).lower())
    return anchors


def audit_single_index(index: Path, root: Path) -> dict[str, Any]:
    if not index.exists():
        return {"exists": False, "links": 0, "local_links": 0, "bad_links": [], "indexed_targets": []}
    bad_links: list[str] = []
    bad_details: list[dict[str, str]] = []
    indexed_targets: list[str] = []
    total = 0
    local_total = 0
    for match in LINK_RE.finditer(read_text(index)):
        total += 1
        raw = match.group("angle") or match.group("bare") or ""
        target, fragment = local_link_target(index, raw, match.group("angle") is not None)
        if target is None:
            continue
        local_total += 1
        destination = parse_link_destination(raw, match.group("angle") is not None)
        label = destination
        if not target.exists():
            bad_links.append(label)
            bad_details.append({"link": label, "reason": "target_missing"})
            continue
        if fragment and target.is_file() and target.suffix.lower() == ".md":
            if fragment.lower() not in markdown_anchors(target):
                bad_links.append(label)
                bad_details.append({"link": label, "reason": "anchor_missing"})
                continue
        if target.is_file():
            indexed_targets.append(relative_name(target, root))
    return {
        "exists": True,
        "links": total,
        "local_links": local_total,
        "bad_links": bad_links,
        "bad_link_details": bad_details,
        "indexed_targets": sorted(set(indexed_targets)),
    }


def audit_indexes(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for spec in config.get("categories", []):
        category = str(spec["name"])
        configured = [root / str(path) for path in spec.get("index_files", [])]
        files = {
            relative_name(path, root): audit_single_index(path, root)
            for path in configured
        }
        cards = card_files(root / str(spec["card_folder"])) if spec.get("card_folder") else []
        indexed = {
            target
            for item in files.values()
            for target in item.get("indexed_targets", [])
        }
        card_targets = {relative_name(path, root) for path in cards}
        unindexed = sorted(card_targets - indexed)
        result[category] = {
            "files": files,
            "exists": any(item.get("exists") for item in files.values()),
            "links": sum(item.get("links", 0) for item in files.values()),
            "local_links": sum(item.get("local_links", 0) for item in files.values()),
            "bad_links": [
                link
                for item in files.values()
                for link in item.get("bad_links", [])
            ],
            "bad_link_details": [
                detail
                for item in files.values()
                for detail in item.get("bad_link_details", [])
            ],
            "card_count": len(cards),
            "indexed_cards": sorted(card_targets - set(unindexed)),
            "unindexed_cards": unindexed,
        }
    return result


def merge_filename(number: int, config: dict[str, Any]) -> str:
    merge = config["merge"]
    return f"{merge['prefix']}-{number:02d}{merge['suffix']}"


def merge_source_names(numbers: list[int], config: dict[str, Any]) -> list[str]:
    return [merge_filename(number, config) for number in numbers]


def audit_merges(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    merge = config["merge"]
    folder = root / str(merge["folder"])
    merge_files = numbered_files(folder, str(merge["prefix"]), str(merge["suffix"]))
    actual_numbers = sorted(merge_files)
    max_number = max(actual_numbers, default=0)
    expected_numbers = list(range(1, max_number + 1))
    missing = [number for number in expected_numbers if number not in merge_files]
    extras = [number for number in actual_numbers if number not in expected_numbers]
    section_pattern = re.compile(str(merge["section_pattern"]), re.M)
    required_sections = int(merge.get("required_sections", 8))
    files: dict[str, Any] = {}
    for number in expected_numbers:
        path = merge_files.get(number)
        if path is None:
            files[merge_filename(number, config)] = {"exists": False}
            continue
        text = read_text(path)
        sections = len(section_pattern.findall(text))
        files[path.name] = {
            "exists": True,
            "sections": sections,
            "bytes": path.stat().st_size,
            "complete_sections": sections == required_sections,
        }
    return {
        "folder": str(folder),
        "expected_numbers": expected_numbers,
        "actual_numbers": actual_numbers,
        "missing": missing,
        "extras": extras,
        "required_sections": required_sections,
        "complete": bool(actual_numbers) and not missing and not extras,
        "files": files,
    }


def audit_terminal_inputs(root: Path, merge_numbers: list[int], config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    folders = [root / "修复" / "终审输入", root / "终审输入"]
    configured_folder = config.get("terminal_input_folder")
    if configured_folder:
        folders.insert(0, root / str(configured_folder))
    folder = next((candidate for candidate in folders if candidate.is_dir()), folders[0])
    expected = set(merge_numbers)
    expected_names = merge_source_names(merge_numbers, config)
    source_pattern = re.compile(
        rf"{re.escape(str(config['merge']['prefix']))}-(\d+){re.escape(str(config['merge']['suffix']))}",
        re.I,
    )
    for spec in config.get("categories", []):
        category = str(spec["name"])
        filename = spec.get("terminal_input")
        if not filename:
            continue
        path = folder / str(filename)
        if not path.exists():
            result[category] = {
                "exists": False,
                "source_count": 0,
                "expected_sources": expected_names,
                "missing_sources": expected_names,
                "extra_sources": [],
            }
            continue
        text = read_text(path)
        source_ids = sorted({int(value) for value in source_pattern.findall(text)})
        missing = sorted(expected - set(source_ids))
        extras = sorted(set(source_ids) - expected)
        result[category] = {
            "exists": True,
            "source_count": len(source_ids),
            "sources": merge_source_names(source_ids, config),
            "expected_sources": expected_names,
            "missing_sources": merge_source_names(missing, config),
            "extra_sources": merge_source_names(extras, config),
            "complete_sources": bool(expected) and set(source_ids) == expected,
            "bytes": path.stat().st_size,
        }
    return result


def chinese_number(value: str) -> int | None:
    digits = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}
    if not value or all(char not in digits for char in value):
        return None
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in digits:
            number = digits[char]
        elif char in units:
            unit = units[char]
            if unit < 10000:
                section += (number or 1) * unit
            else:
                section = (section + number) * unit
                total += section
                section = 0
            number = 0
        else:
            return None
    return total + section + number


def pattern_flags(names: list[str]) -> int:
    flags = re.M
    for name in names:
        flags |= getattr(re, name.upper(), 0)
    return flags


def chapter_numbers(text: str, config: dict[str, Any] | None = None) -> list[int]:
    patterns = (config or DEFAULT_CONFIG)["chapters"].get("patterns", [])
    numbers: list[int] = []
    for item in patterns:
        regex = re.compile(str(item["regex"]), pattern_flags(item.get("flags", [])))
        group = str(item.get("group", "number"))
        for match in regex.finditer(text):
            value = match.groupdict().get(group)
            if value is None:
                value = match.group(1) if match.groups() else None
            if value is None:
                continue
            number = chinese_number(value) if item.get("number_type") == "chinese" else int(value)
            if number is not None:
                numbers.append(number)
    return sorted(set(numbers))


def chapter_markers(text: str, config: dict[str, Any]) -> list[str]:
    markers: list[str] = []
    for marker in config["chapters"].get("markers", []):
        if re.search(rf"(?im)^\s*#{{0,6}}\s*{re.escape(str(marker))}(?:\s|$|[：:])", text):
            markers.append(str(marker))
    return markers


def audit_chapters(
    root: Path, first_chapter: int | None, last_chapter: int | None, config: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    candidates = [root / str(path) for path in config["chapters"].get("candidates", [])]
    for path in candidates:
        if not path.exists():
            continue
        text = read_text(path)
        nums = chapter_numbers(text, config)
        result[relative_name(path, root)] = {
            "min": min(nums) if nums else None,
            "max": max(nums) if nums else None,
            "count": len(nums),
            "markers": chapter_markers(text, config),
            "expected_first": first_chapter,
            "expected_last": last_chapter,
            "has_expected_first": first_chapter in nums if first_chapter is not None else None,
            "has_expected_last": last_chapter in nums if last_chapter is not None else None,
            "range_check_source": "arguments_or_config" if first_chapter is not None or last_chapter is not None else "not_declared",
        }
    return result


def audit_files(root: Path, expected_chunks: int | None, config: dict[str, Any]) -> dict[str, Any]:
    chunks = config["chunks"]
    return {
        "chunks_text": check_numbered(
            root / str(chunks["text"]["folder"]),
            str(chunks["text"]["prefix"]),
            str(chunks["text"]["suffix"]),
            expected_chunks,
        ),
        "chunks_extracted": check_numbered(
            root / str(chunks["extracted"]["folder"]),
            str(chunks["extracted"]["prefix"]),
            str(chunks["extracted"]["suffix"]),
            expected_chunks,
        ),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_manifest(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = root / str(config.get("output", {}).get("manifest_file", config.get("manifest_file", "manifest.json")))
    result: dict[str, Any] = {"path": str(path), "exists": path.exists(), "valid": False}
    if not path.exists():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        result["error"] = str(error)
        return result
    source = data.get("source") if isinstance(data, dict) else None
    required = {"schema_version", "created_at"}
    missing_top = sorted(field for field in required if field not in data)
    required_source = {"path", "sha256", "size_bytes", "mtime_ns"}
    missing_source = sorted(field for field in required_source if not isinstance(source, dict) or field not in source)
    result.update({"missing_top_level": missing_top, "missing_source_fields": missing_source})
    if missing_top or missing_source or not isinstance(source, dict):
        return result
    recorded_hash = str(source["sha256"]).lower()
    result["hash_format_valid"] = bool(re.fullmatch(r"[0-9a-f]{64}", recorded_hash))
    source_path = Path(str(source["path"]))
    if not source_path.is_absolute():
        source_path = (root / source_path).resolve()
    result["source_path"] = str(source_path)
    result["source_accessible"] = source_path.is_file()
    result["valid"] = result["hash_format_valid"]
    if source_path.is_file():
        stat = source_path.stat()
        actual_hash = sha256_file(source_path)
        result.update(
            {
                "hash_match": actual_hash == recorded_hash,
                "size_match": stat.st_size == int(source["size_bytes"]),
                "mtime_match": stat.st_mtime_ns == int(source["mtime_ns"]),
                "actual_sha256": actual_hash,
                "actual_size_bytes": stat.st_size,
                "actual_mtime_ns": stat.st_mtime_ns,
            }
        )
        result["valid"] = result["valid"] and result["hash_match"] and result["size_match"]
    else:
        result["source_verification"] = "unavailable_source_not_found"
    return result


def audit_pipeline_state(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    path = root / str(config.get("output", {}).get("state_file", config.get("state_file", "PIPELINE_STATE.md")))
    result: dict[str, Any] = {"path": str(path), "exists": path.exists(), "missing_headings": []}
    if not path.exists():
        result["valid"] = False
        return result
    text = read_text(path)
    required = [str(item) for item in config.get("state_required_headings", [])]
    missing = [heading for heading in required if not has_heading_or_label(text, [heading])]
    result.update({"valid": not missing, "missing_headings": missing, "bytes": path.stat().st_size})
    return result


def compare_baseline(report: dict[str, Any], baseline_path: Path | None, config: dict[str, Any]) -> dict[str, Any] | None:
    if not baseline_path or not baseline_path.exists():
        return None
    baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    categories = [str(spec["name"]) for spec in config.get("categories", []) if spec.get("card_folder")]
    old = {category: baseline.get("cards", baseline).get(category, {}).get("count") for category in categories}
    new = {category: report["cards"].get(category, {}).get("count") for category in categories}
    return {
        category: {
            "before": old[category],
            "after": new[category],
            "delta": (new[category] or 0) - (old[category] or 0),
        }
        for category in categories
    }


def strict_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for name, data in report["files"].items():
        if not data["complete"]:
            failures.append(f"files.{name}")
    if not report["merges"]["complete"]:
        failures.append("merges.numbering")
    for filename, data in report["merges"]["files"].items():
        if not data.get("complete_sections", False):
            failures.append(f"merges.sections:{filename}")
    for category, data in report["terminal_inputs"].items():
        if not data.get("complete_sources", False):
            failures.append(f"terminal_inputs.sources:{category}")
    for category, data in report["cards"].items():
        for field in (
            "empty",
            "missing_status",
            "missing_source",
            "missing_entity_id",
            "missing_evidence",
            "evidence_field_gaps",
            "missing_fields",
            "placeholder_input_missing",
            "normalized_name_duplicates",
        ):
            if data.get(field):
                failures.append(f"cards.{field}:{category}")
    for category, data in report["indexes"].items():
        if data.get("card_count", 0) and (
            not data.get("exists") or data.get("bad_links") or data.get("unindexed_cards")
        ):
            failures.append(f"indexes.coverage:{category}")
    for path, data in report["chapters"].items():
        if data.get("has_expected_first") is False or data.get("has_expected_last") is False:
            failures.append(f"chapters.range:{path}")
    manifest = report["manifest"]
    if not manifest.get("valid"):
        failures.append("manifest.invalid")
    if manifest.get("source_accessible") and not manifest.get("hash_match"):
        failures.append("manifest.hash_mismatch")
    state = report["pipeline_state"]
    if not state.get("valid"):
        failures.append("pipeline_state.invalid")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit novel-lore-distill output")
    parser.add_argument("root", type=Path, help="book distill output directory")
    parser.add_argument("--config", type=Path, help="JSON audit configuration")
    parser.add_argument("--expected-chunks", type=int, help="expected chunk count")
    parser.add_argument("--first-chapter", type=int, help="expected first chapter number")
    parser.add_argument("--last-chapter", type=int, help="expected last chapter number")
    parser.add_argument("--baseline", type=Path, help="optional repair-baseline.json")
    parser.add_argument("--report", type=Path, help="JSON report path")
    parser.add_argument("--strict", action="store_true", help="exit 1 when audit checks fail")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: output directory does not exist: {root}")
        return 2
    try:
        config = load_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: unable to load config: {error}")
        return 2
    chapters = config["chapters"]
    expected_chunks = args.expected_chunks if args.expected_chunks is not None else config.get("expected_chunks")
    first_chapter = args.first_chapter if args.first_chapter is not None else chapters.get("first")
    last_chapter = args.last_chapter if args.last_chapter is not None else chapters.get("last")
    merges = audit_merges(root, config)
    report: dict[str, Any] = {
        "schema_version": 2,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "config": str(args.config.resolve()) if args.config else "built_in_defaults",
        "files": audit_files(root, expected_chunks, config),
        "merges": merges,
        "terminal_inputs": audit_terminal_inputs(root, merges["actual_numbers"], config),
        "cards": audit_cards(root, config),
        "indexes": audit_indexes(root, config),
        "chapters": audit_chapters(root, first_chapter, last_chapter, config),
        "manifest": audit_manifest(root, config),
        "pipeline_state": audit_pipeline_state(root, config),
    }
    report["baseline_comparison"] = compare_baseline(report, args.baseline, config)
    report["strict_failures"] = strict_failures(report)
    report["strict_pass"] = not report["strict_failures"]
    default_report = root / str(config.get("output", {}).get("report_file", "修复/audit-report.json"))
    report_path = (args.report or default_report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    chunks = report["files"]["chunks_extracted"]
    print(f"root: {root}")
    print(f"chunks: {chunks['actual']}/{chunks['expected']} ({chunks['expected_source']})")
    merge_files = report["merges"]["files"]
    complete_merges = sum(1 for item in merge_files.values() if item.get("complete_sections"))
    print(f"merges complete: {complete_merges}/{len(merge_files)}")
    print(
        "terminal sources:",
        ", ".join(
            f"{category}={data.get('source_count', 0)}/{len(report['merges']['actual_numbers'])}"
            for category, data in report["terminal_inputs"].items()
        ),
    )
    for category, data in report["cards"].items():
        print(
            f"{category}: {data['count']} cards, empty={len(data['empty'])}, "
            f"missing_status={len(data['missing_status'])}, "
            f"missing_source={len(data['missing_source'])}, "
            f"missing_evidence={len(data['missing_evidence'])}"
        )
    print("bad index links:", sum(len(v.get("bad_links", [])) for v in report["indexes"].values()))
    print("strict failures:", len(report["strict_failures"]))
    print(f"report: {report_path}")
    return 1 if args.strict and report["strict_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
