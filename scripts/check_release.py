#!/usr/bin/env python3
"""Fail a release check when public-source hygiene is not satisfied."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".json", ".txt", ".example", ".yml", ".yaml"}
BANNED = [
    r"date in brazil", r"gaidly", r"indexgpt", r"worksitecam", r"motioned",
    r"pixel educa", r"bruno kamoto", r"betmgm",
]
PORTUGUESE = [r"\bnao\b", r"\bcriativos\b", r"\bpublicar\b", r"\bconta de anuncios\b", r"\bcliente\b"]
SECRET_ASSIGNMENT = re.compile(r"(?im)^\s*(?:export\s+)?(?:META_ACCESS_TOKEN|META_APP_SECRET|META_APP_ID)\s*=\s*(?!['\"]?(?:REPLACE|set-this|your-|example|<))[^#\s'\"]")


def text_files() -> list[Path]:
    return [
        p for p in ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
        and ".git" not in p.parts and p.name != "check_release.py"
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--release", action="store_true", help="Also require a final public license")
    args = p.parse_args()
    findings: list[str] = []
    for path in text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        for pattern in BANNED:
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append(f"{relative}: blocked term matching /{pattern}/")
        for pattern in PORTUGUESE:
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append(f"{relative}: possible non-English term matching /{pattern}/")
        if SECRET_ASSIGNMENT.search(text):
            findings.append(f"{relative}: possible committed credential assignment")
    if args.release and "LICENSE PENDING" in (ROOT / "LICENSE").read_text(encoding="utf-8").upper():
        findings.append("LICENSE: public release needs an owner-selected license")
    if findings:
        print("Release hygiene check failed:", file=sys.stderr)
        print("\n".join(f"- {line}" for line in findings), file=sys.stderr)
        return 1
    print("Release hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
