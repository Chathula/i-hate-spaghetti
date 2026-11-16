#!/bin/sh
# i-hate-spaghetti — install this skill into every coding agent on this machine.
#
#   ./install.sh                  detect installed agents, install for each
#   ./install.sh --link           symlink instead of copy (git pull updates all)
#   ./install.sh --all            install everywhere, even where detection is unsure
#   ./install.sh --project DIR    install into that project only
#
# Copy is the default: it survives the clone being moved or deleted.
set -eu

SKILL=i-hate-spaghetti
SRC=$(cd "$(dirname "$0")" && pwd)
MODE=copy
ALL=0
PROJECT=

usage() {
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --link)    MODE=link ;;
        --copy)    MODE=copy ;;
        --all)     ALL=1 ;;
        --project) shift; PROJECT=${1:-} ;;
        -h|--help) usage ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

install_into() {
    dir=$1
    dest="$dir/$SKILL"
    mkdir -p "$dir"
    rm -rf "$dest"
    if [ "$MODE" = link ]; then
        ln -s "$SRC" "$dest"
    else
        cp -R "$SRC" "$dest"
        rm -rf "$dest/.git"
    fi
    if [ -f "$dest/SKILL.md" ]; then
        echo "  installed -> $dest"
    else
        echo "  FAILED   -> $dest" >&2
        exit 1
    fi
}

if [ -n "$PROJECT" ]; then
    [ -d "$PROJECT" ] || { echo "no such directory: $PROJECT" >&2; exit 1; }
    echo "project install ($MODE):"
    install_into "$PROJECT/.agents/skills"
    install_into "$PROJECT/.claude/skills"
    echo
    echo "Commit .agents/skills/$SKILL so every agent on the team picks it up."
    exit 0
fi

echo "user install ($MODE):"
n=0

# ~/.agents/skills is the cross-agent location: Pi, omp, Codex, OpenCode, Claude Code all read it.
install_into "$HOME/.agents/skills"
n=$((n + 1))

for candidate in "$HOME/.claude:claude" "$HOME/.codex:codex" "$HOME/.config/opencode:opencode" "$HOME/.omp:omp"; do
    home_dir=${candidate%%:*}
    label=${candidate##*:}
    if [ -d "$home_dir" ] || [ "$ALL" = 1 ]; then
        install_into "$home_dir/skills"
        case $label in
            codex) echo "    note: enable skills in ~/.codex/config.toml -> [features] skills = true" ;;
            omp)   echo "    note: omp also reads ~/.agents/skills, this copy is native discovery" ;;
        esac
        n=$((n + 1))
    fi
done

echo
echo "$n location(s). Verify with:"
echo "  python3 $SRC/scripts/spaghetti.py sniff ."
