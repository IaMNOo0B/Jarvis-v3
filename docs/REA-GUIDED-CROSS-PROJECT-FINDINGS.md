# REA-Guided Cross-Project Findings for JARVIS v3

Review date: 2026-10-21

This is a targeted source/document inspection, not a claim that every line of each repository has been audited. Findings below are tied to specific files read from the public repositories. No external runtime code was copied into JARVIS. Adopted ideas are reimplemented in JARVIS's own Python/standard-library architecture.

## REA: how to study software without guessing

Source: https://github.com/morluto/rea
- `.agents/skills/reverse-engineer-anything/SKILL.md` explicitly says to use ordinary repository tools for a complete source repository and reserve REA for claims requiring shipped binaries, decompilation, passive runtime evidence, or behavior not established by available source.
- REA's workflow routes the target first, traces one concrete feature, preserves artifact/provider identity and evidence, and keeps unknowns explicit. It does not claim to recover original source or automatically clone behavior.
- REA's own safety/setup guidance treats tool registration, provider availability, and user approval as separate boundaries.

**V3 adoption:** added `jarvis/source_inspection.py` and `/inspect-source [symbol]`. It inventories Python files, hashes them, parses AST without importing/executing source, lists symbols/imports/static calls, and surfaces parse/size warnings. This is a dependency-free adaptation, not REA integration or binary analysis. Static calls remain incomplete for aliases, dynamic dispatch, and runtime behavior.

## Dodaios: task orchestration and self-built skills

Sources:
- https://github.com/Dodaios/Dodaios/blob/main/docs/adr/0009-self-healing-worker-critic.md
- https://github.com/Dodaios/Dodaios/blob/main/docs/adr/0043-self-built-skills-go-live-on-trial.md
- https://github.com/Dodaios/Dodaios/blob/main/docs/product/privacy-safety-and-support/safety-and-approvals.md

Observed design:
- The worker/critic ADR separates typed Action from runtime-produced Observation; an LLM's narration is not proof that a tool succeeded.
- The critic loop has a hard iteration cap and evidence requirements. Tasks use isolated git worktrees rather than writing directly into the user's working tree.
- The self-built skill path requires deterministic validation, replay of prior requests, execution proof, usage/correction monitoring, and an undo/archive path. A passing router match alone is not enough to prove a skill works.
- The approval guide treats approval as authorization for one exact tool call, not a blanket permission for the rest of a task.

**V3 adoption decision:** preserve typed runtime outcomes, explicit postcondition verification, bounded retries, isolated candidate branches/workspaces, and narrow approvals. V3 already has task receipts and reviewable repair/skill proposals, but it does not yet have Dodaios's complete worker/critic system or validated self-building trial pipeline. Do not claim those features are implemented.

## Thoth: tool safety and memory architecture

Sources:
- https://github.com/tokwalabs/Thoth/blob/main/mcp_client/safety.py
- https://github.com/tokwalabs/Thoth/blob/main/memory.py
- https://github.com/tokwalabs/Thoth

Observed design:
- MCP tools are named with normalized server/tool namespaces. Default risk classification considers destructive hints, read-only hints, known browser-session-safe tools, and name/description patterns. Heuristics are useful defaults, not a substitute for a deterministic per-tool policy.
- The public memory wrapper keeps a stable interface while delegating persistence to a knowledge-graph layer, allowing callers to remain decoupled from storage internals.
- The project emphasizes local-first data and opt-in tools/providers.

**V3 adoption decision:** keep tool interfaces stable and risk decisions code-enforced; don't grant permissions from an LLM-generated tool description. V3's explicit memory and capability registry are simpler and remain the authority. A graph/vector database would add dependencies and should only be introduced after a retrieval benchmark demonstrates a real need.

## NOVA: tool dispatch, bounded execution, and memory sync

Sources:
- https://github.com/vincenzo-afk/NOVA/blob/main/core/tools/dispatcher.py
- https://github.com/vincenzo-afk/NOVA/blob/main/core/memory/memory_router.py
- https://github.com/vincenzo-afk/NOVA/blob/main/tasks/phase_verify.py

Observed design:
- Tool registration checks that the callable signature can accept the schema fields; execution has a non-blocking token-bucket rate limiter and redacts sensitive argument fields in error handling.
- Memory synchronization tracks duplicate identities, protects shared pending-sync state with a lock, and removes queued entries only after confirmed remote success.
- Phase verification is an explicit executable test path rather than treating a roadmap checkbox as evidence.

**V3 adoption decision:** add regression tests around tool contract mismatches, secret redaction, cancellation, and sync/error recovery before adding more tools. Do not import NOVA's large dependency stack (voice, vision, vector stores, web crawlers, and optional services) into V3 wholesale.

## Cross-project decisions for V3

1. One runtime-owned source of truth for action results; model text cannot promote an attempted action to success.
2. Keep source provenance, hashes, exact paths/lines, warnings, and unknowns visible during investigations.
3. Build changes on a branch/worktree, run focused tests then the full suite, and retain a diff plus test receipt before considering merge.
4. Learned skills and self-repairs remain proposals until deterministic checks and review policy pass. No unrestricted live self-editing.
5. Keep local data and credentials intact during upgrades; use OS credential storage for secrets.
6. Prefer JARVIS's existing standard-library-first modules. Add external dependencies only with a demonstrated capability gap, license/provenance review, and measured acceptance test.

## Current status and limits

- Implemented in this PR: static Python source inventory, hashes, AST definitions/imports/call names, exact-name tracing, GUI command, and unit tests.
- CI is still pending for the latest PR head at the time this note was written.
- Not implemented by this PR: binary decompilation, live browser/runtime observation, full multi-agent worker/critic, generated-code execution, self-building skills, or automatic rollback.
- The three external projects were inspected through selected source/docs, not exhaustively line-by-line. Further feature-specific audits should name the exact behavior, exact revision, evidence, proposed V3 change, and tests.
