#!/usr/bin/env python3
"""i-hate-spaghetti: sniff a repo's conventions, score its structural noise.

    sniff [path]      project contract: stack, build, tests, layout, naming
    score [files...]  per-file findings: long files/functions, deep nesting,
                      duplicated blocks, commented-out code, TODOs, comment noise

Exit codes for score: 0 clean, 1 findings, 2 usage error. Findings are
heuristics that point at code worth a second look; they are not verdicts.
"""
import argparse
import sys
from pathlib import Path

from analysis import (
    git, is_source, lint_configs, naming_style, walk, read_lines,
    scan_file, duplicate_findings, detect_package_managers, package_scripts,
    test_locations, LANGS, SKIP_DIRS, rel,
)


def cmd_sniff(root: Path) -> int:
    files = list(walk(root))
    if not files:
        print("no source files found")
        return 1

    langs = {}
    for path in files:
        lang = LANGS[path.suffix.lower()]
        langs[lang] = langs.get(lang, 0) + 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])[:5]

    total_lines, sizes = 0, []
    for path in files:
        count = len(read_lines(path))
        total_lines += count
        sizes.append((count, path))
    depth = max((len(Path(rel(p, root)).parts) - 1 for p in files), default=0)

    print("stack:  " + " ".join(f"{k}({v})" for k, v in ranked))
    print(f"size:   {len(files)} source files, {total_lines:,} lines, max depth {min(depth, 10)}")

    managers = detect_package_managers(root)
    if managers:
        print("build:  " + " ".join(managers))
    scripts = package_scripts(root)
    if scripts:
        print("scripts: " + " ".join(scripts))
    lints = lint_configs(root)
    if lints:
        print("lint:   " + " ".join(lints))
    tests = test_locations(root)
    if tests:
        print("tests:  " + ", ".join(tests))

    top_dirs = sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in SKIP_DIRS
    )[:12]
    if top_dirs:
        print("layout: " + " ".join(top_dirs))

    print("biggest:")
    for count, path in sorted(sizes, reverse=True)[:5]:
        print(f"        {rel(path, root)} ({count} lines)")
    print(f"naming: {naming_style([p.name for _, p in sorted(sizes, reverse=True)[:40]])} (dominant)")

    log = git(["log", "-3", "--format=%s"], root)
    if log:
        print("commits: " + " | ".join(s[:60] for s in log.splitlines()))
    return 0


def changed_files(root: Path):
    for ref in ("HEAD", "HEAD~1"):
        out = git(["diff", "--name-only", ref], root)
        if out:
            return [root / line for line in out.splitlines() if is_source(Path(line))]
    return []


def pick_targets(args, root: Path):
    targets = []
    for item in args.files:
        path = Path(item)
        targets.extend(walk(path) if path.is_dir() else [path] if path.is_file() else [])
    if not args.files and args.diff:
        targets = changed_files(root)
    return [p for p in targets or list(walk(root)) if is_source(p)]


def cmd_score(args) -> int:
    root = Path(".")
    targets = pick_targets(args, root)
    if not targets:
        print("score: 0 flags in 0 of 0 files")
        return 0

    per_file = {p: scan_file(p, args.max_lines, args.max_func, args.max_nest) for p in targets}
    for path, line, check, detail in duplicate_findings(targets, root):
        per_file.setdefault(path, []).append((line, check, detail))

    lines, flagged, total = [], 0, 0
    for path in sorted(per_file):
        found = per_file[path]
        if not found:
            continue
        flagged += 1
        total += len(found)
        lines.extend(f"{rel(path, root)}:{line}  {check}  {detail}" for line, check, detail in sorted(found))

    if not args.quiet:
        print("\n".join(lines))
    pct = 100 * flagged / len(targets)
    print(f"score: {total} flags in {flagged} of {len(targets)} files ({pct:.1f}%)")
    return 1 if total else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="spaghetti", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    sniff = sub.add_parser("sniff", help="print the project contract")
    sniff.add_argument("path", nargs="?", default=".")

    score = sub.add_parser("score", help="report structural findings")
    score.add_argument("files", nargs="*", help="files or directories (default: whole repo)")
    score.add_argument("--diff", action="store_true", help="only files changed vs HEAD")
    score.add_argument("--max-lines", type=int, default=400)
    score.add_argument("--max-func", type=int, default=60)
    score.add_argument("--max-nest", type=int, default=4)
    score.add_argument("--quiet", action="store_true", help="summary line only")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return cmd_sniff(Path(args.path)) if args.cmd == "sniff" else cmd_score(args)
    except KeyboardInterrupt:
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # e.g. piped into `head`
        sys.exit(0)
