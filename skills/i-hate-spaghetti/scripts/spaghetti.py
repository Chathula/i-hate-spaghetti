#!/usr/bin/env python3
"""i-hate-spaghetti: sniff a repo's conventions, score its structural noise.

    sniff [path]      project contract: stack, build, tests, layout, naming
    score [files...]  per-file findings: long files/functions, deep nesting,
                      duplicated blocks, commented-out code, TODOs, comment noise

Output is plain when piped; --color auto|always|never overrides (NO_COLOR disables
the default). Exit codes for score: 0 clean, 1 findings, 2 usage error. Findings
are heuristics that point at code worth a second look; they are not verdicts.
"""
import argparse
import os
import sys
from pathlib import Path

from analysis import (
    git, is_source, lint_configs, naming_style, walk, read_lines,
    scan_file, duplicate_findings, detect_package_managers, package_scripts,
    test_locations, comment_style, LANGS, SKIP_DIRS, rel,
)

CODES = {
    "bold": "1", "dim": "2", "red": "31", "green": "32",
    "yellow": "33", "cyan": "36",
}
NOISE_CHECKS = {"commented-code", "todos", "long-lines", "noise-ratio"}


class Theme:
    """ANSI painter. Padding is applied before painting, so widths never count escapes."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text, *names):
        if not self.enabled or not names:
            return text
        return "".join(f"\033[{CODES[n]}m" for n in names) + text + "\033[0m"


def want_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never" or "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def print_kv(rows, style: Theme) -> None:
    """Aligned `key: value` block — the sniff contract."""
    width = max(len(label) for label, _ in rows) + 1
    for label, value in rows:
        print(style(f"{label}:".ljust(width), "dim") + " " + value)


def print_biggest(sizes, root: Path, style: Theme) -> None:
    top = sorted(sizes, reverse=True)[:5]
    width = max([len("lines")] + [len(str(count)) for count, _ in top])
    print(style("biggest:", "dim"))
    print(style(f"  {'lines'.rjust(width)}  file", "dim"))
    for count, path in top:
        print(f"  {style(str(count).rjust(width), 'yellow')}  {rel(path, root)}")


def cmd_sniff(root: Path, style: Theme) -> int:
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

    rows = [
        ("stack", " ".join(f"{k}({v})" for k, v in ranked)),
        ("size", f"{len(files)} source files, {total_lines:,} lines, max depth {min(depth, 10)}"),
    ]
    managers = detect_package_managers(root)
    if managers:
        rows.append(("build", " ".join(managers)))
    scripts = package_scripts(root)
    if scripts:
        rows.append(("scripts", " ".join(scripts)))
    lints = lint_configs(root)
    if lints:
        rows.append(("lint", " ".join(lints)))
    tests = test_locations(root)
    if tests:
        rows.append(("tests", ", ".join(tests)))

    top_dirs = sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in SKIP_DIRS
    )[:12]
    if top_dirs:
        rows.append(("layout", " ".join(top_dirs)))
    rows.append(("comments", comment_style(files)))

    print(style("i-hate-spaghetti", "bold") + style(" · project contract", "dim"))
    print_kv(rows, style)
    print_biggest(sizes, root, style)

    print_kv([(
        "naming",
        naming_style([p.name for _, p in sorted(sizes, reverse=True)[:40]]) + " (dominant)",
    )], style)

    log = git(["log", "-3", "--format=%s"], root)
    if log:
        print_kv([("commits", " | ".join(s[:60] for s in log.splitlines()))], style)
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


def cmd_score(args, style: Theme) -> int:
    root = Path(".")
    targets = pick_targets(args, root)
    if not targets:
        print("score: 0 flags in 0 of 0 files")
        return 0

    per_file = {p: scan_file(p, args.max_lines, args.max_func, args.max_nest) for p in targets}
    for path, line, check, detail in duplicate_findings(targets, root):
        per_file.setdefault(path, []).append((line, check, detail))

    groups = {path: found for path, found in per_file.items() if found}
    total = sum(len(found) for found in groups.values())
    if not args.quiet:
        for path in sorted(groups):
            print(style(rel(path, root), "bold", "cyan"))
            for line, check, detail in sorted(groups[path]):
                tone = "yellow" if check in NOISE_CHECKS else "red"
                number = style(str(line).rjust(5), "dim")
                print(f"  {number}  {style(check.ljust(14), tone)}  {detail}")

    pct = 100 * len(groups) / len(targets)
    tone = "green" if not total else "yellow"
    summary = (f"score: {style(str(total), tone)} flags in "
               f"{len(groups)} of {len(targets)} files ({pct:.1f}%)")
    print(summary)
    return 1 if total else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="spaghetti", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="auto (TTY only) | always | never",
    )
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
    style = Theme(want_color(args.color))
    try:
        return cmd_sniff(Path(args.path), style) if args.cmd == "sniff" else cmd_score(args, style)
    except KeyboardInterrupt:
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # e.g. piped into `head`
        sys.exit(0)
