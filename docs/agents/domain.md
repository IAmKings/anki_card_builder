# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout: multi-context

This repo uses a **multi-context** domain docs layout: a root `GLOSSARY-MAP.md` points to one `GLOSSARY.md` per context, and each context keeps its own `docs/adr/`.

At setup time neither file exists yet. They are created lazily by `/domain-modeling` (reached via `/grill-with-docs` and `/improve-codebase-architecture`): the root `GLOSSARY-MAP.md` and the per-context `GLOSSARY.md` files appear the first time a term or a decision is actually written down. Do not create empty placeholders up front.

> Naming note: this version of the skills uses `GLOSSARY.md` / `GLOSSARY-MAP.md`. Older versions used `CONTEXT.md` / `CONTEXT-MAP.md`; if such files are ever found in this repo they should be renamed to the glossary names.

## Before exploring, read these

- **`GLOSSARY-MAP.md`** at the repo root if it exists — it points at one `GLOSSARY.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.
- **`src/<context>/docs/adr/`** — context-scoped decisions, in multi-context repos.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── GLOSSARY-MAP.md                    ← points at every context's glossary
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── <context-a>/
    │   ├── GLOSSARY.md
    │   └── docs/adr/                  ← context-specific decisions
    └── <context-b>/
        ├── GLOSSARY.md
        └── docs/adr/
```

The contexts are the ones declared in `GLOSSARY-MAP.md`; until that file exists, treat the repo as having no named contexts rather than inventing them.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the relevant `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
