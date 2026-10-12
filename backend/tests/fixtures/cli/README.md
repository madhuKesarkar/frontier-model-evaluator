# Recorded CLI outputs

Real outputs captured on the architect's Mac (2026-10-12), used to test the live adapters
without any model call (BE-R4).

| File | Source |
|---|---|
| `claude_ok.json` | `claude -p "Say hello" --output-format json` (Claude Code 2.1.296, Claude Pro) |
| `claude_auth_expired.json` | the same command while the sign-in had expired |
| `codex_ok.jsonl` | `codex exec --json --skip-git-repo-check --ephemeral "Say hello"` (Codex 0.162.1, ChatGPT Go, gpt-6-luna) |
