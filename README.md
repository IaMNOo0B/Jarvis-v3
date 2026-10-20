# JARVIS v3

A Windows-first desktop AI assistant, built incrementally from a clean foundation.

## Project status

**Early prototype — not a finished assistant.** Text chat, provider interfaces, secure credential integration, and a minimal GUI are under active development. Explicit natural-language launch requests for a fixed allow-list of local Windows apps are recognized in English/Hinglish and run without a second confirmation dialog; this does not authorize arbitrary commands. Each completed chat response and app-launch attempt is now automatically recorded in the local learning database with an evidence-labelled outcome; no `/experience` command is needed for that basic history. This records what JARVIS itself observed, not whether the user's larger goal succeeded. Automatic records can contain a short task description, so users should not enter passwords or secrets into chat. Memory controls, reminders, and skill-review commands remain available, but automatic skill creation, automatic code changes, background web research, Wikipedia ingestion, voice, broad desktop automation, installer, and end-to-end Windows verification are not complete. A narrow Windows PowerShell UI Automation path for typing into a detected blank Notepad document is wired and checks exact read-back; it has not yet been tested on a real Windows host. Skill proposals remain text-only and do not execute code or bypass safety gates. A compact research-ledger index has been added at `docs/JARVIS-RESEARCH-LEDGER.md`; it summarizes the submitted categories and implementation queue, but does not yet reproduce every original study entry or source file. GUI chat now performs bounded lexical retrieval from local `docs/` and `knowledge/` text files and includes source paths with an explicit untrusted-reference warning. This is local-file retrieval only—not web crawling, Wikipedia syncing, repository polling, or semantic/vector search. The ledger’s historical `[BUILT]` labels are not claims that those features exist in V3.

## Complete implementation scope

The consolidated feature inventory, build order, safety rules, and release gates live in [docs/MASTER-IMPLEMENTATION-MAP.md](docs/MASTER-IMPLEMENTATION-MAP.md). Treat it as the single roadmap; the research ledger records study provenance and implementation evidence.


### Automated task execution boundary

The GUI routes supported app-launch, bounded multi-app launch, blank-Notepad text-entry and public-research intents through the code-registered capability registry and task runtime. The Notepad path launches Notepad, targets only a detected blank document, then checks the entered text by reading it back. Unknown intents never become shell commands. Use **Stop** or **Esc** to request cooperative cancellation of chat, research, and provider health checks; a running network/provider call may continue until its timeout, and its result is discarded at the next safe boundary. If cancellation arrives during app launch, check whether the app opened before retrying. This is not yet full general-purpose desktop automation.

## One-click Windows control

Use **`JARVIS.bat`** as the only setup/control entry point. It opens one menu for:
1. Start JARVIS (creates the Python environment on first run if needed).
2. First-time setup or environment repair checks.
3. Safe update (only on a clean Git checkout; fast-forward only).
4. Diagnostics for Python, Git, local environment, and Ollama.
5. Exit.

The menu checks Python 3.12+, Tkinter, and SQLite. It does not install third-party packages, download an AI model, or configure cloud credentials automatically. Ollama and the configured model remain separate prerequisites for local AI chat. Updates never reset or force-overwrite local changes.

Local databases and the virtual environment are ignored by Git. Back up user data before manual repository operations.

**Verification note:** the batch menu is source-reviewed but has not yet been executed on a real Windows machine. It is not a signed installer, and this project remains a prototype.

## Start the GUI

Requirements: Windows, Python 3.12+, and Ollama installed and running with the configured model available. No Python packages are required by this project.

- Clone or download this repository.
- Double-click `Start_JARVIS.pyw` to open the GUI without a console window.
- The default provider is local Ollama with `qwen2.5:7b-instruct-q4_K_M`; obtain the model separately in Ollama before first use.
- Use **Check AI status** for a real generation check.
- Ask naturally, e.g. `Can you please open Notepad for me?`, `open Notepad and Calculator`, `open Notepad and type Hello Sir`, `type Hello Sir in Notepad`, `open the calculator`, `launch Visual Studio Code`, `Jarvis, zara Chrome kholo`, or `open https://example.com in Edge`. Explicit requests to open allow-listed apps no longer need a separate confirmation popup. Supported apps are Notepad, Chrome, Edge, Calculator, File Explorer, Task Manager, Paint, Windows Terminal, and VS Code. JARVIS reports that Windows accepted app-launch requests; app visibility is not verified. The Notepad typing path is restricted to a detected blank document and reports verified only after exact text read-back. It requires Windows PowerShell and UI Automation support; no real-Windows smoke test has yet been recorded. Supplied Notepad text and explicit browser URLs are omitted from durable task/learning receipts (both are still visible in the live GUI transcript). Unknown apps and arbitrary window typing are not supported. Explicit HTTP(S) URLs can be opened in Chrome (default) or Edge; JARVIS reports only that Windows accepted the browser-open request, not that the page loaded. It will not click page elements, download files, or submit forms as part of this command.
- Use `/help` for the in-app command list. Use `/tasks` to view the last 10 automatically recorded task receipts, `/repairs` to inspect recent reviewable diagnostic proposals, and `/clear-tasks` to delete task receipts after confirmation. `/repairs` is read-only: proposals do not edit live code or run generated code. These distinguish generated responses, accepted launch requests, and research lookups; they do not claim the user's overall goal succeeded. Obvious API-key/token patterns are redacted before task receipts are stored.
- Ask naturally for information, for example `Can you find information about black holes?`, `Look up on Wikipedia artificial intelligence`, or `Please search for GitHub agent frameworks`. Common lookup wording is routed automatically to the bounded Wikipedia or GitHub public API, so you do not need to memorize a special command. Unknown requests remain chat and never become arbitrary shell commands. JARVIS displays result titles, short snippets, source URLs and limitations, and saves the result metadata to a local SQLite archive. Use `/research-history` to review the last 10 research runs. Only fixed public APIs are used; redirects and unapproved hosts are blocked. Never include secrets in search queries. Wikipedia snippets are leads, not verified facts; GitHub repository metadata is not a code audit.
- Create reminders naturally: `Remind me in 20 minutes to study` or `Remind me tomorrow at 8:30 PM to study`. Ambiguous times such as `tomorrow at 8` are not guessed. The explicit fallback is `/remind 2030-01-01T10:00:00+05:30 | Study`; list pending reminders with `/reminders`; cancel one with `/cancel-reminder ID`. The timestamp must include a timezone offset. Due reminders show an in-app notification while the GUI is open; there is no background service or notification guarantee while JARVIS is closed.
- Save memory naturally with `Remember that I prefer concise answers`; ask `What do you remember about me?` to review it, or `Forget that I prefer concise answers` to request deletion (confirmation required). `/remember`, `/memories`, `/forget ID`, and `/forget-all` remain available. Memory is saved only on an explicit request, credential-like content is rejected, and memory is not automatically injected into AI prompts yet.
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
5. Desktop app registry and UI Automation-first control (bounded Notepad typing adapter wired; real Windows verification and general desktop automation remain open).
6. Memory and reminders.
7. GUI/tray, activity feed, and cancellation.
8. Optional voice plugin.
9. Data-preserving packaging and updates.

See [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) for milestones and acceptance criteria.

## Verification policy

Every milestone records what changed, exact checks run, their results, and what remains unverified. Do not describe a feature as working merely because it has been planned or mocked.
