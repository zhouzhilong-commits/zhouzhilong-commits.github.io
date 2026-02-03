#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit Mermaid code blocks for Mermaid 10.9.5 compatibility and style-guide consistency.

Why:
  - Mermaid 10.9.5 does NOT support `style ...` inside `sequenceDiagram` or `classDiagram`.
  - Keeping Mermaid version pinned avoids drift, but authors can still accidentally write
    unsupported syntax. This script finds (and optionally fixes) those cases.

Usage:
  python3 scripts/mermaid_audit.py
  python3 scripts/mermaid_audit.py --fix
  python3 scripts/mermaid_audit.py --paths _posts _pages

Exit codes:
  0: no issues
  1: issues found (and not fixed)
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


MERMAID_FENCE_RE = re.compile(r"^```mermaid\s*$")
FENCE_END_RE = re.compile(r"^```\s*$")


@dataclass
class MermaidBlock:
    file_path: str
    start_line: int  # 1-based
    end_line: int  # 1-based inclusive
    lines: List[str]

    def kind(self) -> str:
        for ln in self.lines:
            s = ln.strip()
            if not s or s.startswith("%%"):
                continue
            # Mermaid directive line: `%%{init: ...}%%` can appear before type
            if s.startswith("%%{") and s.endswith("}%%"):
                continue
            return s.split()[0]  # graph/flowchart/sequenceDiagram/classDiagram/...
        return "unknown"


@dataclass
class Issue:
    file_path: str
    line_no: int
    message: str


def iter_markdown_files(paths: List[str]) -> Iterable[str]:
    for base in paths:
        if os.path.isfile(base):
            yield base
            continue
        for root, _, files in os.walk(base):
            # skip generated site
            if os.path.sep + "_site" + os.path.sep in (root + os.path.sep):
                continue
            for fn in files:
                if fn.endswith(".md") or fn.endswith(".markdown"):
                    yield os.path.join(root, fn)


def parse_mermaid_blocks(file_path: str) -> List[MermaidBlock]:
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks: List[MermaidBlock] = []
    i = 0
    while i < len(lines):
        if MERMAID_FENCE_RE.match(lines[i]):
            start = i
            j = i + 1
            while j < len(lines) and not FENCE_END_RE.match(lines[j]):
                j += 1
            if j >= len(lines):
                # unterminated fence; treat as block until EOF
                end = len(lines) - 1
            else:
                end = j
            # contents exclude fences; keep only mermaid body lines
            body = lines[start + 1 : end]
            blocks.append(
                MermaidBlock(
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=end + 1,
                    lines=body,
                )
            )
            i = end + 1
            continue
        i += 1
    return blocks


def find_issues(block: MermaidBlock) -> List[Issue]:
    issues: List[Issue] = []
    kind = block.kind()
    if kind in ("sequenceDiagram", "classDiagram"):
        for idx, ln in enumerate(block.lines):
            if ln.lstrip().startswith("style "):
                issues.append(
                    Issue(
                        file_path=block.file_path,
                        line_no=block.start_line + 1 + idx,
                        message=f"`style` is not supported in {kind} (Mermaid 10.9.5). Use themeVariables or diagram-native constructs.",
                    )
                )
    return issues


def apply_fixes(block: MermaidBlock) -> Tuple[MermaidBlock, int]:
    """
    Returns (new_block, removed_lines_count).
    For now we only auto-fix: remove `style ...` lines in sequenceDiagram/classDiagram.
    """
    kind = block.kind()
    if kind not in ("sequenceDiagram", "classDiagram"):
        return block, 0

    new_lines: List[str] = []
    removed = 0
    for ln in block.lines:
        if ln.lstrip().startswith("style "):
            removed += 1
            continue
        new_lines.append(ln)
    return MermaidBlock(
        file_path=block.file_path,
        start_line=block.start_line,
        end_line=block.end_line,
        lines=new_lines,
    ), removed


def rewrite_file_with_blocks(file_path: str, updated_blocks: List[MermaidBlock]) -> None:
    """
    Rewrite file by replacing mermaid block bodies (between ```mermaid and closing ```).
    Assumes blocks are non-overlapping and in the same order as parsed.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Build an index by start fence line for replacement
    # We re-parse to find fence boundaries and then inject updated body lines.
    blocks = parse_mermaid_blocks(file_path)
    if len(blocks) != len(updated_blocks):
        raise RuntimeError(f"Block count changed unexpectedly for {file_path}")

    out: List[str] = []
    i = 0
    bi = 0
    while i < len(lines):
        if MERMAID_FENCE_RE.match(lines[i]):
            out.append(lines[i])  # ```mermaid
            # skip old body until end fence
            j = i + 1
            while j < len(lines) and not FENCE_END_RE.match(lines[j]):
                j += 1
            # inject new body
            out.extend(updated_blocks[bi].lines)
            bi += 1
            # append closing fence if present
            if j < len(lines):
                out.append(lines[j])
            i = j + 1
            continue
        out.append(lines[i])
        i += 1

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paths",
        nargs="*",
        default=["_posts", "_pages"],
        help="Directories or files to scan (default: _posts _pages)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix supported issues (currently removes `style` in class/sequence diagrams).",
    )
    args = parser.parse_args()

    all_issues: List[Issue] = []
    files = list(iter_markdown_files(args.paths))
    touched_files = set()

    for fp in files:
        blocks = parse_mermaid_blocks(fp)
        if not blocks:
            continue

        if args.fix:
            updated_blocks: List[MermaidBlock] = []
            removed_total = 0
            for b in blocks:
                nb, removed = apply_fixes(b)
                updated_blocks.append(nb)
                removed_total += removed

            # Re-check issues after fixes
            issues_after: List[Issue] = []
            for b in updated_blocks:
                issues_after.extend(find_issues(b))

            if removed_total > 0:
                rewrite_file_with_blocks(fp, updated_blocks)
                touched_files.add(fp)

            all_issues.extend(issues_after)
        else:
            for b in blocks:
                all_issues.extend(find_issues(b))

    if all_issues:
        for iss in all_issues:
            print(f"{iss.file_path}:{iss.line_no}: {iss.message}")
        return 1

    if args.fix and touched_files:
        for fp in sorted(touched_files):
            print(f"fixed: {fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

