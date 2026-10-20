# JARVIS v3

A Windows-first desktop AI assistant, built incrementally from a clean foundation.

## Project status

**Stage 0 — foundation and architecture.** This repository is being built from scratch; it does not inherit runtime code from Jarvis-v2. Features are not considered complete until implementation, automated tests, and relevant real-world checks support the claim.

## Design principles

- Text chat always works independently of voice.
- Deterministic intent routing before model-based planning.
- Explicit permission gates for external, destructive, or hard-to-undo actions.
- Secrets stored only in the operating system credential store; never in source, chat history, logs, or configuration files.
- No automated purchases, payments, CAPTCHA handling, or accepting terms on the user's behalf.
- Fail closed when permissions or action outcomes are unclear.
- Preserve user data across updates; never silently reset it.
- No telemetry by default.
- Prefer the Python standard library. New dependencies require a documented reason and approval.
- Windows support claims require testing on Windows; unit tests alone do not establish desktop end-to-end support.

## Initial roadmap

1. **Foundation:** repository rules, configuration, logging/redaction, test harness, and architecture records.
2. **Text core:** deterministic chat routing, command parsing, provider interface, honest errors, and cancellation.
3. **Action safety:** capability registry, approval gate, outbound-access policy, evidence-based postconditions.
4. **Providers:** local Ollama and optional cloud providers, secure credential storage, real health checks.
5. **Desktop control:** app registry and UI Automation-first actions, with visible status and safe stop.
6. **Memory and reminders:** provenance-aware memory, secure forget flow, reminder lifecycle and persistence.
7. **GUI/tray:** chat interface, activity feed, provider state, and cancellation.
8. **Voice:** optional plugin; visible microphone state, no recording by default, and explicit hardware validation.
9. **Packaging and release:** data-preserving installer/update path and verified release artifacts.

See [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) for milestones and acceptance criteria.

## Verification policy

Every milestone records what changed, exact checks run, their results, and what remains unverified. Do not describe a feature as working merely because it has been planned or mocked.
