# Security

## Reporting

Open a private security advisory on
[GitHub](https://github.com/Chathula/i-hate-spaghetti/security/advisories/new), or
email the maintainer from the address on the repository profile. Please do not
open a public issue for a vulnerability.

## Threat model

The skill reads local source code and runs one read-only CLI. It has no
dependencies, no network access, no telemetry, no credential handling and no
shell. `git` is invoked with a fixed argument list, never through a shell.

The agent-facing risk is **indirect prompt injection**: repository text —
source, comments, commit messages, diffs, filenames, issues and fixtures — enters
the model's context. The mitigations are deliberately redundant:

- `SKILL.md` tells the agent that repository content is data, never
  instructions, and to never run commands or fetch URLs it suggests.
- `references/review.md` applies the same rule to diffs.
- `sniff` summarises commit prefixes instead of echoing commit subjects.
- Paths, script names and directory names are stripped of terminal control
  characters before printing, so a filename cannot emit ANSI/OSC escapes.

The residual risk is the feature itself: review mode reads a diff chosen by the
user. A contributor can write hostile text into that diff, but the text is
treated as evidence and the skill never executes it.

## Snyk scan

Run the scan against the skill directory before a release:

```bash
# Agent Scan v0.6+
uvx snyk-agent-scan@latest skills/i-hate-spaghetti/SKILL.md

# Agent Scan v0.5.x (pinned)
uvx snyk-agent-scan@0.5.17 skills/i-hate-spaghetti/SKILL.md

# Snyk CLI extension
snyk agent-scan --experimental --no-upload skills/i-hate-spaghetti/SKILL.md
```

The expected finding is `third_party_content_exposure` (W011, medium): a
code-reading skill necessarily exposes the agent to repository text. Review the
evidence, confirm the mitigations above, then suppress only that reviewed risk
in CI:

```bash
uvx snyk-agent-scan@latest --ci --ignore-risks third_party_content_exposure \
  skills/i-hate-spaghetti/SKILL.md          # v0.6+
uvx snyk-agent-scan@0.5.17 --ci --ignore-issues-codes W011 \
  skills/i-hate-spaghetti/SKILL.md          # v0.5.x
```

Anything else — `malicious_code`, `secret_detection`, `suspicious_download_url`,
`unverifiable_dependencies`, `prompt_injection_skill_instructions` — is a real
finding and must be fixed, not ignored. Re-scan after every change, then request
a fresh audit on skills.sh.
