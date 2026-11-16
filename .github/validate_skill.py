#!/usr/bin/env python3
"""Validate the skill before it ships: frontmatter, limits, and that every
referenced support file exists. Vendored from the portable-agent-skills skill.

    python3 .github/validate_skill.py skills/i-hate-spaghetti

Exit 0 clean, 1 problems found. Stdlib only.
"""
import re
import sys
from pathlib import Path

MAX_NAME = 64
MAX_DESCRIPTION = 500  # Codex rejects longer; the spec allows 1024
MAX_LINES = 500        # the spec's recommendation for SKILL.md
NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
PATH_RE = re.compile(r"(?:scripts|references|templates|assets)/[\w./-]+")


def split_frontmatter(text):
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with '---' at byte 0 (no leading blank line or BOM)")
    end = re.search(r"\n---\s*\n", text[3:])
    if not end:
        raise ValueError("unterminated frontmatter: no closing '---' line")
    return text[3:end.start() + 3], text[end.end() + 3:]


def field(block, key):
    match = re.search(r"^" + key + r":\s*(.+)$", block, re.M)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def validate(skill_dir):
    problems = []
    skill = skill_dir / "SKILL.md"
    if not skill.is_file():
        return ["no SKILL.md in " + str(skill_dir)]
    text = skill.read_text(encoding="utf-8", errors="replace")
    try:
        block, body = split_frontmatter(text)
    except ValueError as exc:
        return [str(exc)]

    name = field(block, "name")
    description = field(block, "description")
    if not name:
        problems.append("frontmatter: missing 'name'")
    if not description:
        problems.append("frontmatter: missing 'description'")

    if name:
        if not NAME_RE.fullmatch(name):
            problems.append("name '%s': lowercase letters, digits and single hyphens only" % name)
        if len(name) > MAX_NAME:
            problems.append("name is %d chars (max %d)" % (len(name), MAX_NAME))
        if skill_dir.resolve().name != name:
            problems.append("name '%s' != directory '%s' - clients index by directory"
                            % (name, skill_dir.resolve().name))

    if description:
        if len(description) > MAX_DESCRIPTION:
            problems.append("description is %d chars (max %d for Codex CLI)"
                            % (len(description), MAX_DESCRIPTION))
        if "use when" not in description.lower():
            problems.append("description states what but not when - add 'Use when ...', "
                            "it is the routing signal")

    lines = len(text.splitlines())
    if lines > MAX_LINES:
        problems.append("SKILL.md is %d lines (max %d) - move depth into references/"
                        % (lines, MAX_LINES))

    for ref in sorted(set(PATH_RE.findall(body))):
        if not (skill_dir / ref).exists():
            problems.append("referenced file missing: " + ref)

    return problems


def main(argv):
    targets = [Path(a) for a in argv[1:]] or [Path("skills/i-hate-spaghetti")]
    failed = False
    for target in targets:
        problems = validate(target)
        if problems:
            failed = True
            print("FAIL " + str(target), file=sys.stderr)
            for problem in problems:
                print("  - " + problem, file=sys.stderr)
        else:
            print("ok   " + str(target))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
