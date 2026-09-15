#!/usr/bin/env python3
"""Audit a novel-lore-distill output directory.

Usage:
    python audit_lore_distill.py <book-distill-dir>
    python audit_lore_distill.py <book-distill-dir> [--expected-chunks 40]

The script is read-only with respect to the source and card files except for
the JSON report path supplied by --report (default: <dir>/修复/audit-report.json).
Expected chunk and chapter ranges are optional because they vary by novel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

CHAPTER_RE = re.compile(r"(?:第\s*(\d+)\s*[章节回]|(?:Chapter|CHAPTER)\s+(\d+))")
SECTION_RE = re.compile(
    r"^#{1,3}\s*(?:[一二三四五六七八九十]+、|\d+[.)、．])\s*\S+", re.M
)
SOURCE_RE = re.compile(
    r"(?:^##\s*来源\s+|^\s*[-*]\s*)merge-(\d+)\.md\b", re.M
)
LINK_RE = re.compile(r"\]\(<([^>]+)>\)|\]\(([^)]+)\)")
SECTION_COUNT = 8
CARD_CATEGORIES = ("角色", "事件", "地点", "势力", "物品", "能力")
TERMINAL_INPUTS = {
    "角色": "角色-一级合并汇总.md",
    "事件": "事件-一级合并汇总.md",
    "地点": "地点-一级合并汇总.md",
    "势力": "势力-一级合并汇总.md",
    "物品": "物品-一级合并汇总.md",
    "能力": "能力-一级合并汇总.md",
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


def check_numbered(
    folder: Path, prefix: str, suffix: str, expected: int | None
) -> dict:
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
        "expected_source": "highest_actual_number" if inferred else "argument",
        "actual": len(files),
        "actual_numbers": actual_numbers,
        "missing": missing,
        "extras": extras,
        "complete": complete,
        "trailing_range_unverified": inferred,
    }


def card_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        p
        for p in folder.glob("*.md")
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
    return bool(
        re.search(r"^##\s*来源\s*$|^\s*(?:[-*]\s*)?(?:\*\*)?来源(?:\*\*)?[：:]", text, re.M)
    )


def normalize_name(name: str) -> str:
    name = re.sub(r"（[^）]*）|\([^)]*\)", "", name)
    name = re.sub(r"__重复-\d+|__修复重复\d+", "", name)
    return name.strip()


def audit_cards(root: Path) -> dict:
    result = {}
    for category in CARD_CATEGORIES:
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
    for category in CARD_CATEGORIES:
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
    merge_files = numbered_files(root / "合并", "merge", ".md")
    actual_numbers = sorted(merge_files)
    max_number = max(actual_numbers, default=0)
    expected_numbers = list(range(1, max_number + 1))
    missing = [number for number in expected_numbers if number not in merge_files]
    extras = [number for number in actual_numbers if number not in expected_numbers]
    files = {}
    for number in expected_numbers:
        path = merge_files.get(number)
        if path is None:
            files[f"merge-{number:02d}.md"] = {"exists": False}
            continue
        text = read_text(path)
        sections = len(SECTION_RE.findall(text))
        files[path.name] = {
            "exists": True,
            "sections": sections,
            "bytes": path.stat().st_size,
            "complete_sections": sections == SECTION_COUNT,
        }
    return {
        "expected_numbers": expected_numbers,
        "actual_numbers": actual_numbers,
        "missing": missing,
        "extras": extras,
        "complete": bool(actual_numbers) and not missing and not extras,
        "files": files,
    }


def merge_source_names(numbers: list[int]) -> list[str]:
    return [f"merge-{number:02d}.md" for number in numbers]


def audit_terminal_inputs(root: Path, merge_numbers: list[int]) -> dict:
    result = {}
    folder = root / "修复" / "终审输入"
    if not folder.exists():
        folder = root / "终审输入"
    expected = set(merge_numbers)
    expected_names = merge_source_names(merge_numbers)
    for category, filename in TERMINAL_INPUTS.items():
        path = folder / filename
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
        source_ids = sorted({int(value) for value in SOURCE_RE.findall(text)})
        source_names = merge_source_names(source_ids)
        missing = sorted(expected - set(source_ids))
        extras = sorted(set(source_ids) - expected)
        result[category] = {
            "exists": True,
            "source_count": len(source_ids),
            "sources": source_names,
            "expected_sources": expected_names,
            "missing_sources": merge_source_names(missing),
            "extra_sources": merge_source_names(extras),
            "complete_sources": bool(expected) and set(source_ids) == expected,
            "bytes": path.stat().st_size,
        }
    return result


def chapter_numbers(text: str) -> list[int]:
    return [int(first or second) for first, second in CHAPTER_RE.findall(text)]


def audit_chapters(
    root: Path, first_chapter: int | None, last_chapter: int | None
) -> dict:
    candidates = [
        root / "大事年表.md",
        root / "时间线.md",
        root / "chronology.md",
        root / "修复" / "暂存" / "大事记-R" / "大事年表.md",
    ]
    result = {}
    for path in candidates:
        if not path.exists():
            continue
        nums = chapter_numbers(read_text(path))
        result[str(path.relative_to(root))] = {
            "min": min(nums) if nums else None,
            "max": max(nums) if nums else None,
            "expected_first": first_chapter,
            "expected_last": last_chapter,
            "has_expected_first": first_chapter in nums if first_chapter is not None else None,
            "has_expected_last": last_chapter in nums if last_chapter is not None else None,
            "range_check_source": "arguments" if first_chapter is not None or last_chapter is not None else "not_declared",
        }
    return result


def audit_files(root: Path, expected_chunks: int | None) -> dict:
    return {
        "chunks_text": check_numbered(root / "分块文本", "chunk", ".txt", expected_chunks),
        "chunks_extracted": check_numbered(root / "分块提取", "chunk", ".md", expected_chunks),
    }


def compare_baseline(report: dict, baseline_path: Path | None) -> dict | None:
    if not baseline_path or not baseline_path.exists():
        return None
    baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    old = {
        category: baseline.get(category, {}).get("count") for category in CARD_CATEGORIES
    }
    new = {
        category: report["cards"].get(category, {}).get("count")
        for category in CARD_CATEGORIES
    }
    return {
        category: {
            "before": old[category],
            "after": new[category],
            "delta": (new[category] or 0) - (old[category] or 0),
        }
        for category in CARD_CATEGORIES
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit novel-lore-distill output")
    parser.add_argument("root", type=Path, help="book distill output directory")
    parser.add_argument("--expected-chunks", type=int, help="expected chunk count")
    parser.add_argument("--first-chapter", type=int, help="expected first chapter number")
    parser.add_argument("--last-chapter", type=int, help="expected last chapter number")
    parser.add_argument("--baseline", type=Path, help="optional repair-baseline.json")
    parser.add_argument("--report", type=Path, help="JSON report path")
    args = parser.parse_args()
    root = args.root.resolve()
    merges = audit_merges(root)
    report = {
        "root": str(root),
        "files": audit_files(root, args.expected_chunks),
        "merges": merges,
        "terminal_inputs": audit_terminal_inputs(root, merges["actual_numbers"]),
        "cards": audit_cards(root),
        "indexes": audit_indexes(root),
        "chapters": audit_chapters(root, args.first_chapter, args.last_chapter),
    }
    report["baseline_comparison"] = compare_baseline(report, args.baseline)
    report_path = (args.report or (root / "修复" / "audit-report.json")).resolve()
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
            f"short<300={len(data['short_lt300_bytes'])}"
        )
    print("bad index links:", sum(len(v.get("bad_links", [])) for v in report["indexes"].values()))
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
