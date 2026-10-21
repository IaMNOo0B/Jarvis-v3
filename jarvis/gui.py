"""Small no-console Windows chat window with explicitly approved app launching."""

import queue
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from datetime import datetime, timezone

from jarvis.reminders import ReminderStore, parse_natural_reminder
from jarvis.memory import MemoryStore, is_sensitive_memory_request, parse_natural_remember_request
from jarvis.learning import LearningStore
from jarvis.auto_learning import AutomaticLearning
from jarvis.self_healing import RepairLedger, should_propose_desktop_repair
from jarvis.task_planner import TaskPlanner, extract_research_query
from jarvis.task_runtime import action_event_for_runtime, execute_plan
from jarvis.capabilities import build_capability_registry
from jarvis.research import PublicResearch, ResearchError, ResearchReport
from jarvis.research_archive import ResearchArchive
from jarvis.activity import ActivityJournal
from jarvis.task_receipts import TaskReceiptStore
from jarvis.cancellation import CancellationToken, OperationCancelled
from jarvis.source_inspection import inspect_source_tree, trace_symbol

from jarvis.chat_service import ChatService
from jarvis.knowledge_base import KnowledgeBase
from jarvis.credentials import CredentialStore, CredentialStoreError
from jarvis.desktop_actions import parse_app_launch_batch, parse_app_launch_request
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
        self.current_cancellation: CancellationToken | None = None
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.reminders = ReminderStore()
        self.memory = MemoryStore()
        self.learning = LearningStore()
        self.auto_learning = AutomaticLearning(self.learning)
        self.repairs = RepairLedger()
        self.planner = TaskPlanner()
        self.research = PublicResearch()
        self.capability_registry = build_capability_registry(self.research)
        self.research_archive = ResearchArchive()
        self.activity = ActivityJournal()
        self.task_receipts = TaskReceiptStore()
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
        self.stop_button = ttk.Button(compose, text="Stop", command=self.stop_current, state="disabled")
        self.stop_button.pack(side="right", padx=(0, 6))
        self.send_button = ttk.Button(compose, text="Send", command=self.send)
        self.send_button.pack(side="right")
        self.root.bind("<Escape>", self._escape_stop)
        ttk.Label(shell, text="Stop / Esc cancels at safe boundaries. Desktop actions are limited to explicit allow-listed requests. No microphone is active.").pack(anchor="w", pady=(8, 0))
        self._append("JARVIS", "Ready. Ask a question or use /help. Try “open Notepad”, “open Notepad and Calculator”, or “open Notepad and type Hello Sir”.")
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

    def _record_runtime_steps(self, task: str, steps) -> None:
        """Persist per-step outcomes without upgrading attempts to verified success."""
        status_map = {
            "verified": "verified",
            "attempted": "attempted",
            "failed": "failed",
            "partial": "partial",
            "blocked": "blocked",
            "cancelled": "cancelled",
            "unknown": "unknown",
            "skipped": "skipped",
            "approval_required": "blocked",
            "invalid_result": "failed",
        }
        for step in steps:
            label = f"{step.name}: {step.target}" if step.target else step.name
            evidence = step.detail
            if step.evidence and step.evidence != "none":
                evidence = f"{evidence} | evidence: {step.evidence}"
            try:
                self.task_receipts.record_step(
                    task, label[:200], status_map.get(step.status, "failed"), evidence=evidence[:4000],
                )
            except (ValueError, OSError):
                self._record_activity("task_step_receipt", "not_saved", f"step {label[:100]} remains visible in the final task result")

    def _begin_work(self) -> CancellationToken:
        token = CancellationToken()
        self.current_cancellation = token
        self.busy = True
        self.send_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        return token

    def _finish_work_controls(self) -> None:
        self.busy = False
        self.current_cancellation = None
        self.send_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.entry.focus_set()

    def stop_current(self) -> None:
        token = self.current_cancellation
        if token is None or token.cancelled:
            return
        token.cancel()
        self.stop_button.configure(state="disabled")
        self.status.set("Stop requested; an in-flight provider/network call may continue until its timeout. Its result will be discarded.")
        self._record_activity("task_cancel", "requested")

    def _escape_stop(self, event=None) -> None:
        self.stop_current()

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
            if kind == "cancelled":
                task = str(payload)
                self._append("JARVIS", f"Stopped task: {task}. An in-flight call may have continued until timeout; its result was discarded.")
                self._record_activity("task_cancel", "observed_at_safe_boundary")
                self.status.set("Task cancelled at a safe boundary.")
                self._finish_work_controls()
            elif kind == "response":
                task, response = payload
                self._finish_response(str(task), str(response))
            elif kind == "action":
                outcome, detail, task = payload
                self._finish_action(str(outcome), str(detail), str(task))
            elif kind == "health":
                healthy, detail = payload
                label = "HEALTHY" if healthy else "NOT HEALTHY"
                self._record_activity("provider_health", "healthy" if healthy else "unhealthy", detail)
                self.status.set(f"AI status: {label} · {detail}")
                self._finish_work_controls()
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
        natural_prefixes = (
            "remind me in ", "please remind me in ", "jarvis remind me in ",
            "jarvis, remind me in ", "remind me at ", "remind me today ",
            "remind me tomorrow ", "please remind me at ", "please remind me today ",
            "please remind me tomorrow ", "jarvis remind me at ", "jarvis, remind me at ",
            "jarvis remind me today ", "jarvis, remind me today ",
            "jarvis remind me tomorrow ", "jarvis, remind me tomorrow ",
        )
        natural_relative_tail = (
            lowered.startswith(("remind me to ", "please remind me to ", "jarvis remind me to ", "jarvis, remind me to "))
            and any(unit in lowered for unit in (" in minute", " in min", " in hour", " in hr", " in day"))
        )
        if lowered.startswith(natural_prefixes) or natural_relative_tail:
            parsed = parse_natural_reminder(message)
            if parsed is None:
                self._append("JARVIS", "I couldn't safely determine that reminder time, so nothing was saved. Say, for example, 'Remind me in 20 minutes to study', 'Remind me tomorrow at 8:30 PM to study', or use /remind with a full ISO time and timezone.")
                return True
            due_at, content = parsed
            try:
                reminder = self.reminders.create(due_at, content)
            except (ValueError, OSError):
                self._append("JARVIS", "Reminder not saved. Check that the time is valid and the message is not too long.")
                return True
            local_due = datetime.fromisoformat(due_at).strftime("%a %d %b %Y, %I:%M %p %Z").strip()
            self._record_activity("reminder_create", "success", f"id={reminder.reminder_id}")
            self._append("JARVIS", f"Saved reminder #{reminder.reminder_id} for {local_due} in your PC's local time. JARVIS can notify you while its window stays open.")
            return True
        if lowered == "/reminders":
            items = self.reminders.list()
            if not items:
                self._append("JARVIS", "No pending reminders.")
            else:
                lines = [f"#{item.reminder_id} · {item.due_at} · {item.message}" for item in items]
                self._append("JARVIS", "Pending reminders:\n" + "\n".join(lines))
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

        natural_content = parse_natural_remember_request(stripped)
        if natural_content is not None:
            if is_sensitive_memory_request(natural_content):
                self._append("JARVIS", "I won't save passwords, API keys, tokens, passcodes, or recovery codes as memory. No memory was created.")
                return True
            try:
                item = self.memory.remember(natural_content, source="explicit_user_request")
            except ValueError:
                self._append("JARVIS", "Memory not saved. Keep it between 1 and 4000 characters.")
                return True
            self._record_activity("memory_save", "success", f"id={item.memory_id}")
            self._append("JARVIS", f"Remembered: {item.content} (memory #{item.memory_id}). I only save a memory when you explicitly ask.")
            return True

        if lowered in {"what do you remember?", "what do you remember about me?", "show my memories", "what have you remembered?"}:
            items = self.memory.list()
            if not items:
                self._append("JARVIS", "I have no saved memories.")
            else:
                lines = [f"#{item.memory_id} · {item.content} (source: {item.source})" for item in items]
                self._append("JARVIS", "Saved memories:\n" + "\n".join(lines))
            return True

        if lowered in {"forget all my memories", "forget everything you remember about me", "delete all memories"}:
            if not messagebox.askyesno("Forget all memories", "Permanently delete ALL saved JARVIS memories?", parent=self.root):
                self._append("JARVIS", "Cancelled. Memories were kept.")
            else:
                count = self.memory.forget_all(confirmed=True)
                self._record_activity("memory_forget_all", "success", f"count={count}")
                self._append("JARVIS", f"Forgot {count} saved memories.")
            return True

        forget_prefix = "please forget that " if lowered.startswith("please forget that ") else "forget that " if lowered.startswith("forget that ") else None
        if forget_prefix:
            target = stripped[len(forget_prefix):].strip().casefold()
            matches = [item for item in self.memory.list() if target and target in item.content.casefold()]
            if len(matches) == 1:
                item = matches[0]
                if messagebox.askyesno("Forget memory", f"Permanently delete memory #{item.memory_id}: {item.content}?", parent=self.root):
                    self.memory.forget(item.memory_id)
                    self._record_activity("memory_forget", "success", f"id={item.memory_id}")
                    self._append("JARVIS", f"Forgot memory #{item.memory_id}.")
                else:
                    self._append("JARVIS", "Cancelled. Memory was kept.")
            elif len(matches) > 1:
                self._append("JARVIS", "More than one memory matches. No data was deleted:\n" + "\n".join(f"#{item.memory_id} · {item.content}" for item in matches) + "\nPlease identify the memory number.")
            else:
                self._append("JARVIS", "No saved memory matched that wording; nothing was deleted.")
            return True

        if lowered.startswith("/remember "):
            content = stripped[len("/remember "):].strip()
            if is_sensitive_memory_request(content):
                self._append("JARVIS", "I won't save passwords, API keys, tokens, passcodes, or recovery codes as memory. No memory was created.")
                return True
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
                self._append("JARVIS", "Saved memories:\n" + "\n".join(lines))
            return True
        if lowered.startswith("/forget ") or lowered.startswith("forget memory "):
            raw_id = stripped.split()[-1]
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

    def _handle_help_command(self, message: str) -> bool:
        if message.strip().casefold() != "/help":
            return False
        self._append("JARVIS", "Supported features and commands:\n- Normal messages: chat with the selected provider\n- Open allow-listed apps by name; chain up to five with 'and' for sequential launch. Use 'open Notepad and type Hello Sir' or 'type Hello Sir in Notepad' to enter text only into a detected blank Notepad document and verify exact read-back\n- Find/research/look up a topic: bounded public Wikipedia search; mention GitHub to search repository metadata\n- Open an explicit HTTP(S) URL in Chrome by default or Edge with 'open https://example.com in Edge'; only the supplied URL is opened, and page load/content are not verified\n- /tasks: recent task receipts\n- /clear-tasks: delete task receipts after confirmation\n- /research-history: recent archived research\n- Natural reminders: 'Remind me in 20 minutes to study' or 'Remind me tomorrow at 8:30 PM to study'; /remind TIME | MESSAGE, /reminders, /cancel-reminder ID\n- Natural memory: 'Remember that I prefer concise answers', 'What do you remember about me?', or 'Forget that I prefer concise answers' (deletion is confirmed); /remember TEXT, /memories, /forget ID, /forget-all\n- /experiences, /skills, /learn TRIGGER | INSTRUCTIONS, /approve-skill ID, /reject-skill ID\n- /repairs: inspect recent reviewable diagnostic proposals; nothing is auto-applied\n- /inspect-source [symbol]: inspect JARVIS Python source statically and trace exact symbol definitions/call sites without executing code\n- Check AI status: performs a real provider generation check\nSupported actions: allow-listed app launches, bounded multi-app sequences, explicit HTTP(S) URL opening, public research, and Notepad text entry into a detected blank document with exact read-back when Windows UI Automation is available. URL navigation only asks the browser to open the supplied address; it does not click, download or submit forms, and page load is unverified. The Notepad typing path requires Windows PowerShell and UI Automation; it has not had a real-Windows smoke test. Existing text is not replaced. Arbitrary-window typing, browser automation and broad desktop automation remain unsupported. Stop cannot forcibly interrupt an in-flight provider/network call; research is not independent fact verification; voice is not implemented.")
        return True

    def _handle_repair_command(self, message: str) -> bool:
        if message.strip().casefold() != "/repairs":
            return False
        try:
            items = self.repairs.list_proposals(limit=10)
        except Exception:
            self._append("JARVIS", "Repair proposals could not be read. No code was changed.")
            return True
        if not items:
            self._append("JARVIS", "No repair proposals are saved.")
            return True
        lines = ["Recent repair proposals (review only; nothing is auto-applied):"]
        for item in items:
            lines.append(f"#{item.repair_id} [{item.status.upper()}] · {item.created_at}")
            lines.append(f"  Issue: {item.failure_summary[:400]}")
            lines.append(f"  Proposed review: {item.proposed_change[:800]}")
            lines.append(f"  Reference: {item.source_ref}")
        self._append("JARVIS", "\n".join(lines))
        return True

    def _handle_task_history_command(self, message: str) -> bool:
        lowered = message.strip().casefold()
        if lowered == "/clear-tasks":
            if not messagebox.askyesno("Clear task history", "Permanently delete all saved task receipts? This does not delete memories or research history.", parent=self.root):
                self._append("JARVIS", "Cancelled. Task receipts were kept.")
                return True
            try:
                count = self.task_receipts.clear()
            except (OSError, ValueError):
                self._append("JARVIS", "Task history could not be cleared; no other data was changed.")
                return True
            self._record_activity("task_receipts_clear", "success", f"count={count}")
            self._append("JARVIS", f"Deleted {count} task receipts. Memories and research history were not changed.")
            return True
        if lowered != "/tasks":
            return False
        try:
            items = self.task_receipts.recent(limit=10)
        except (OSError, ValueError):
            self._append("JARVIS", "Task history could not be read; no records were deleted.")
            return True
        if not items:
            self._append("JARVIS", "No task receipts recorded yet.")
            return True
        labels = {
            "response_generated": "response generated; goal completion unverified",
            "action_accepted": "OS accepted action; final state unverified",
            "action_failed": "action failed",
            "action_partial": "partially completed; check state before retrying",
            "action_verified": "action completed with verified postcondition",
            "action_unknown": "outcome unknown; check before retrying",
            "provider_failed": "provider failed",
            "research_succeeded": "public-source lookup returned results",
            "research_failed": "public-source lookup failed",
        }
        lines = [f"#{item['id']} · {item['created_at']} · {labels.get(item['outcome'], item['outcome'])} · {item['task']}" for item in items]
        try:
            steps = self.task_receipts.recent_steps(limit=10)
        except (OSError, ValueError):
            steps = []
        if steps:
            lines.append("")
            lines.append("Recent execution steps (not goal-success claims):")
            lines.extend(f"  - {item['created_at']} · {item['step']} · {item['outcome']} · {item['evidence']}" for item in steps)
        self._append("JARVIS", "Recent task receipts (observed outcome, not assumed success):\n" + "\n".join(lines))
        return True

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

    def _handle_source_inspection_command(self, message: str) -> bool:
        stripped = message.strip()
        lowered = stripped.casefold()
        if lowered != "/inspect-source" and not lowered.startswith("/inspect-source "):
            return False
        parts = stripped.split(maxsplit=1)
        symbol = parts[1].strip() if len(parts) == 2 else ""
        if symbol.startswith("/") or "\\" in symbol or len(symbol) > 200:
            self._append("JARVIS", "Usage: /inspect-source [symbol name]. The inspection root is fixed to the JARVIS project; arbitrary paths are not accepted.")
            return True
        project_root = Path(__file__).resolve().parent.parent
        try:
            report = inspect_source_tree(project_root)
            if symbol:
                traced = trace_symbol(report, symbol)
                definitions = traced["definitions"]
                callers = traced["callers"]
                lines = [f"Static source trace for '{symbol}' (not proof of runtime behavior):"]
                if definitions:
                    lines.append("Definitions:")
                    lines.extend(f"  - {item.qualified_name} · {item.path}:{item.line}" for item in definitions[:10])
                else:
                    lines.append("No exact definition found.")
                if callers:
                    lines.append("Statically named call sites:")
                    lines.extend(f"  - {item.caller} calls {item.callee} · {item.path}:{item.line}" for item in callers[:10])
                else:
                    lines.append("No statically named call sites found.")
                if len(definitions) > 10 or len(callers) > 10:
                    lines.append("Output capped at 10 definitions and 10 call sites.")
            else:
                parsed = sum(1 for item in report.files if item.parsed)
                lines = [
                    "JARVIS source inspection (static evidence only; inspected code was not executed):",
                    f"Python files: {len(report.files)} total, {parsed} parsed, {len(report.files) - parsed} skipped/unparsed.",
                    f"Definitions: {len(report.symbols)} · imports: {len(report.imports)} · static call sites: {len(report.calls)}.",
                    "Use /inspect-source SYMBOL to find exact definitions and statically named callers.",
                ]
            if report.warnings:
                lines.append(f"Warnings/unknowns: {len(report.warnings)} (some files may be unreadable, oversized, or syntactically invalid).")
                lines.extend(f"  - {warning}" for warning in report.warnings[:5])
            self._record_activity("source_inspection", "completed", f"files={len(report.files)}; symbol_query={'yes' if symbol else 'no'}")
            self._append("JARVIS", "\n".join(lines))
        except (OSError, ValueError):
            self._append("JARVIS", "Source inspection failed. No source files were modified or executed.")
        return True

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
        if self._handle_help_command(message):
            return
        if self._handle_reminder_command(message):
            return
        if self._handle_memory_command(message):
            return
        if self._handle_learning_command(message):
            return
        if self._handle_repair_command(message):
            return
        if self._handle_research_history_command(message):
            return
        if self._handle_source_inspection_command(message):
            return
        if self._handle_task_history_command(message):
            return
        plan = self.planner.plan(message)
        self._record_activity("task_plan", plan.intent, f"steps={len(plan.steps)}")
        if plan.intent == "invalid_research":
            self._append("JARVIS", "Research request incomplete. Example: 'research Wikipedia artificial intelligence' or 'research GitHub agent framework'.")
            return
        if plan.intent == "open_url":
            # URLs can contain temporary tokens or other private query data; keep
            # the destination out of durable task/learning receipts.
            history_task = "Browser navigation request (URL omitted)"
            try:
                self.task_receipts.record_step(
                    history_task, "browser navigation", "started",
                    evidence="Explicit request to open one supplied HTTP(S) URL in an allow-listed browser.",
                )
            except (ValueError, OSError):
                self._record_activity("task_step_receipt", "not_saved", "Browser request still proceeds; started receipt could not be stored")
            token = self._begin_work()
            self.status.set("Action: opening supplied URL in browser…")

            def url_open_work():
                try:
                    token.raise_if_cancelled()
                    runtime = execute_plan(
                        plan,
                        registry=self.capability_registry,
                        approved=True,
                        cancellation=token,
                    )
                    self._record_runtime_steps(history_task, runtime.step_results)
                    event = action_event_for_runtime(runtime)
                    if event[0] == "cancelled":
                        self._post_event("cancelled", history_task)
                        return
                except OperationCancelled:
                    self._post_event("cancelled", history_task)
                    return
                except Exception:
                    event = ("action_failed", "Unexpected browser navigation error. No further action was taken.")
                self._post_event("action", (event[0], event[1], history_task))

            threading.Thread(target=url_open_work, daemon=True).start()
            return
        if plan.intent == "notepad_type_text":
            # Text supplied for typing may be private. Keep the request's content
            # out of durable task/learning receipts; the live GUI transcript is in-memory.
            history_task = "Notepad text-entry request (content omitted)"
            try:
                self.task_receipts.record_step(
                    history_task, "Notepad text workflow", "started",
                    evidence="Explicit request to enter text into a blank Notepad document.",
                )
            except (ValueError, OSError):
                self._record_activity("task_step_receipt", "not_saved", "Notepad workflow still proceeds; started receipt could not be stored")
            token = self._begin_work()
            self.status.set("Action: opening Notepad and verifying typed text…")

            def notepad_type_work():
                runtime = None
                try:
                    token.raise_if_cancelled()
                    runtime = execute_plan(
                        plan,
                        registry=self.capability_registry,
                        approved=True,
                        cancellation=token,
                    )
                    self._record_runtime_steps(history_task, runtime.step_results)
                    event = action_event_for_runtime(runtime)
                    if event[0] == "cancelled":
                        self._post_event("cancelled", history_task)
                        return
                except OperationCancelled:
                    self._post_event("cancelled", history_task)
                    return
                except Exception:
                    event = ("action_failed", "Unexpected Notepad automation error. Inspect the desktop before retrying.")
                self._post_event("action", (event[0], event[1], history_task))

            threading.Thread(target=notepad_type_work, daemon=True).start()
            return
        if plan.intent in {"research_wikipedia", "research_github"}:
            query = extract_research_query(message, plan.intent)
            if not query:
                self._append("JARVIS", "I recognized a lookup request but could not safely extract its topic. Please rephrase the topic; no network request was made.")
                return
            source = "wikipedia" if plan.intent == "research_wikipedia" else "github"
            try:
                self.task_receipts.record_step(message, f"public {source.title()} lookup", "started", evidence="Explicit user-requested public lookup.")
            except (ValueError, OSError):
                self._record_activity("task_step_receipt", "not_saved", "research still proceeds; step receipt could not be stored")
            token = self._begin_work()
            self.status.set(f"Research: searching public {source.title()} metadata…")

            def research_work():
                try:
                    token.raise_if_cancelled()
                    runtime = execute_plan(
                        plan,
                        registry=self.capability_registry,
                        arguments={"query": query},
                    )
                    outcome = runtime.capability_result
                    if runtime.status != "verified" or outcome is None or not isinstance(outcome.value, ResearchReport):
                        raise ResearchError("Registered research capability did not return a usable report.")
                    report = outcome.value
                    token.raise_if_cancelled()
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
                    self._post_event("research", (True, "\n".join(lines), message))
                except OperationCancelled:
                    self._post_event("cancelled", message)
                except (ResearchError, ValueError):
                    if token.cancelled:
                        self._post_event("cancelled", message)
                    else:
                        self._post_event("research", (False, "Public research failed or was unavailable. No result was fabricated.", message))
                except Exception:
                    if token.cancelled:
                        self._post_event("cancelled", message)
                    else:
                        self._post_event("research", (False, "Unexpected research error. No result was fabricated.", message))

            threading.Thread(target=research_work, daemon=True).start()
            return

        app_name = parse_app_launch_request(message)
        app_names = parse_app_launch_batch(message)
        if app_name and not app_names:
            app_names = (app_name,)
        if app_names and plan.intent in {"launch_allowlisted_app", "launch_allowlisted_apps"}:
            # An explicit, unambiguous request for fixed allow-listed apps is the
            # per-request authorization. Multi-app plans execute sequentially.
            display_apps = ", ".join(name.title() for name in app_names)
            try:
                self.task_receipts.record_step(
                    message, f"launch {display_apps}", "started",
                    evidence="Sir explicitly requested these allow-listed local app launches.",
                )
            except (ValueError, OSError):
                self._record_activity("task_step_receipt", "not_saved", "launch still proceeds; step receipt could not be stored")
            token = self._begin_work()
            self.status.set(f"Action: launching {display_apps}…")

            def launch():
                runtime = None
                try:
                    token.raise_if_cancelled()
                    runtime = execute_plan(
                        plan,
                        registry=self.capability_registry,
                        approved=True,
                        cancellation=token,
                    )
                    self._record_runtime_steps(message, runtime.step_results)
                    outcome = runtime.capability_result
                    event = action_event_for_runtime(runtime)
                    if event[0] == "cancelled":
                        self._post_event("cancelled", message)
                        return
                except OperationCancelled:
                    self._post_event("cancelled", message)
                    return
                except Exception:
                    event = ("action_failed", "Unexpected launch error. No further action was taken.")
                self._post_event("action", (event[0], event[1], message))

            threading.Thread(target=launch, daemon=True).start()
            return

        token = self._begin_work()
        self.status.set(f"AI status: generating with {self.provider_name}…")

        def work():
            try:
                token.raise_if_cancelled()
                response = self.service.respond(message, timeout_seconds=120.0)
                token.raise_if_cancelled()
            except OperationCancelled:
                self._post_event("cancelled", message)
                return
            except Exception:
                if token.cancelled:
                    self._post_event("cancelled", message)
                    return
                response = "An unexpected error occurred; no desktop action was performed."
            if token.cancelled:
                self._post_event("cancelled", message)
                return
            # The UI event handler expects both the original task and its response.
            self._post_event("response", (message, response))

        threading.Thread(target=work, daemon=True).start()

    def _finish_action(self, outcome: str, detail: str, task: str) -> None:
        if self.closing:
            return
        activity_status = {"action_verified": "verified", "action_accepted": "accepted", "action_failed": "failed", "action_partial": "partial", "action_unknown": "unknown"}.get(outcome, "failed")
        self._record_activity("desktop_action", activity_status)
        try:
            self.task_receipts.record_step(task, "desktop action sequence", {"action_verified": "verified", "action_accepted": "attempted", "action_failed": "failed", "action_partial": "partial", "action_unknown": "unknown"}.get(outcome, "failed"), evidence=detail)
        except (ValueError, OSError):
            self._record_activity("task_step_receipt", "not_saved", "desktop action outcome remains visible but step receipt was not saved")
        try:
            receipt = self.task_receipts.record(task, outcome, evidence=detail)
            self._record_activity("task_receipt", receipt["outcome"], f"id={receipt['id']}")
        except (ValueError, OSError):
            self._record_activity("task_receipt", "not_saved", "desktop result remains visible but receipt was not saved")
        try:
            reflection = self.auto_learning.reflect(task, outcome=outcome, evidence=detail)
            self._record_activity("automatic_reflection", reflection.outcome, f"episode={reflection.episode.episode_id}")
        except (ValueError, OSError):
            self._record_activity("automatic_reflection", "failed", "action result was not recorded")
        if should_propose_desktop_repair(outcome, detail):
            try:
                repair = self.repairs.propose(
                    failure_summary="Unexpected desktop-action worker error; task content and internal details omitted.",
                    proposed_change=(
                        "Reproduce the failure using a fake adapter first. Inspect the registered capability dispatch "
                        "and exception boundary, add a focused regression test, run the full test suite, then verify "
                        "on real Windows. Do not blindly retry non-idempotent actions or modify live code automatically."
                    ),
                    source_ref="gui-desktop-action-failure",
                )
                self._record_activity("repair_proposal", "proposed", f"id={repair.repair_id}")
                self._append(
                    "JARVIS",
                    f"Saved reviewable desktop diagnostic proposal #{repair.repair_id}. No code was changed automatically.",
                )
            except (ValueError, OSError):
                self._record_activity(
                    "repair_proposal", "not_saved",
                    "Unexpected desktop failure remains visible; diagnostic proposal could not be stored.",
                )
        self._append("JARVIS", detail)
        self._finish_work_controls()
        self.status.set({"action_verified": "Action: text entry and read-back verified", "action_accepted": "Action: launch requests accepted; visibility unverified", "action_partial": "Action: partially completed; check desktop before retrying", "action_unknown": "Action: outcome unknown; check desktop before retrying"}.get(outcome, "Action: not completed"))

    def _finish_response(self, task: str, response: str) -> None:
        if self.closing:
            return
        failure = response.startswith(("The AI provider failed;", "The AI provider returned an empty response;", "An unexpected error occurred;"))
        try:
            receipt = self.task_receipts.record(task, "provider_failed" if failure else "response_generated", evidence="Provider response received; real-world goal completion is unverified." if not failure else "No usable provider response was returned.")
            self._record_activity("task_receipt", receipt["outcome"], f"id={receipt['id']}")
        except (ValueError, OSError):
            self._record_activity("task_receipt", "not_saved", "chat result remains visible but receipt was not saved")
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
        self._finish_work_controls()
        self.status.set(f"AI status: response finished · {self.provider_name}")

    def _finish_research(self, success: bool, detail: str, task: str) -> None:
        if self.closing:
            return
        outcome = "research_succeeded" if success else "research_failed"
        try:
            self.task_receipts.record_step(task, "public source lookup", "verified" if success else "failed", evidence="Lookup returned a report; independent fact verification is not implied." if success else "Source lookup failed or was unavailable.")
        except (ValueError, OSError):
            self._record_activity("task_step_receipt", "not_saved", "research result remains visible but step receipt was not saved")
        try:
            receipt = self.task_receipts.record(task, outcome, evidence="Public-source lookup returned a report; independent verification is not implied." if success else "Research source unavailable or failed.")
            self._record_activity("task_receipt", receipt["outcome"], f"id={receipt['id']}")
        except (ValueError, OSError):
            self._record_activity("task_receipt", "not_saved", "research result remains visible but receipt was not saved")
        try:
            reflection = self.auto_learning.reflect(task, outcome="response_generated" if success else "provider_failed", evidence="Public-source lookup completed." if success else "Research source unavailable.")
            self._record_activity("automatic_reflection", reflection.outcome, f"episode={reflection.episode.episode_id}")
        except (ValueError, OSError):
            self._record_activity("automatic_reflection", "failed", "research outcome was not recorded")
        self._record_activity("public_research", "success" if success else "failed")
        self._append("JARVIS", detail)
        self._finish_work_controls()
        self.status.set("Research: finished" if success else "Research: unavailable")

    def check_status(self) -> None:
        if self.busy or self.closing:
            self.status.set("AI status: busy; wait for the current request")
            return
        token = self._begin_work()
        self.status.set("AI status: testing with a real generation request…")
        provider = self.provider

        def work():
            try:
                token.raise_if_cancelled()
                result = check_provider(provider, timeout_seconds=15.0)
                token.raise_if_cancelled()
                payload = (result.healthy, result.detail)
            except OperationCancelled:
                self._post_event("cancelled", "provider health check")
                return
            except Exception:
                if token.cancelled:
                    self._post_event("cancelled", "provider health check")
                    return
                payload = (False, "Provider health check failed unexpectedly.")
            if token.cancelled:
                self._post_event("cancelled", "provider health check")
                return
            self._post_event("health", payload)

        threading.Thread(target=work, daemon=True).start()

    def close(self) -> None:
        self.closing = True
        if self.current_cancellation is not None:
            self.current_cancellation.cancel()
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
