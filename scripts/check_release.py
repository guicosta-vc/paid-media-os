#!/usr/bin/env python3
"""Private pre-publication hygiene checks for the public release tree."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LICENSE_TITLE = "Business Source License 1.1"
REQUIRED_NOTICE_PREFIXES = (
    "Copyright (c) 2026 Gui Costa and Venture Compass.",
    "Paid Media OS is source-available under the Business Source License 1.1 (BUSL-1.1).",
    "Commercial services are permitted as described in LICENSE; competing productization requires a separate license.",
)
PATTERNS = {
    "Meta account-shaped identifier": re.compile(r"\bact_[0-9]{6,}\b", re.I),
    "private-key marker": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "common token assignment": re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][^'\"\s]{12,}", re.I),
    "private home path": re.compile(r"/root/(?:cerebro-da-empresa|leo-workspace)\b", re.I),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    )
    return [ROOT / item for item in result.stdout.decode().split("\0") if item]


def text_content(path: Path) -> str | None:
    raw = path.read_bytes()
    if b"\0" in raw:
        return None
    return raw.decode("utf-8", errors="replace")


def scan() -> list[str]:
    problems: list[str] = []
    for path in tracked_files():
        text = text_content(path)
        if text is None:
            continue
        rel = path.relative_to(ROOT)
        for label, pattern in PATTERNS.items():
            if match := pattern.search(text):
                problems.append(f"{rel}: {label}: {match.group(0)!r}")
    return problems


def release_contract_problems() -> list[str]:
    problems: list[str] = []
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notice_text = (ROOT / "NOTICE").read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    if not license_text.startswith(LICENSE_TITLE):
        problems.append("LICENSE must contain the Business Source License 1.1 text")
    for line in REQUIRED_NOTICE_PREFIXES:
        if line not in notice_text:
            problems.append(f"NOTICE is missing required line: {line}")
    if "<COMMERCIAL_LICENSING_CONTACT>" in notice_text or "<COMMERCIAL_LICENSING_CONTACT>" in readme_text:
        problems.append("commercial licensing contact placeholder remains")
    if "source-available" not in readme_text.lower():
        problems.append("README must describe the project as source-available")
    pending_license_marker = "License pending " + "owner selection"
    if pending_license_marker in "\n".join(
        text_content(path) or "" for path in tracked_files()
    ):
        problems.append("a skill or document still says the license is pending")
    superseded_license_marker = "Poly" + "Form Noncommercial"
    if superseded_license_marker in "\n".join(text_content(path) or "" for path in tracked_files()):
        problems.append("a file still references the superseded " + superseded_license_marker + " license")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    problems = scan()
    if args.release:
        problems.extend(release_contract_problems())
    if problems:
        print("Release hygiene failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Release hygiene passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
