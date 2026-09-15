#!/usr/bin/env python3
"""Create a source manifest for a novel-lore-distill output directory."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a novel source manifest")
    parser.add_argument("source_file", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--force", action="store_true", help="replace an existing manifest")
    args = parser.parse_args()
    source = args.source_file.resolve()
    output_dir = args.output_dir.resolve()
    if not source.is_file():
        print(f"error: source file does not exist: {source}")
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists() and not args.force:
        print(f"error: manifest already exists; use --force to replace: {manifest_path}")
        return 2
    stat = source.stat()
    data = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(source),
            "sha256": sha256_file(source),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
    }
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest: {manifest_path}")
    print(f"sha256: {data['source']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
