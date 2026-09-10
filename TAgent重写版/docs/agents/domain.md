# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **single-context**: one `CONTEXT.md` at the root, one `docs/adr/` directory.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the glossary / ubiquitous language.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

Neither exists yet in this repo — that is expected and fine.

## File structure

```
/
├── CONTEXT.md
├── docs/
│   ├── adr/
│   │   ├── 0001-....md
│   │   └── 0002-....md
│   └── agents/          ← this directory
├── basic-agent/
├── open-webui/
├── deploy/
└── scripts/
```

## Existing human-facing documentation

This repo already carries hand-written docs in Chinese. They are **not** domain docs in the sense above — don't treat them as `CONTEXT.md` or as ADRs — but they are useful background when exploring:

- `README.md` — quick start, architecture overview
- `文档/TAgent-v1项目说明与启动手册.md` — project manual
- `文档/代码手册/` — code manual
- `日志/开发日志.md` — development log
- `日志/测试方法.md` — testing methodology

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
