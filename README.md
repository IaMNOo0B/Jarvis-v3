# JARVIS v3

A Windows-first desktop AI assistant, built incrementally from a clean foundation.

## Project status

**Early prototype — not a finished assistant.** Text chat, provider interfaces, secure credential integration, and a minimal GUI are under active development. Notepad/Chrome launch requests are recognized from a small set of natural English/Hinglish phrasings and always require per-request confirmation. Each completed chat response and app-launch attempt is now automatically recorded in the local learning database with an evidence-labelled outcome; no `/experience` command is needed for that basic history. This records what JARVIS itself observed, not whether the user's larger goal succeeded. Automatic records can contain a short task description, so users should not enter passwords or secrets into chat. Memory controls, reminders, and skill-review commands remain available, but automatic skill creation, automatic code changes, background web research, Wikipedia ingestion, voice, live UI Automation, installer, and end-to-end Windows verification are not complete. Skill proposals remain text-only and do not execute code or bypass safety gates. A compact research-ledger index has been added at `docs/JARVIS-RESEARCH-LEDGER.md`; it summarizes the submitted categories and implementation queue, but does not yet reproduce every original study entry or source file. GUI chat now performs bounded lexical retrieval from local `docs/` and `knowledge/` text files and includes source paths with an explicit untrusted-reference warning. This is local-file retrieval only—not web crawling, Wikipedia syncing, repository polling, or semantic/vector search. The ledger’s historical `[BUILT]` labels are not claims that those features exist in V3.

## Start the GUI

Requirements: Windows, Python 3.12+, and Ollama installed and running with the configured model available. No Python packages are required by this project.

- Clone or download this repository.
- Double-click `Start_JARVIS.pyw` to open the GUI without a console window.
- The default provider is local Ollama with `qwen2.5:7b-instruct-q4_K_M`; obtain the model separately in Ollama before first use.
- Use **Check AI status** for a real generation check.
- Ask naturally, e.g. `Can you please open Notepad for me?` or `Jarvis, zara Chrome kholo`. JARVIS asks for confirmation before launching. It only reports that Windows accepted the launch request; app visibility is not yet verified. Unknown apps are not launched.
- Ask for bounded public research with `research Wikipedia artificial intelligence` or `research GitHub agent framework`. JARVIS displays result titles, short snippets, source URLs and limitations. Only fixed public APIs are used; never include secrets in search queries. Wikipedia snippets are leads, not verified facts; GitHub repository metadata is not a code audit.
- Create a reminder with `/remind 2030-01-01T10:00:00+05:30 | Study`; list pending reminders with `/reminders`; cancel one with `/cancel-reminder ID`. The timestamp must include a timezone offset. Due reminders show an in-app notification while the GUI is open; there is no background service or notification guarantee while JARVIS is closed.
- Save memory only when explicitly requested with `/remember I prefer concise answers`; view it with `/memories`; delete one with `/forget ID` (confirmation required); delete all with `/forget-all` (confirmation required). Memory is local and is not automatically injected into AI prompts yet.
- If startup fails, launch `python Start_JARVIS.pyw` from a terminal to see Python diagnostics. This fallback is optional, not the normal workflow.

The GUI starts with local Ollama. To use Gemini on Windows, click **Save Gemini key…**, enter the key into the masked prompt, then choose **Google Gemini** and click **Apply**. The key is stored only in Windows Credential Manager; JARVIS does not probe the key before saving it and does not display it back. Use **Check AI status** to make a real generation request. A key may still be invalid, restricted, or out of quota; status testing is what checks whether the provider can actually respond. Never paste API keys into chat or source files.

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

## Roadmap

1. Foundation and test harness.
2. Text core and provider interface.
3. Action safety and outbound-access policy.
4. Local Ollama and optional cloud providers.
5. Desktop app registry and UI Automation-first control (contract/tests started; live adapter not wired).
6. Memory and reminders.
7. GUI/tray, activity feed, and cancellation.
8. Optional voice plugin.
9. Data-preserving packaging and updates.

See [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) for milestones and acceptance criteria.

## Verification policy

Every milestone records what changed, exact checks run, their results, and what remains unverified. Do not describe a feature as working merely because it has been planned or mocked.
