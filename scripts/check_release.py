#!/usr/bin/env python3
"""Private pre-publication hygiene checks for the public release tree."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LICENSE_TITLE = "Business Source License 1.1"
REQUIRED_NOTICE_PREFIXES = (
    "Copyright (c) 2026 Gui Costa and Venture Compass.",
    "Paid Media OS is source-available under the Business Source License 1.1 (BUSL-1.1).",
    "Commercial services are permitted as described in LICENSE; paid competing productization requires a separate license.",
)
PATTERNS = {
    "Meta account-shaped identifier": re.compile(r"\bact_[0-9]{6,}\b", re.I),
    "private-key marker": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "common token assignment": re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][^'\"\s]{12,}", re.I),
    "private home path": re.compile(r"/root/(?:cerebro-da-empresa|leo-workspace)\b", re.I),
}


def is_git_worktree(root: Path) -> bool:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    ).returncode == 0


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def scan_entries(root: Path = ROOT) -> list[tuple[str, bytes]]:
    """Return staged bytes in Git, or all portable-bundle source files otherwise."""
    if is_git_worktree(root):
        entries: list[tuple[str, bytes]] = []
        staged = [item for item in git(root, "ls-files", "-z", "--cached").decode().split("\0") if item]
        for relative in staged:
            entries.append((relative, git(root, "show", f":{relative}")))
        untracked = [item for item in git(root, "ls-files", "-z", "--others", "--exclude-standard").decode().split("\0") if item]
        for relative in untracked:
            entries.append((relative, (root / relative).read_bytes()))
        return entries
    return [
        (str(path.relative_to(root)), path.read_bytes())
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]


def text_content(raw: bytes) -> str | None:
    if b"\0" in raw:
        return None
    return raw.decode("utf-8", errors="replace")


def release_text(root: Path, relative: str) -> str:
    if is_git_worktree(root):
        try:
            raw = git(root, "show", f":{relative}")
        except subprocess.CalledProcessError:
            return ""
    else:
        try:
            raw = (root / relative).read_bytes()
        except FileNotFoundError:
            return ""
    return text_content(raw) or ""


def scan(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for relative, raw in scan_entries(root):
        text = text_content(raw)
        if text is None:
            continue
        for label, pattern in PATTERNS.items():
            if match := pattern.search(text):
                problems.append(f"{relative}: {label}: {match.group(0)!r}")
    return problems


def release_contract_problems(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    license_text = release_text(root, "LICENSE")
    notice_text = release_text(root, "NOTICE")
    readme_text = release_text(root, "README.md")
    if not license_text.startswith(LICENSE_TITLE):
        problems.append("LICENSE must contain the Business Source License 1.1 text")
    for line in REQUIRED_NOTICE_PREFIXES:
        if line not in notice_text:
            problems.append(f"NOTICE is missing required line: {line}")
    if "<COMMERCIAL_LICENSING_CONTACT>" in notice_text or "<COMMERCIAL_LICENSING_CONTACT>" in readme_text:
        problems.append("commercial licensing contact placeholder remains")
    if "source-available" not in readme_text.lower():
        problems.append("README must describe the project as source-available")
    content = "\n".join(text_content(raw) or "" for _, raw in scan_entries(root))
    pending_license_marker = "License pending " + "owner selection"
    if pending_license_marker in content:
        problems.append("a skill or document still says the license is pending")
    superseded_license_marker = "Poly" + "Form Noncommercial"
    if superseded_license_marker in content:
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
