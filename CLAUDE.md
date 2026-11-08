# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

`main` has no application source yet — git tracks only `README.md`. The other root files (`devops-guidelines.md`, `user-available-skills.md`, `skills-lock.json`, `initial-project-setup.html`, `.mcp.json`) are governance/tooling, not app code. The `accounts/`, `config/`, `core/`, and `delivery/` directories at the repo root contain **only stray `__pycache__` files with no matching `.py` sources** — leftover compiled artifacts from elsewhere, not a working app on this branch. Don't mistake their presence for real code.

Stated purpose (per the user, 2026-11-08): a Telegram bot that fetches information and updates https://reutl.vercel.app/reut/2026-2027/e4/. No tech stack, dependencies, or bot code exist yet for that purpose — don't guess at a stack nobody picked.

**Divergent work-in-progress to be aware of:** the git worktree at `.claude/worktrees/survey-pipeline-task8/` (branch `worktree-survey-pipeline-task8`) holds a separate, already-substantial Django implementation — a multi-tenant "weekly school atmosphere survey" platform (roster import, anonymized per-pupil survey tokens, SMS/email delivery via a pluggable gateway). It has no Telegram or reutl.vercel.app integration, and its own CLAUDE.md (in that directory) describes its architecture. The two directions don't match — confirm with the user which product this repo is actually building before extending either one; don't assume the worktree's survey platform is secretly "the same project" as the Telegram bot.

An MCP server, `codebase-memory-mcp`, is configured in `.mcp.json` at the repo root.

When real application code lands on `main`, update this file with:
- Build, lint, and test commands (including how to run a single test)
- High-level architecture and structure notes that aren't obvious from browsing individual files

## Commit messages

When committing and pushing, write a meaningful commit message that covers both:
- **Business/why**: what user-facing or product problem this addresses, or why the change matters
- **Technical/what**: the concrete implementation change made

Keep it concise (a short summary line, plus 1-3 bullets if needed) — not a changelog dump.

## Available skills tracking

`user-available-skills.md` is an append-only log of skills available for use in this project. Whenever a new skill is added/installed/used for the first time, append it there (name + one-line description). Never remove an entry, even after that skill is no longer used.

## DevOps guidelines

`devops-guidelines.md` tracks DevOps/CI-CD/release requirements (branch policy, pipelines, deployments, infra, environments, secrets). Whenever a requirement or decision touches this domain, update that file to reflect it.
