# External agent research notes

Research date: 2026-10-20

This document records architectural ideas reviewed for JARVIS V3. External repositories are references, not trusted code. No third-party runtime code was copied into JARVIS V3 as part of this research pass. Any future code adoption requires license review, dependency/security review, compatibility tests, and a focused diff.

## Candidates

- [Microsoft UFO](https://github.com/microsoft/UFO) — Windows-native desktop-agent research and UI interaction; newer UFO³ work describes DAG task decomposition, asynchronous orchestration, and multi-device agent coordination. Best research target for Windows UIA and future task orchestration. It is a substantial system and should not be imported wholesale into this stdlib-first Python 3.12 prototype.
- [Browser Use](https://github.com/browser-use/browser-use) — browser-specific agent interaction. Useful for a dedicated browser skill adapter, but adds dependencies and browser lifecycle/security considerations; keep optional and behind an explicit capability.
- [MineDojo Voyager](https://github.com/MineDojo/Voyager) — lifelong skill acquisition using an executable skill library and feedback/self-verification. Its Minecraft environment and GPT-4/Node stack do not fit JARVIS directly. Adopt the concept of reusable skills with provenance and verification, not the game-specific implementation.
- [NvlFR/self-evolving-agent](https://github.com/NvlFR/self-evolving-agent) — recursive self-improvement experiment with a persistent self-model and evolution history. Early/experimental work; not suitable for wholesale runtime adoption. Its history/self-model concept is reflected conservatively in explicit experience records.
- [Johin2/self-heal](https://github.com/Johin2/self-heal) — failure-aware repair loop, retaining prior failed attempts and verifying outcomes. Useful principle for future repair orchestration; automatically rewriting running functions is not appropriate for the current desktop assistant.
- [Bravim-Ketan-Purohit/self-healing-agent](https://github.com/Bravim-Ketan-Purohit/self-healing-agent) — isolated execution and traceback-driven repair. Its README explicitly identifies sandboxing as load-bearing. JARVIS should not execute generated code on the host; a future repair runner needs a real isolation boundary and test gate.
- [psyduckler/self-healing-agents](https://github.com/psyduckler/self-healing-agents) — detect, diagnose, risk-score, repair, verify, and learn from recurring errors. Useful direction for a bounded self-healing subsystem.
- [agentclash/agentic-memory](https://github.com/agentclash/agentic-memory) — semantic, episodic, and procedural memory separation. It uses a more complex embedding/provider stack; JARVIS starts with local SQLite and explicit provenance to avoid adding a mandatory dependency or outbound calls.

## Implemented from this research pass

- Added jarvis/learning.py: local SQLite episodic records plus procedural skill proposals.
- Added tests/test_learning.py: persistence, exact normalized trigger lookup, pending-by-default behavior, rejection, one-time review, provenance checks, and input bounds.
- Added GUI commands: /experience, /experiences, /learn, /skills, /approve-skill, and /reject-skill.
- A proposal is text-only and is not executable. It is not automatically injected into prompts, cannot authorize a desktop action, and cannot modify JARVIS source. Approval means the user reviewed and accepted a reusable procedure record, not that it has blanket permission to run.
- Updated README to disclose this capability and its limitations.

## Deliberately not adopted

- Unrestricted self-modifying code, automatic installation of third-party repositories, unattended host-shell execution, and blanket desktop permissions.
- Required browser/agent frameworks before a license, dependency, security, and Windows-compatibility review.
- Claims of subjective self-awareness. The practical engineering target is inspectable self-state: health, task progress, error history, memory provenance, and verified capabilities.

## Remaining integration work

1. Add a tested, cancellable task planner and postcondition-based action runner.
2. Implement Windows UI Automation and browser adapters as optional capability modules.
3. Build a self-healing repair workflow that produces isolated patches, runs tests, and can roll back; never silently rewrites protected policy.
4. Add remote phone control only after authenticated pairing, replay protection, permission scopes, and clear device status are tested.
5. Add golden end-to-end Windows receipts for desktop, voice, remote commands, credentials, upgrades, and secret scanning.