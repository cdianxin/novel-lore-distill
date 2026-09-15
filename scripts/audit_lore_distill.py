#!/usr/bin/env python3
"""Audit a novel-lore-distill output directory.

Usage:
    python audit_lore_distill.py <book-distill-dir> [--baseline repair/repair-baseline.json]

The script is read-only with respect to the output directory except for the
JSON report path supplied by --report (default: <dir>/修复/audit-report.json).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

CHAPTER_RE = re.compile(r"第(\d+)章")
SECTION_RE = re.compile(r"^#{1,3}\s*[一二三四五六七]、", re.M)
SOURCE_RE = re.compile(r"^## 来源 merge-(\d\d)\.md\s*$", re.M)
LINK_RE = re.compile(r"\]\(<([^>]+)>\)|\]\(([^)]+)\)")
CATEGORIES = ("角色", "副本", "鬼", "势力", "道具")
TERMINAL_INPUTS = {
    "角色": "角色-一级合并汇总.md",
    "副本": "副本-一级合并汇总.md",
    "鬼": "鬼-一级合并汇总.md",
    "势力": "势力-一级合并汇总.md",
    "道具": "道具-一级合并汇总.md",
    "术语": "术语-一级合并汇总.md",
    "大事记": "大事记-一级合并汇总.md",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def numbered_files(folder: Path, prefix: str, suffix: str) -> dict[int, Path]:
    result: dict[int, Path] = {}
    if not folder.exists():
        return result
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+){re.escape(suffix)}$")
    for path in folder.iterdir():
        match = pattern.match(path.name)
        if match:
            result[int(match.group(1))] = path
    return result


def check_numbered(folder: Path, prefix: str, suffix: str, expected: int) -> dict:
    files = numbered_files(folder, prefix, suffix)
    missing = [i for i in range(1, expected + 1) if i not in files]
    extras = sorted(i for i in files if i < 1 or i > expected)
    return {
        "folder": str(folder),
        "expected": expected,
        "actual": len(files),
        "missing": missing,
        "extras": extras,
        "complete": not missing,
    }


def card_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        p for p in folder.glob("*.md")
        if "索引" not in p.name and "index" not in p.name.lower()
    )


def entity_status(text: str) -> str | None:
    patterns = (
        r"^##\s*实体状态\s*$\n\s*(?:[-*]\s*)?(.+?)\s*$",
        r"^\s*(?:-\s*)?(?:\*\*)?实体状态(?:\*\*)?[：:]\s*(.+?)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.M)
        if match:
            return match.group(1).strip()
    return None


def source_present(text: str) -> bool:
    return bool(re.search(r"^##\s*来源\s*$|^\s*(?:-\s*)?(?:\*\*)?来源(?:\*\*)?[：:]", text, re.M))


def normalize_name(name: str) -> str:
    name = re.sub(r"（[^）]*）|\([^)]*\)", "", name)
    name = re.sub(r"__重复-\d+|__修复重复\d+", "", name)
    return name.strip()


def audit_cards(root: Path) -> dict:
    result = {}
    for category in CATEGORIES:
        folder = root / category
        cards = card_files(folder)
        statuses: dict[str, int] = {}
        missing_status: list[str] = []
        missing_source: list[str] = []
        placeholders: list[str] = []
        short_cards: list[str] = []
        normalized: dict[str, list[str]] = {}
        for path in cards:
            text = read_text(path)
            status = entity_status(text)
            if status is None:
                missing_status.append(path.name)
                status = "未标注"
            statuses[status] = statuses.get(status, 0) + 1
            if not source_present(text):
                missing_source.append(path.name)
            if "输入未提供" in text:
                placeholders.append(path.name)
            if path.stat().st_size < 300:
                short_cards.append(path.name)
            normalized.setdefault(normalize_name(path.stem), []).append(path.name)
        duplicates = {k: v for k, v in normalized.items() if k and len(v) > 1}
        result[category] = {
            "count": len(cards),
            "empty": [p.name for p in cards if p.stat().st_size == 0],
            "short_lt300_bytes": short_cards,
            "statuses": statuses,
            "missing_status": missing_status,
            "missing_source": missing_source,
            "placeholder_input_missing": placeholders,
            "normalized_name_duplicates": duplicates,
        }
    return result


def audit_indexes(root: Path) -> dict:
    result = {}
    for category in CATEGORIES:
        paths = [root / f"{category}索引.md", root / category / f"{category}索引.md"]
        for index in paths:
            key = str(index.relative_to(root))
            if not index.exists():
                result[key] = {"exists": False, "links": 0, "bad_links": []}
                continue
            bad: list[str] = []
            total = 0
            for line in read_text(index).splitlines():
                match = LINK_RE.search(line)
                if not match:
                    continue
                rel = match.group(1) or match.group(2)
                total += 1
                if not (index.parent / rel).exists():
                    bad.append(rel)
            result[key] = {"exists": True, "links": total, "bad_links": bad}
    return result


def audit_merges(root: Path) -> dict:
    result = {}
    merge_dir = root / "合并"
    for number in range(1, 10):
        path = merge_dir / f"merge-{number:02d}.md"
        if not path.exists():
            result[path.name] = {"exists": False}
            continue
        text = read_text(path)
        result[path.name] = {
            "exists": True,
            "sections": len(SECTION_RE.findall(text)),
            "bytes": path.stat().st_size,
            "complete_sections": len(SECTION_RE.findall(text)) == 7,
        }
    return result


def audit_terminal_inputs(root: Path) -> dict:
    result = {}
    folder = root / "修复" / "终审输入"
    if not folder.exists():
        folder = root / "终审输入"
    for category, filename in TERMINAL_INPUTS.items():
        path = folder / filename
        if not path.exists():
            result[category] = {"exists": False, "source_count": 0}
            continue
        text = read_text(path)
        sources = sorted(set(SOURCE_RE.findall(text)))
        result[category] = {
            "exists": True,
            "source_count": len(sources),
            "sources": sources,
            "has_merge_04": "04" in sources,
            "has_merge_08": "08" in sources,
            "complete_sources": sources == [f"{i:02d}" for i in range(1, 10)],
            "bytes": path.stat().st_size,
        }
    return result


def audit_chapters(root: Path) -> dict:
    candidates = [root / "大事年表.md", root / "修复" / "暂存" / "大事记-R" / "大事年表.md"]
    result = {}
    for path in candidates:
        if not path.exists():
            continue
        nums = [int(value) for value in CHAPTER_RE.findall(read_text(path))]
        result[str(path.relative_to(root))] = {
            "min": min(nums) if nums else None,
            "max": max(nums) if nums else None,
            "has_first": 1 in nums,
            "has_last_1567": 1567 in nums,
        }
    return result


def audit_files(root: Path) -> dict:
    return {
        "chunks_text": check_numbered(root / "分块文本", "chunk", ".txt", 81),
        "chunks_extracted": check_numbered(root / "分块提取", "chunk", ".md", 81),
    }


def compare_baseline(report: dict, baseline_path: Path | None) -> dict | None:
    if not baseline_path or not baseline_path.exists():
        return None
    baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    old = {
        category: baseline.get(category, {}).get("count")
        for category in CATEGORIES
    }
    new = {
        category: report["cards"].get(category, {}).get("count")
        for category in CATEGORIES
    }
    return {category: {"before": old[category], "after": new[category], "delta": (new[category] or 0) - (old[category] or 0)} for category in CATEGORIES}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit novel-lore-distill output")
    parser.add_argument("root", type=Path, help="book distill output directory")
    parser.add_argument("--baseline", type=Path, help="optional repair-baseline.json")
    parser.add_argument("--report", type=Path, help="JSON report path")
    args = parser.parse_args()
    root = args.root.resolve()
    report = {
        "root": str(root),
        "files": audit_files(root),
        "merges": audit_merges(root),
        "terminal_inputs": audit_terminal_inputs(root),
        "cards": audit_cards(root),
        "indexes": audit_indexes(root),
        "chapters": audit_chapters(root),
    }
    report["baseline_comparison"] = compare_baseline(report, args.baseline)
    report_path = (args.report or (root / "修复" / "audit-report.json")).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"root: {root}")
    print(f"chunks: {report['files']['chunks_extracted']['actual']}/81")
    print(f"merges complete: {sum(1 for x in report['merges'].values() if x.get('complete_sections'))}/9")
    print("terminal sources:", ", ".join(f"{k}={v.get('source_count', 0)}/9" for k, v in report["terminal_inputs"].items()))
    for category, data in report["cards"].items():
        print(f"{category}: {data['count']} cards, empty={len(data['empty'])}, missing_status={len(data['missing_status'])}, missing_source={len(data['missing_source'])}, short<300={len(data['short_lt300_bytes'])}")
    print("bad index links:", sum(len(v.get("bad_links", [])) for v in report["indexes"].values()))
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
