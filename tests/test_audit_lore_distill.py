from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_lore_distill.py"
SPEC = importlib.util.spec_from_file_location("audit_lore_distill", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def all_sections() -> str:
    return "\n".join(f"## {index}、栏目{index}" for index in range(1, 9))


def valid_card() -> str:
    return """# 甲
## 实体状态
核心
## 实体 ID
char-001
## 证据
- evidence_id: E-001
  source_file: novel.txt
  source_chunk: chunk-001.txt
  source_chapter: 第十二章
  locator: 场景 A
  evidence_type: direct
  confidence: high
  fact_status: fact
## 来源
- source_file: novel.txt
- source_chunk: chunk-001.txt
- source_chapter: 第十二章
"""


class AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_chinese_and_case_insensitive_chapters(self) -> None:
        text = "序章\n第十二章\nChapter 13\n终章\n"
        config = audit.load_config(None)
        self.assertEqual(audit.chapter_numbers(text, config), [12, 13])
        self.assertEqual(audit.chapter_markers(text, config), ["序章", "终章"])

    def test_dynamic_merges_and_eight_sections(self) -> None:
        for number in (1, 2, 3):
            write(self.root / "合并" / f"merge-{number:02d}.md", all_sections())
        report = audit.audit_merges(self.root, audit.load_config(None))
        self.assertEqual(report["actual_numbers"], [1, 2, 3])
        self.assertTrue(report["complete"])
        self.assertTrue(all(item["complete_sections"] for item in report["files"].values()))

    def test_source_evidence_and_index_coverage(self) -> None:
        write(self.root / "角色" / "甲.md", valid_card())
        write(self.root / "角色" / "乙.md", "# 乙\n## 实体状态\n仅提及\n")
        write(
            self.root / "角色索引.md",
            "[甲](角色/甲.md#missing-anchor) [甲正文](角色/甲.md) [乙](角色/乙.md) [坏](角色/不存在.md)\n",
        )
        config = audit.load_config(None)
        cards = audit.audit_cards(self.root, config)["角色"]
        self.assertEqual(cards["missing_evidence"], ["乙.md"])
        self.assertEqual(cards["missing_entity_id"], ["乙.md"])
        indexes = audit.audit_indexes(self.root, config)["角色"]
        self.assertEqual(indexes["links"], 4)
        self.assertEqual(indexes["bad_links"], ["角色/甲.md#missing-anchor", "角色/不存在.md"])
        self.assertEqual(indexes["unindexed_cards"], [])

    def test_unindexed_card_is_reported(self) -> None:
        write(self.root / "角色" / "甲.md", valid_card())
        write(self.root / "角色" / "乙.md", valid_card().replace("char-001", "char-002"))
        write(self.root / "角色索引.md", "[甲](角色/甲.md)\n")
        indexes = audit.audit_indexes(self.root, audit.load_config(None))["角色"]
        self.assertEqual(indexes["unindexed_cards"], ["角色/乙.md"])

    def test_strict_exit_code_and_missing_root(self) -> None:
        root = self.root / "book"
        write(root / "分块文本" / "chunk-001.txt")
        write(root / "分块提取" / "chunk-001.md")
        report_path = root / "修复" / "report.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(root), "--strict", "--report", str(report_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertFalse(report["strict_pass"])
        missing = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root / "missing")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(missing.returncode, 2)

    def test_manifest_and_pipeline_state(self) -> None:
        source = self.root / "novel.txt"
        write(source, "source")
        manifest = {
            "schema_version": 1,
            "created_at": "2026-01-01T00:00:00+00:00",
            "source": {
                "path": str(source),
                "sha256": audit.sha256_file(source),
                "size_bytes": source.stat().st_size,
                "mtime_ns": source.stat().st_mtime_ns,
            },
        }
        write(self.root / "manifest.json", json.dumps(manifest))
        headings = "\n".join(f"## {heading}" for heading in audit.DEFAULT_CONFIG["state_required_headings"])
        write(self.root / "PIPELINE_STATE.md", headings)
        config = audit.load_config(None)
        self.assertTrue(audit.audit_manifest(self.root, config)["valid"])
        self.assertTrue(audit.audit_pipeline_state(self.root, config)["valid"])


if __name__ == "__main__":
    unittest.main()
