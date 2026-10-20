# JARVIS V3 — Master Implementation Map

Updated: 2026-10-20
Purpose: one integrated backlog and release gate. This is a plan plus implementation receipts, not a claim that every capability exists.

## Product outcome

Sir types one natural-language message in the JARVIS window. JARVIS classifies the intent, plans supported steps, checks permissions and prerequisites, executes only registered capabilities, verifies postconditions, and reports what happened. It asks a question only when an essential detail is missing or policy requires approval. Unknown tasks are answered as chat or reported unsupported; they never become arbitrary shell/code execution.

## One entry point

- `JARVIS.bat` is the single user-facing Windows entry point: double-click starts JARVIS directly; pass `--menu` to open setup/repair, safe update, diagnostics, and exit options.
- Start can create a local Python virtual environment on first run.
- Setup checks Python 3.12+, Tkinter and SQLite.
- Update is fast-forward-only and refuses a dirty working tree.
- Diagnostics report Python, Git, environment and Ollama presence.
- No extra BAT entry points are retained.
- Limitation: setup does not silently install third-party dependencies, download multi-GB models, create accounts, or configure cloud credentials. A signed installer and clean-Windows verification remain release work.

## Capability map and acceptance gates

| Area | Current baseline | Required work before release |
|---|---|---|
| Conversation/provider | Text GUI; Ollama and explicit Gemini provider paths | Provider failure/timeout tests, clear status, no silent cloud fallback, live provider smoke tests |
| Intent/planning | Deterministic supported-intent planner | Natural-language routing for known safe actions; clarify ambiguity; reject unknown actions |
| Orchestration | Registered capability registry, planner-to-runtime bridge, GUI dispatch for bounded research, allow-listed app launch sequences, blank-Notepad typing workflow, explicit URL navigation, Stop/Esc cancellation checkpoints | Integration regression tests, per-step plan journal, real Windows UI automation and verified postconditions |
| Desktop | Allow-listed app launches/sequences; explicit validated HTTP(S) URL opening in Chrome/Edge; narrow PowerShell UIA workflow for typing into a detected blank Notepad document with exact read-back | Real Windows smoke test and recorded evidence; extend semantic selectors to more apps/actions; no coordinate-only automation; keep the app registry and shell guard |
| Verification | UI action postcondition contract and task receipts | Each action supplies observable evidence; distinguish attempted/failed/unknown/verified; no fake success |
| Permissions | Fail-closed SafetyGate for supported actions | Centralize every side effect through policy; approvals for external/destructive/irreversible actions; test bypass attempts |
| Memory | SQLite provenance, explicit remember/list/forget | data migration and backup tests; retrieval rules; deletion coverage; no untrusted memory as instructions |
| Learning/skills | Experience records and reviewable skill proposals | quality evaluation, provenance, sandboxed trial; never auto-grant permissions or execute a learned text blob |
| Knowledge | Bounded lexical local-doc search | chunk refresh/deletion, source trust, citations, prompt-budget enforcement, poisoning tests |
| Public research | Explicit bounded Wikipedia/GitHub API queries and SQLite archive | license/security review for code sources, deduplication, independent fact checks; no automatic execution |
| Scout/reverse engineering | Research register and adoption notes | opt-in scheduled scans, rate limits, source provenance, repo static analysis, dependency/license/threat checks, patch proposals only |
| Self-healing | Reviewable repair proposals for unexpected desktop-worker exceptions; `/repairs` read-only listing | isolated worktree, patch diff, focused/full tests, health checks, rollback evidence; no silent live self-editing |
| Voice | Not complete | wake-word, visible mic state, Hinglish STT, Hindi TTS, interruption/stop; text works without voice; target-PC tests |
| Phone remote | Not complete | authenticated pairing, scoped commands, replay protection, expiry, revocation and unknown-outcome handling |
| Browser/web | Explicit HTTP(S) URL opening in allow-listed Chrome/Edge only; no page interaction | Add browser UI Automation with semantic selectors, explicit domain/network policy, page content treated as untrusted, per-action evidence; no inferred downloads/form submissions |
| Proactivity | Not complete | opt-in schedule, daily cap, urgency rules, dismissal suppression, no unsolicited external side effects |
| Security/privacy | secret storage and bounded activity journal | secret scans, egress tests, injection tests, data retention/forget audit, screenshot memory-only default, no telemetry |
| Performance | Local-first target for RTX 2060 6 GB / 16 GB RAM | measure cold/warm latency, memory/VRAM and model throughput; enforce timeouts and memory guard; never claim unmeasured speed |
| Release/updates | Unified BAT menu and guarded updater source | Windows clean install/upgrade, preserve databases/credentials, signed/package integrity checks, rollback, inspect uploaded artifact |
| Research ledger | Compact index of 258 numbered studies and topic collections | full exact original prose import is still incomplete; only mark each item built after V3 code/tests/platform evidence |

## Cross-cutting execution contract

1. Convert user text into a typed intent and plan.
2. Only code-registered capabilities may execute; model output cannot register a handler or supply executable code.
3. Validate arguments, preconditions, risk, approval, and cancellation.
4. Execute one bounded step at a time; parallelize only independent, explicitly safe steps.
5. Record each step's start/end, redacted arguments, outcome class, and evidence pointer. Do not log secrets or full transcripts by default.
6. Verify a real postcondition. A process launch accepted by Windows is not proof the app is visible; a tool call returning is not proof the user's goal was achieved.
7. On failure, stop dependent steps, classify the failure, and offer a safe recovery. Never blind-retry a non-idempotent action.
8. Final response reports completed-and-verified, attempted/unverified, failed/blocked, and remaining work separately.

## Build order (integrated; do not release partial modules as a finished product)

### Gate A — Safe core
- Wire the orchestration registry into chat/task dispatch.
- Add typed task state and cancellation through GUI workers.
- Add persistent per-step receipts and postcondition evidence contracts. (Step receipts now cover public research, bounded app-launch sequences, URL navigation (URL omitted from durable receipts), and the Notepad text workflow; exact read-back is implemented, but live Windows evidence remains open.)
- Add adversarial, ambiguity, timeout, cancellation and secret-redaction tests.

### Gate B — Desktop vertical slice
- A narrow Windows-only PowerShell UI Automation backend is wired behind the adapter for Notepad text entry into a detected blank document; input is passed as JSON over stdin to a fixed script, with `shell=False` and a bounded helper timeout. A registered read-only preflight checks that Windows and the fixed PowerShell helper are available before it launches Notepad.
- Unit tests cover approval gating, adapter payload/allow-list limits, partial outcomes and exact read-back contract. `scripts/smoke_test_notepad_uia.py` now provides a manual, confirmation-gated real-Windows test: open one blank Notepad document, run the script, type `RUN`, and record its exact read-back result. It has not yet been run on real Windows.
- An explicit-URL-only navigation capability is wired for allow-listed Chrome/Edge; test only navigation to the exact user-supplied HTTP(S) URL and report the process launch as attempted, not page-verified. Never infer arbitrary downloads, credentials, clicks or form submissions.
- Run real Windows smoke tests; fake adapters remain unit tests, not proof of desktop support.

### Gate C — Resilience and knowledge
- Integrate bounded knowledge retrieval and research archive with provenance.
- Isolated repair workspace: generate proposal, inspect diff, run focused tests, full tests, health checks, then ask approval before applying. Preserve backup and rollback.
- Evaluate on a golden task suite including Hinglish and injection attempts.

### Gate D — Optional capabilities
- Voice, phone remote, browser actions, scheduled scout, proactivity, analytics and model training each require their own permission model and platform tests. They do not block the text core from functioning.

### Gate E — Release
- Test clean install and upgrade on supported Windows.
- Confirm user data survives update and restore procedure works.
- Secret/dependency/license scans, CI green on final commit, package integrity read-back, version and rollback notes.
- Only then call it release-ready.

## Current receipts (2026-10-20)

- `JARVIS.bat` is merged to `main` as the one user-facing entry point. Double-click starts the GUI directly and bootstraps a private `.venv` on first run; `JARVIS.bat --menu` opens maintenance options. Duplicate BAT entry points were removed.
- GUI multiline output formatting was corrected in the working branch.
- Public research, archive, task receipts and reviewable learning/self-healing records exist as bounded prototype modules. Step receipts are now persisted for public research, allow-listed app launch sequences, explicit URL navigation, and Notepad text entry; URL and typed-text payloads are omitted from durable task/learning receipts. The Notepad text limit is enforced in UTF-16 code units before launch and again at the capability/UIA boundary. A read-only preflight prevents known helper/platform-unavailable cases from launching Notepad; successful preflight is not itself a side effect. Typing targets only a blank document and reports verified only after exact read-back. This is not evidence of a real Windows smoke test.
- jarvis/orchestration.py now defines a fail-closed capability registry, approval gate, cancellation checkpoints and explicit evidence outcomes. Unit tests were added in tests/test_orchestration.py.
- GUI dispatch now routes explicit Wikipedia/GitHub research, allow-listed app launch sequences, fixed Notepad text entry, and explicit HTTP(S) URL navigation through the registered capability registry and task runtime. Automatic reflection supports `action_verified`, `action_partial`, and `action_unknown` without silently treating them as generic failures. Unexpected desktop-worker exceptions now create a generic reviewable repair proposal; normal precondition failures and ambiguous/partial outcomes do not. `/repairs` lists the latest proposals read-only. No proposal changes live code automatically. Stop/Esc cancellation is wired to chat generation, research and provider health checks; launch cancellation warns that the app may already have opened. Cancellation cannot forcibly interrupt an in-flight provider/network call; it discards the result at the next safe boundary.
- Automated CI passed on commit `58477eaa74163421ebe36ae65d2ef2edb8da338f` ([run 39470402752](https://github.com/IaMNOo0B/Jarvis-v3/actions/runs/39470402752)): Python source compilation, GUI-launcher compilation, PowerShell helper syntax parsing on Windows, and all **212 standard-library tests on both Ubuntu and Windows** passed. Windows CI exposed and helped fix open SQLite handles during temporary-database cleanup; DB-backed stores now use a shared transaction scope that commits/rolls back and always closes handles. The `.pyw` launcher now sets the project working directory and displays a redacted startup diagnostic if an exception escapes startup. A Windows CI runner is not an interactive target-PC GUI test. The manual Notepad smoke script and double-click GUI launch still need real user-PC verification. Stop/Esc cancellation is wired to chat, research and provider health checks at safe boundaries; active provider/network calls are not forcibly interrupted. Cancellation during app launch is reported as unknown because the app may already have opened. Accepted launch requests still do not prove that a window became visible.
- PR #2 was squash-merged to `main` on 2026-10-20 (merge commit `36c691ebaad98bbe684b73615a34dae047ab713a`). This does not make the project fully release-ready: the real Windows launcher/UIA smoke test, clean install/upgrade/data-preservation checks, and packaging gates remain open.

## Definition of done

Release is allowed only when Gates A–E have their relevant automated tests passing, Windows-specific claims have real Windows evidence, no critical security issue remains open, the updater preserves user data, the final package is inspected after upload, and every feature status is backed by evidence. Research inventory tags from older versions are never treated as V3 proof.