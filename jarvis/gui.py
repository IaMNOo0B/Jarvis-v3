"""Small no-console Windows chat window with explicitly approved app launching."""

import queue
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from datetime import datetime, timezone

from jarvis.reminders import ReminderStore
from jarvis.memory import MemoryStore
from jarvis.learning import LearningStore
from jarvis.auto_learning import AutomaticLearning
from jarvis.self_healing import RepairLedger
from jarvis.task_planner import TaskPlanner
from jarvis.research import PublicResearch, ResearchError
from jarvis.research_archive import ResearchArchive
from jarvis.activity import ActivityJournal

from jarvis.chat_service import ChatService
from jarvis.knowledge_base import KnowledgeBase
from jarvis.credentials import CredentialStore, CredentialStoreError
from jarvis.desktop_actions import launch_app_with_approval, parse_app_launch_request
from jarvis.health import check_provider
from jarvis.provider_config import ProviderConfig, build_provider


class JarvisWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JARVIS v3")
        self.root.geometry("780x590")
        self.root.minsize(580, 430)
        self.provider_name = "ollama"
        self.provider = build_provider()
        self.service = self._make_service(self.provider)
        self.busy = False
        self.closing = False
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.reminders = ReminderStore()
        self.memory = MemoryStore()
        self.learning = LearningStore()
        self.auto_learning = AutomaticLearning(self.learning)
        self.repairs = RepairLedger()
        self.planner = TaskPlanner()
        self.research = PublicResearch()
        self.research_archive = ResearchArchive()
        self.activity = ActivityJournal()
        self._notified_reminders: set[int] = set()

        shell = ttk.Frame(root, padding=12)
        shell.pack(fill="both", expand=True)
        heading = ttk.Frame(shell)
        heading.pack(fill="x")
        ttk.Label(heading, text="JARVIS v3", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(heading, text="Check AI status", command=self.check_status).pack(side="right")
        provider_row = ttk.Frame(shell)
        provider_row.pack(fill="x", pady=(8, 2))
        ttk.Label(provider_row, text="AI provider:").pack(side="left")
        self.provider_choice = tk.StringVar(value="Local Ollama")
        self.provider_picker = ttk.Combobox(
            provider_row, textvariable=self.provider_choice,
            values=("Local Ollama", "Google Gemini"), state="readonly", width=18,
        )
        self.provider_picker.pack(side="left", padx=(8, 6))
        ttk.Button(provider_row, text="Apply", command=self.apply_provider).pack(side="left")
        ttk.Button(provider_row, text="Save Gemini key…", command=self.save_gemini_key).pack(side="left", padx=(6, 0))
        self.status = tk.StringVar(value="AI status: not checked · Ollama local model")
        ttk.Label(shell, textvariable=self.status).pack(anchor="w", pady=(6, 6))
        self.transcript = scrolledtext.ScrolledText(shell, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.transcript.pack(fill="both", expand=True, pady=(0, 8))
        compose = ttk.Frame(shell)
        compose.pack(fill="x")
        self.entry = ttk.Entry(compose)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send)
        self.send_button = ttk.Button(compose, text="Send", command=self.send)
        self.send_button.pack(side="right")
        ttk.Label(shell, text="Notepad/Chrome launch requires confirmation. No microphone is active.").pack(anchor="w", pady=(8, 0))
        self._append("JARVIS", "Ready. Ask a question or use /help. Try “open Notepad” or “Notepad kholo” to request an approved app launch.")
        self.entry.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(40, self._drain_events)
        self.root.after(1000, self._check_due_reminders)

    def _append(self, speaker: str, message: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{speaker}: {message}\n\n")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _record_activity(self, event: str, status: str, detail: str = "") -> None:
        try:
            self.activity.record(event, status, detail=detail)
        except (OSError, ValueError):
            # Activity logging must never block the requested user operation.
            pass

    def _post_event(self, kind: str, payload: object) -> None:
        # Worker threads only write to a thread-safe queue. Tk calls stay on the UI thread.
        self._events.put((kind, payload))

    def _drain_events(self) -> None:
        if self.closing:
            return
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "response":
                task, response = payload
                self._finish_response(str(task), str(response))
            elif kind == "action":
                success, detail, task = payload
                self._finish_action(bool(success), str(detail), str(task))
            elif kind == "health":
                healthy, detail = payload
                label = "HEALTHY" if healthy else "NOT HEALTHY"
                self._record_activity("provider_health", "healthy" if healthy else "unhealthy", detail)
                self.status.set(f"AI status: {label} · {detail}")
                self.busy = False
                self.send_button.configure(state="normal")
            elif kind == "research":
                success, detail, task = payload
                self._finish_research(bool(success), str(detail), str(task))
        self.root.after(40, self._drain_events)

    def _check_due_reminders(self) -> None:
        if self.closing:
            return
        try:
            for reminder in self.reminders.due():
                if reminder.reminder_id in self._notified_reminders:
                    continue
                # Mark before showing UI so repeated polling cannot duplicate this session notification.
                if self.reminders.mark_fired(reminder.reminder_id):
                    self._notified_reminders.add(reminder.reminder_id)
                    self._record_activity("reminder_due", "notified")
                    self._append("REMINDER", reminder.message)
                    messagebox.showinfo("JARVIS reminder", reminder.message, parent=self.root)
        except Exception:
            self.status.set("Reminder check failed; saved reminders were not deleted.")
        if not self.closing:
            self.root.after(1000, self._check_due_reminders)

    def _handle_reminder_command(self, message: str) -> bool:
        lowered = message.casefold().strip()
        if lowered == "/reminders":
            items = self.reminders.list()
            if not items:
                self._append("JARVIS", "No pending reminders.")
            else:
                lines = [f"#{item.reminder_id} · {item.due_at} · {item.message}" for item in items]
                self._append("JARVIS", "Pending reminders:\\n" + "\\n".join(lines))
            return True
        if lowered.startswith("/cancel-reminder "):
            raw_id = message.strip().split(maxsplit=1)[1]
            if not raw_id.isdigit():
                self._append("JARVIS", "Usage: /cancel-reminder ID")
            elif self.reminders.cancel(int(raw_id)):
                self._record_activity("reminder_cancel", "success")
                self._append("JARVIS", f"Cancelled reminder #{raw_id}.")
            else:
                self._append("JARVIS", f"No pending reminder found with ID {raw_id}.")
            return True
        if lowered.startswith("/remind "):
            payload = message.strip()[len("/remind "):]
            if "|" not in payload:
                self._append("JARVIS", "Usage: /remind YYYY-MM-DDTHH:MM:SS+05:30 | reminder text (time must include timezone)")
                return True
            due_at, content = payload.split("|", 1)
            try:
                reminder = self.reminders.create(due_at.strip(), content)
            except (ValueError, OSError):
                self._append("JARVIS", "Reminder not saved. Check the ISO date/time, timezone offset, and message.")
                return True
            self._record_activity("reminder_create", "success")
            self._append("JARVIS", f"Saved reminder #{reminder.reminder_id} for {reminder.due_at} (UTC).")
            return True
        return False

    def _handle_memory_command(self, message: str) -> bool:
        stripped = message.strip()
        lowered = stripped.casefold()
        if lowered.startswith("/remember "):
            content = stripped[len("/remember "):].strip()
            try:
                item = self.memory.remember(content, source="explicit_user_command")
            except ValueError:
                self._append("JARVIS", "Memory not saved. Use /remember followed by 1–4000 characters.")
                return True
            self._record_activity("memory_save", "success")
            self._append("JARVIS", f"Saved memory #{item.memory_id}. Use /memories to list it or /forget ID to delete it.")
            return True
        if lowered == "/memories":
            items = self.memory.list()
            if not items:
                self._append("JARVIS", "No saved memories.")
            else:
                lines = [f"#{item.memory_id} · {item.content} (source: {item.source})" for item in items]
                self._append("JARVIS", "Saved memories:\\n" + "\\n".join(lines))
            return True
        if lowered.startswith("/forget "):
            raw_id = stripped.split(maxsplit=1)[1]
            if not raw_id.isdigit():
                self._append("JARVIS", "Usage: /forget ID")
                return True
            if not messagebox.askyesno("Forget memory", f"Permanently delete saved memory #{raw_id}?", parent=self.root):
                self._append("JARVIS", "Cancelled. Memory was kept.")
            elif self.memory.forget(int(raw_id)):
                self._record_activity("memory_forget", "success")
                self._append("JARVIS", f"Forgot memory #{raw_id}.")
            else:
                self._append("JARVIS", f"Memory #{raw_id} was not found.")
            return True
        if lowered == "/forget-all":
            if not messagebox.askyesno("Forget all memories", "Permanently delete ALL saved JARVIS memories?", parent=self.root):
                self._append("JARVIS", "Cancelled. Memories were kept.")
            else:
                count = self.memory.forget_all(confirmed=True)
                self._record_activity("memory_forget_all", "success", f"count={count}")
                self._append("JARVIS", f"Forgot {count} saved memories.")
            return True
        return False

    def _handle_research_history_command(self, message: str) -> bool:
        if message.strip().casefold() != "/research-history":
            return False
        try:
            runs = self.research_archive.recent(limit=10)
        except (OSError, ValueError):
            self._append("JARVIS", "Research history could not be read; no records were deleted.")
            return True
        if not runs:
            self._append("JARVIS", "No archived research yet.")
            return True
        lines = []
        for run in runs:
            lines.append(f"#{run['id']} · {run['saved_at']} · {run['query']}")
            for source in run["sources"]:
                lines.append(f"  - {source['title']}: {source['url']}")
            if run["warnings"]:
                lines.append(f"  Limitations: {run['warnings']}")
        self._append("JARVIS", "Recent archived research (source links preserved):\n" + "\n".join(lines))
        return True

    def _handle_learning_command(self, message: str) -> bool:
        stripped = message.strip()
        lowered = stripped.casefold()
        if lowered.startswith("/experience "):
            payload = stripped[len("/experience "):]
            parts = [part.strip() for part in payload.split("|", 2)]
            if len(parts) < 2:
                self._append("JARVIS", "Usage: /experience task | outcome | optional evidence")
                return True
            try:
                episode = self.learning.record_episode(parts[0], parts[1], evidence=parts[2] if len(parts) == 3 else "")
            except ValueError:
                self._append("JARVIS", "Experience not saved. Check task, outcome, and evidence lengths.")
                return True
            self._record_activity("learning_episode", "saved", f"id={episode.episode_id}")
            self._append("JARVIS", f"Recorded experience #{episode.episode_id}. This records an outcome; it does not prove the task succeeded beyond the evidence provided.")
            return True
        if lowered.startswith("/learn "):
            payload = stripped[len("/learn "):]
            if "|" not in payload:
                self._append("JARVIS", "Usage: /learn exact trigger | reusable instructions")
                return True
            trigger, instructions = payload.split("|", 1)
            try:
                skill = self.learning.propose_skill(trigger, instructions)
            except ValueError:
                self._append("JARVIS", "Skill proposal not saved. Check that trigger and instructions are non-empty and within limits.")
                return True
            self._record_activity("skill_proposal", "pending", f"id={skill.skill_id}")
            self._append("JARVIS", f"Saved skill proposal #{skill.skill_id} as PENDING. It will not run until you review and approve it with /approve-skill {skill.skill_id}.")
            return True
        if lowered == "/skills":
            skills = self.learning.list_skills(limit=30)
            if not skills:
                self._append("JARVIS", "No learned skill proposals yet.")
            else:
                lines = [f"#{item.skill_id} [{item.status.upper()}] {item.trigger} — {item.instructions}" for item in skills]
                self._append("JARVIS", "Skill proposals (text only; no code is auto-executed):\n" + "\n".join(lines))
            return True
        if lowered.startswith("/approve-skill ") or lowered.startswith("/reject-skill "):
            approve = lowered.startswith("/approve-skill ")
            raw_id = stripped.split(maxsplit=1)[1]
            if not raw_id.isdigit():
                self._append("JARVIS", "Usage: /approve-skill ID or /reject-skill ID")
                return True
            skill_id = int(raw_id)
            if approve and not messagebox.askyesno("Approve learned skill", f"Approve skill proposal #{skill_id}? Review its trigger and instructions in /skills first. Approval stores the procedure; it does not grant desktop permissions.", parent=self.root):
                self._append("JARVIS", "Cancelled. Skill remains unchanged.")
                return True
            try:
                item = self.learning.review_skill(skill_id, approve=approve)
            except ValueError as exc:
                self._append("JARVIS", f"Could not review skill: {exc}")
                return True
            status = "approved" if approve else "rejected"
            self._record_activity("skill_review", status, f"id={skill_id}")
            self._append("JARVIS", f"Skill proposal #{skill_id} marked {status.upper()}. Learned procedures do not bypass action safety checks.")
            return True
        if lowered == "/experiences":
            episodes = self.learning.recent_episodes(limit=20)
            if not episodes:
                self._append("JARVIS", "No recorded experiences yet.")
            else:
                lines = [f"#{item.episode_id} · {item.task} → {item.outcome}" + (f" (evidence: {item.evidence})" if item.evidence else "") for item in episodes]
                self._append("JARVIS", "Recent experiences:\n" + "\n".join(lines))
            return True
        return False

    def _set_provider(self, name: str) -> None:
        credentials = CredentialStore() if name == "gemini" else None
        provider = build_provider(ProviderConfig(name=name), credentials=credentials)
        self.provider = provider
        self.service = self._make_service(provider)
        self.provider_name = name
        self._record_activity("provider_select", "selected", name)
        self.status.set(f"Provider selected: {'Google Gemini' if name == 'gemini' else 'Local Ollama'} · run Check AI status to test")

    def _make_service(self, provider):
        project_root = Path(__file__).resolve().parent.parent
        roots = [project_root / "docs", project_root / "knowledge"]
        return ChatService(provider, KnowledgeBase(roots))

    def apply_provider(self) -> None:
        if self.busy or self.closing:
            self.status.set("AI status: wait for the current request before changing provider")
            return
        name = "gemini" if self.provider_choice.get() == "Google Gemini" else "ollama"
        try:
            self._set_provider(name)
        except (ValueError, CredentialStoreError, OSError):
            self.provider_choice.set("Local Ollama" if self.provider_name == "ollama" else "Google Gemini")
            if name == "gemini":
                messagebox.showerror(
                    "Gemini is not ready",
                    "No Gemini key was loaded from Windows Credential Manager. Save a key first, then apply Gemini again.",
                    parent=self.root,
                )
            else:
                messagebox.showerror("Provider unavailable", "JARVIS could not configure that provider.", parent=self.root)

    def save_gemini_key(self) -> None:
        if self.busy or self.closing:
            self.status.set("AI status: wait for the current request before changing credentials")
            return
        try:
            store = CredentialStore()
        except (CredentialStoreError, OSError):
            messagebox.showerror("Secure storage unavailable", "JARVIS could not access Windows Credential Manager. No key was saved.", parent=self.root)
            return
        key = simpledialog.askstring(
            "Save Gemini API key",
            "Enter your Gemini API key. It will be stored in Windows Credential Manager, not in a file.",
            show="*",
            parent=self.root,
        )
        if key is None:
            return
        key = key.strip()
        if not ((key.startswith("AQ.") and len(key) >= 40) or (key.startswith("AIza") and len(key) >= 30)):
            messagebox.showerror("Key format not recognized", "Expected a Gemini key beginning with AQ. or AIza. The key was not saved.", parent=self.root)
            return
        try:
            store.set_secret("gemini.api_key", key)
        except (ValueError, CredentialStoreError, OSError):
            messagebox.showerror("Save failed", "Windows Credential Manager could not save the key. The key was not displayed or written to a file.", parent=self.root)
            return
        # Drop this local reference; never echo or log the credential.
        key = ""
        messagebox.showinfo("Key saved", "Gemini key saved in Windows Credential Manager. Select Google Gemini and press Apply to use it.", parent=self.root)

    def send(self, event=None) -> None:
        if self.busy or self.closing:
            return
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, "end")
        self._append("Sir", message)
        if self._handle_reminder_command(message):
            return
        if self._handle_memory_command(message):
            return
        if self._handle_learning_command(message):
            return
        if self._handle_research_history_command(message):
            return
        plan = self.planner.plan(message)
        self._record_activity("task_plan", plan.intent, f"steps={len(plan.steps)}")
        if plan.intent == "invalid_research":
            self._append("JARVIS", "Research request incomplete. Example: 'research Wikipedia artificial intelligence' or 'research GitHub agent framework'.")
            return
        if plan.intent in {"research_wikipedia", "research_github"}:
            prefix_map = {
                "research_wikipedia": ("research wikipedia ", "wiki research ", "wikipedia par research "),
                "research_github": ("research github ", "github research ", "github par research "),
            }
            lowered = message.casefold().strip()
            prefix = next(p for p in prefix_map[plan.intent] if lowered.startswith(p))
            query = message.strip()[len(prefix):].strip()
            source = "wikipedia" if plan.intent == "research_wikipedia" else "github"
            self.busy = True
            self.send_button.configure(state="disabled")
            self.status.set(f"Research: searching public {source.title()} metadata…")

            def research_work():
                try:
                    report = self.research.search(source, query)
                    try:
                        run_id = self.research_archive.save(report)
                        self._record_activity("research_archive", "saved", f"run_id={run_id}")
                    except (OSError, ValueError):
                        self._record_activity("research_archive", "failed", "research results remain visible but were not archived")
                    lines = [f"Research query: {report.query}", ""]
                    if not report.sources:
                        lines.append("No results were returned by the source.")
                    for index, item in enumerate(report.sources, 1):
                        lines.append(f"{index}. {item.title}")
                        lines.append(item.snippet or "No description/snippet supplied.")
                        lines.append(item.url)
                        lines.append("")
                    if report.warnings:
                        lines.append("Limitations:")
                        lines.extend(f"- {warning}" for warning in report.warnings)
                    self._post_event("research", (True, "\\n".join(lines), message))
                except (ResearchError, ValueError):
                    self._post_event("research", (False, "Public research failed or was unavailable. No result was fabricated.", message))
                except Exception:
                    self._post_event("research", (False, "Unexpected research error. No result was fabricated.", message))

            threading.Thread(target=research_work, daemon=True).start()
            return

        app_name = parse_app_launch_request(message)
        if app_name:
            approved = messagebox.askyesno(
                "Approve app launch",
                f"Allow JARVIS to launch {app_name.title()} on this PC?",
                parent=self.root,
            )
            if not approved:
                self._append("JARVIS", "Cancelled. No app was launched.")
                return
            self.busy = True
            self.send_button.configure(state="disabled")
            self.status.set(f"Action: launching {app_name.title()}…")

            def launch():
                try:
                    result = launch_app_with_approval(app_name, user_approved=True)
                    event = (result.success, result.detail)
                except Exception:
                    event = (False, "Unexpected launch error. No further action was taken.")
                self._post_event("action", (event[0], event[1], message))

            threading.Thread(target=launch, daemon=True).start()
            return

        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.set(f"AI status: generating with {self.provider_name}…")

        def work():
            try:
                response = self.service.respond(message, timeout_seconds=120.0)
            except Exception:
                response = "An unexpected error occurred; no desktop action was performed."
            # The UI event handler expects both the original task and its response.
            self._post_event("response", (message, response))

        threading.Thread(target=work, daemon=True).start()

    def _finish_action(self, success: bool, detail: str, task: str) -> None:
        if self.closing:
            return
        self._record_activity("desktop_launch", "accepted" if success else "failed")
        try:
            reflection = self.auto_learning.reflect(task, outcome="action_accepted" if success else "action_failed", evidence=detail)
            self._record_activity("automatic_reflection", reflection.outcome, f"episode={reflection.episode.episode_id}")
        except (ValueError, OSError):
            self._record_activity("automatic_reflection", "failed", "action result was not recorded")
        self._append("JARVIS", detail)
        self.busy = False
        self.send_button.configure(state="normal")
        self.status.set("Action: launch request accepted" if success else "Action: not completed")
        self.entry.focus_set()

    def _finish_response(self, task: str, response: str) -> None:
        if self.closing:
            return
        failure = response.startswith(("The AI provider failed;", "The AI provider returned an empty response;", "An unexpected error occurred;"))
        try:
            reflection = self.auto_learning.reflect(task, outcome="provider_failed" if failure else "response_generated")
            self._record_activity("automatic_reflection", reflection.outcome, f"episode={reflection.episode.episode_id}")
        except (ValueError, OSError):
            self._record_activity("automatic_reflection", "failed", "response outcome was not recorded")
        if failure:
            # Turn a known failure into a reviewable diagnosis task, never an auto-applied patch.
            try:
                repair = self.repairs.propose(
                    failure_summary="AI provider request failed or returned no usable text.",
                    proposed_change=(
                        "Inspect provider selection, local service availability, timeout, and response parsing. "
                        "Reproduce with a fake provider first; add a regression test before proposing a code patch. "
                        "Do not retry indefinitely or change provider/security settings automatically."
                    ),
                    source_ref="gui-provider-failure",
                )
                self._record_activity("repair_proposal", "proposed", f"id={repair.repair_id}")
            except (ValueError, OSError):
                self._record_activity("repair_proposal", "not_saved", "failure diagnosis proposal could not be stored")
        self._append("JARVIS", response)
        self.busy = False
        self.send_button.configure(state="normal")
        self.status.set(f"AI status: response finished · {self.provider_name}")
        self.entry.focus_set()

    def _finish_research(self, success: bool, detail: str, task: str) -> None:
        if self.closing:
            return
        outcome = "response_generated" if success else "provider_failed"
        try:
            reflection = self.auto_learning.reflect(task, outcome=outcome, evidence="Public-source lookup completed." if success else "Research source unavailable.")
            self._record_activity("automatic_reflection", reflection.outcome, f"episode={reflection.episode.episode_id}")
        except (ValueError, OSError):
            self._record_activity("automatic_reflection", "failed", "research outcome was not recorded")
        self._record_activity("public_research", "success" if success else "failed")
        self._append("JARVIS", detail)
        self.busy = False
        self.send_button.configure(state="normal")
        self.status.set("Research: finished" if success else "Research: unavailable")
        self.entry.focus_set()

    def check_status(self) -> None:
        if self.busy or self.closing:
            self.status.set("AI status: busy; wait for the current request")
            return
        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.set("AI status: testing with a real generation request…")
        provider = self.provider

        def work():
            try:
                result = check_provider(provider, timeout_seconds=15.0)
                payload = (result.healthy, result.detail)
            except Exception:
                payload = (False, "Provider health check failed unexpectedly.")
            self._post_event("health", payload)

        threading.Thread(target=work, daemon=True).start()

    def close(self) -> None:
        self.closing = True
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        JarvisWindow(root)
    except Exception as exc:
        root.withdraw()
        messagebox.showerror("JARVIS could not start", f"Startup failed ({type(exc).__name__}). Check that Ollama is installed and running.")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
