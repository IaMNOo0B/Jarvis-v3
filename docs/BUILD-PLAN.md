# JARVIS v3 — Build Plan

## Scope

Build a new Windows-first desktop assistant in this repository. Do not copy runtime implementation from Jarvis-v2. Reuse only validated lessons and requirements, not unverified claims. Keep the project modular, testable, and safe by default.

## Architecture (target, introduced incrementally)

- `jarvis/`: application package; chat orchestration, intent parsing, providers, policy, actions, memory, reminders, and desktop integration separated into small modules.
- `tests/`: fast deterministic unit and integration tests; no live credentials or real desktop actions required by default.
- `docs/`: architecture decisions, threat model, milestone receipts, and unresolved-risk register.
- `config/`: non-secret defaults and schema only. Never store credentials here.
- `data/`: user state with explicit migration/backup rules; never overwritten by code updates.
- `scripts/`: only safe, documented helper scripts where needed.
- `.github/workflows/`: CI for supported Python versions and static checks.

This is a target layout, not a claim that these components already exist. Introduce files only when a milestone needs them.

## Milestones and exit criteria

### M0 — Requirements and safety foundation
- [ ] Document threat boundaries, approvals, secret handling, data preservation, and support claims.
- [ ] Select the minimum supported Python version and define the supported Windows test matrix.
- [ ] Add a standard-library-first test setup and CI.
- [ ] Add a risk register; distinguish open, mitigated, and verified risks.

**Exit:** repository structure and policy are reviewed; baseline CI passes.

### M1 — Text-only vertical slice
- [ ] A single application entry point and deterministic chat loop.
- [ ] Clear separation between user input, intent parsing, policy, provider, and response formatting.
- [ ] Small talk and known commands work without requiring an LLM.
- [ ] Provider failure is explicit; no invented success and no silent fallback that skips required tools.
- [ ] Cancellation and bounded timeouts are defined.

**Exit:** tests cover normal paths, malformed input, provider failure, timeout, and cancellation.

### M2 — Policy and capability registry
- [ ] Typed action/capability definitions with schemas and risk levels.
- [ ] Fail-closed approval gate for external, destructive, and hard-to-undo actions.
- [ ] One outbound-network policy point; no hidden egress.
- [ ] Tool output treated as untrusted evidence, not instructions.
- [ ] Actions report evidence and postconditions, not just that a command was issued.

**Exit:** adversarial and permission-boundary tests pass.

### M3 — Providers and credentials
- [ ] Provider interface with bounded calls and normalized errors.
- [ ] Ollama integration first; optional cloud providers behind explicit configuration.
- [ ] Credentials stored through Windows Credential Manager or an approved OS credential-store abstraction.
- [ ] Key input masked; never logged or persisted to ordinary files.
- [ ] Health checks perform a real minimal generation call and report what was actually tested.

**Exit:** fake-provider tests pass; local-model and cloud-provider checks are separately recorded when actually run.

### M4 — Windows desktop actions
- [x] App registry and deterministic verb-object routing for allow-listed launches, bounded launch sequences, Notepad typing, and explicit URL navigation.
- [x] Define a UI Automation-first adapter contract and allow-listed app/action registry; wire a narrow Windows PowerShell adapter for blank-Notepad text entry with exact read-back verification (real Windows smoke test remains open).
- [x] Wire an explicit HTTP(S)-only URL opener for Chrome/Edge using a fixed executable and `shell=False`; it reports the OS launch as attempted, not page-load verified.
- [ ] Extend semantic UI Automation beyond the narrow Notepad text-entry workflow; do not introduce coordinate-only desktop automation.
- [ ] Shell guard, visible activity/status, cancellation, and postcondition checks in live desktop integration.
- [ ] Screenshot/image data held in memory only unless the user explicitly requests otherwise.
- [ ] Run `python scripts/smoke_test_notepad_uia.py` on real Windows, inspect the exact read-back result, and record the outcome; no claim of Windows support before that run.

**Exit:** Notepad/browser actions are tested on Windows with a recorded result and a safe failure path.

### M5 — Reminders and memory
- [ ] Reminder create/list/cancel/fire lifecycle with persistence and tests.
- [ ] Memory entries include provenance and support a secure forget workflow.
- [ ] User data survives upgrades; migrations are explicit and recoverable.
- [ ] No hidden collection of conversation or telemetry data.

**Exit:** lifecycle and data-preservation tests pass; relevant Windows checks are recorded.

### M6 — GUI and optional voice
- [ ] GUI with activity feed, connection state, and genuine Stop/Esc cancellation.
- [ ] Voice is a plugin; text core remains usable without microphone or TTS.
- [ ] Visible microphone/listening indicator; no recording by default.
- [ ] Hinglish recognition and Hindi speech output are treated as unverified until tested on target hardware.

**Exit:** GUI tests pass; voice hardware result is explicitly marked tested or untested.

### M7 — Packaging and release
- [ ] Repeatable build/package process and clean-machine smoke test.
- [ ] Updates preserve user data and credentials.
- [ ] Release artifact is downloaded/read back and inspected after upload.
- [ ] Secret scan and dependency review completed.

**Exit:** artifact integrity, installation, startup, data preservation, and smoke-test receipts are recorded.

## Verification rules

1. Inspect the changed code and diff.
2. Run the complete relevant test suite after the final code change, on a clean/stable tree; CI currently runs it on Ubuntu and Windows.
3. Record exact commands, environment, counts, and failures. Do not invent local execution evidence when only CI ran.
4. Separate unit-test evidence from live provider, interactive Windows desktop, microphone, and packaging evidence; a hosted Windows runner is not proof of target-PC UI automation.
5. Scan repository artifacts for credentials and accidental user data.
6. Keep each unresolved risk open until there is direct evidence it is closed.

## Risk register (initial)

| Risk | Status | Closure evidence |
|---|---|---|
| Fresh install starts on Windows | Open | Clean Windows install/startup receipt |
| Provider health reflects real generation | Open | Minimal live generation result |
| Notepad typing confirms actual postcondition on target Windows PC | Open | Real Windows transcript showing blank-document detection, input, exact read-back; fake-adapter contract tests are not E2E evidence |
| Stop/Esc cancels in-flight work | Open | Cancellation integration test and GUI check |
| Credentials never leak into logs/artifacts | Open | Automated secret-pattern scan and code review |
| Updates preserve user data | Open | Upgrade test with pre-existing test data |
| Voice behavior on target hardware | Open | Explicit real-device test; otherwise label untested |

## Change discipline

- Small, reviewable changes; tests added alongside behavior.
- Standard library preferred. No new dependency without a clear need and approval.
- No destructive cleanup, publishing, or release actions without explicit authorization.
- Keep `main` stable; use a working branch for implementation once the initial baseline exists.
- Each delivery reports: verified, still open, and the single next step.
