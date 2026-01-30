#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
De-duplicate '计算机基础' posts (cs-os/cs-network/cs-arch), keep one canonical post per topic,
add redirect_from for removed permalinks, delete duplicates, and regenerate sidebar nav sections
in `_data/navigation.yml` so the sidebar is complete.

Selection rule (per topic):
- Prefer the post with the most lines (assume more content = higher quality).
- Tie-breaker: prefer the higher note number (usually newer).
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "_posts"
NAV_PATH = ROOT / "_data" / "navigation.yml"

CS_PAT = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<cs>cs-(?:os|network|arch))-note-(?P<note>\d+)-(?P<topic>[a-z0-9-]+)\.md$"
)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def split_front_matter(text: str) -> Tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    fm = "---" + parts[1] + "---\n"
    body = parts[2].lstrip("\n")
    return fm, body


def get_fm_value(front_matter: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\\s*(.+?)\\s*$", front_matter, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()


def parse_redirect_from(front_matter: str) -> List[str]:
    # very small YAML subset: redirect_from: then indented list items
    lines = front_matter.splitlines()
    out: List[str] = []
    in_block = False
    for line in lines:
        if re.match(r"^redirect_from\\s*:\\s*$", line.strip()):
            in_block = True
            continue
        if in_block:
            if re.match(r"^\\S", line):  # next top-level key
                break
            m = re.match(r"^\\s*-\\s*(.+?)\\s*$", line)
            if m:
                out.append(m.group(1).strip())
    return out


def upsert_redirect_from(front_matter: str, redirects: List[str]) -> str:
    redirects = [r if r.startswith("/") else ("/" + r) for r in redirects]
    redirects = [r if r.endswith("/") else (r + "/") for r in redirects]
    existing = parse_redirect_from(front_matter)
    merged = []
    seen = set()
    for r in existing + redirects:
        if r not in seen:
            merged.append(r)
            seen.add(r)

    if not merged:
        return front_matter

    block = "redirect_from:\\n" + "\\n".join([f"  - {r}" for r in merged]) + "\\n"

    if re.search(r"^redirect_from\\s*:\\s*$", front_matter, re.M):
        # Replace existing block
        def repl(m: re.Match) -> str:
            return block

        # Replace from redirect_from: line up to (but not including) next top-level key or end.
        pattern = re.compile(r"^redirect_from\\s*:\\s*$[\\s\\S]*?(?=^\\S|\\Z)", re.M)
        return pattern.sub(block.rstrip("\\n"), front_matter).rstrip("\\n") + "\\n"

    # Insert before closing --- (just before the last line '---')
    fm_lines = front_matter.splitlines()
    if fm_lines and fm_lines[-1].strip() == "---":
        # insert before last line
        new_lines = fm_lines[:-1] + [block.rstrip("\\n")] + [fm_lines[-1]]
        return "\\n".join(new_lines) + "\\n"

    # fallback: append
    return front_matter.rstrip("\\n") + "\\n" + block


@dataclass
class PostInfo:
    path: Path
    cs: str
    topic: str
    note: int
    title: str
    permalink: str
    lines: int


def collect_cs_posts() -> List[PostInfo]:
    posts: List[PostInfo] = []
    for p in POSTS_DIR.glob("*.md"):
        m = CS_PAT.match(p.name)
        if not m:
            continue
        cs = m.group("cs")  # cs-os / cs-network / cs-arch
        topic = m.group("topic")
        note = int(m.group("note"))
        s = read_text(p)
        fm, _ = split_front_matter(s)
        title = get_fm_value(fm, "title")
        permalink = get_fm_value(fm, "permalink")
        posts.append(PostInfo(p, cs, topic, note, title, permalink, len(s.splitlines())))
    return posts


def select_canonical(group: List[PostInfo]) -> PostInfo:
    # Most lines, then higher note number.
    return sorted(group, key=lambda x: (x.lines, x.note), reverse=True)[0]


def regenerate_nav_section(nav_text: str, key: str, title: str, items: List[Tuple[str, str]]) -> str:
    """
    Replace nav section for `key:` with a newly generated one.
    items: list of (title, url)
    """
    section = [f"{key}:", f"  - title: \"{title}\"", "    children:"]
    for t, url in items:
        section.append(f"      - title: \"{t}\"")
        section.append(f"        url: {url}")
    section_text = "\n".join(section) + "\n"

    # Match from '^key:' up to next top-level key (line starting without indentation) or EOF.
    # Some editors may introduce \r; be robust.
    pattern = re.compile(rf"^(?:\\ufeff)?{re.escape(key)}:[\\s\\S]*?(?=^(?:\\ufeff)?\\S|\\Z)", re.M)
    if pattern.search(nav_text):
        return pattern.sub(section_text.rstrip("\\n"), nav_text).rstrip("\\n") + "\\n"

    # Fallback: append at end (should not normally happen).
    return nav_text.rstrip("\\n") + "\\n\\n" + section_text


def main() -> int:
    posts = collect_cs_posts()
    groups: Dict[Tuple[str, str], List[PostInfo]] = {}
    for pi in posts:
        groups.setdefault((pi.cs, pi.topic), []).append(pi)

    deletions: List[PostInfo] = []
    redirects_to_add: Dict[Path, List[str]] = {}

    for key, group in groups.items():
        if len(group) <= 1:
            continue
        canonical = select_canonical(group)
        others = [x for x in group if x.path != canonical.path]
        # collect redirects from others' permalinks
        other_links = [x.permalink for x in others if x.permalink]
        redirects_to_add.setdefault(canonical.path, []).extend(other_links)
        deletions.extend(others)

    # Apply redirect_from updates
    for path, redirects in redirects_to_add.items():
        s = read_text(path)
        fm, body = split_front_matter(s)
        new_fm = upsert_redirect_from(fm, redirects)
        write_text(path, new_fm + body)

    # Delete duplicates
    for pi in deletions:
        pi.path.unlink(missing_ok=True)

    # Rebuild sidebars for cs_os/cs_network/cs_arch based on remaining posts
    remaining = collect_cs_posts()
    by_cs: Dict[str, List[PostInfo]] = {"cs-os": [], "cs-network": [], "cs-arch": []}
    for pi in remaining:
        by_cs.setdefault(pi.cs, []).append(pi)

    for cs in by_cs:
        by_cs[cs].sort(key=lambda x: x.note)

    nav = read_text(NAV_PATH)
    nav = regenerate_nav_section(
        nav, "cs_os", "操作系统", [(p.title, p.permalink) for p in by_cs.get("cs-os", []) if p.permalink]
    )
    nav = regenerate_nav_section(
        nav, "cs_network", "计算机网络", [(p.title, p.permalink) for p in by_cs.get("cs-network", []) if p.permalink]
    )
    nav = regenerate_nav_section(
        nav, "cs_arch", "计算机组成", [(p.title, p.permalink) for p in by_cs.get("cs-arch", []) if p.permalink]
    )
    write_text(NAV_PATH, nav)

    print(f"Updated redirect_from on {len(redirects_to_add)} canonical posts.")
    print(f"Deleted {len(deletions)} duplicate posts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

