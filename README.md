# JARVIS v3

A Windows-first desktop AI assistant, built incrementally from a clean foundation.

## Project status

**Early prototype — not a finished assistant.** Text chat, provider interfaces, secure credential integration, and a minimal GUI are under active development. Desktop app launching is limited to exact Notepad/Chrome requests with an explicit confirmation dialog. Voice, reminders, memory, general UI automation, installer, and end-to-end Windows verification are not complete.

## Start the GUI

Requirements: Windows, Python 3.12+, and Ollama installed and running with the configured model available. No Python packages are required by this project.

- Clone or download this repository.
- Double-click `Start_JARVIS.pyw` to open the GUI without a console window.
- The default provider is local Ollama with `qwen2.5:7b-instruct-q4_K_M`; obtain the model separately in Ollama before first use.
- Use **Check AI status** for a real generation check.
- Enter exactly `open notepad` or `open chrome` to request an app launch. JARVIS asks for confirmation first. It only reports that Windows accepted the launch request; it does not yet verify that the app became visible.
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
5. Desktop app registry and UI Automation-first control.
6. Memory and reminders.
7. GUI/tray, activity feed, and cancellation.
8. Optional voice plugin.
9. Data-preserving packaging and updates.

See [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) for milestones and acceptance criteria.

## Verification policy

Every milestone records what changed, exact checks run, their results, and what remains unverified. Do not describe a feature as working merely because it has been planned or mocked.
