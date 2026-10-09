# Security Policy

## Supported versions

Only the latest released version receives security fixes.

| Version | Supported |
| ------- | --------- |
| 0.2.x   | ✅ |
| < 0.2   | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, use
GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.

If private reporting is unavailable, contact a maintainer directly.

Please include:

- a description of the issue and its impact,
- steps to reproduce,
- affected version(s) and platform.

We aim to acknowledge reports within a few days.

## Handling credentials

`opencode2others` reads an API key supplied by you (via `--api-key`, an
environment variable, or automatic discovery from existing local configs) and
may write it into local configuration files:

- Pi: `~/.pi/agent/models.json` (`apiKey`) and, with `--write-auth`,
  `~/.pi/agent/auth.json` (mode `0600` on POSIX).
- Claude Code: `~/.claude/settings.json` (`ANTHROPIC_AUTH_TOKEN`).
- ZCode: `~/.zcode/v2/config.json` (`provider.*.options.apiKey`).
- Codex: **not** written; Codex reads it from the env var named by `env_key`.

Notes:

- Every file is backed up to `<file>.bak` before being rewritten. These backups
  contain the same secrets — keep them out of version control.
- The only network requests that include the key are the optional `--probe`
  requests, which are sent to your configured base URL (OpenCode).
- Never paste real keys into issues, pull requests or test fixtures.
