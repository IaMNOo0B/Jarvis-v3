"""Small no-console Windows chat window with explicitly approved app launching."""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from datetime import datetime, timezone

from jarvis.reminders import ReminderStore
from jarvis.memory import MemoryStore

from jarvis.chat_service import ChatService
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
        self.service = ChatService(self.provider)
        self.busy = False
        self.closing = False
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.reminders = ReminderStore()
        self.memory = MemoryStore()
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
                self._finish_response(str(payload))
            elif kind == "action":
                success, detail = payload
                self._finish_action(bool(success), str(detail))
            elif kind == "health":
                healthy, detail = payload
                label = "HEALTHY" if healthy else "NOT HEALTHY"
                self.status.set(f"AI status: {label} · {detail}")
                self.busy = False
                self.send_button.configure(state="normal")
        self.root.after(40, self._drain_events)

    def _check_due_reminders(self) -> None:\n        if self.closing:\n            return\n        try:\n            for reminder in self.reminders.due():\n                if reminder.reminder_id in self._notified_reminders:\n                    continue\n                # Mark before showing UI so repeated polling cannot duplicate this session notification.\n                if self.reminders.mark_fired(reminder.reminder_id):\n                    self._notified_reminders.add(reminder.reminder_id)\n                    self._append("REMINDER", reminder.message)\n                    messagebox.showinfo("JARVIS reminder", reminder.message, parent=self.root)\n        except Exception:\n            self.status.set("Reminder check failed; saved reminders were not deleted.")\n        if not self.closing:\n            self.root.after(1000, self._check_due_reminders)\n\n    def _handle_reminder_command(self, message: str) -> bool:\n        lowered = message.casefold().strip()\n        if lowered == "/reminders":\n            items = self.reminders.list()\n            if not items:\n                self._append("JARVIS", "No pending reminders.")\n            else:\n                lines = [f"#{item.reminder_id} · {item.due_at} · {item.message}" for item in items]\n                self._append("JARVIS", "Pending reminders:\\n" + "\\n".join(lines))\n            return True\n        if lowered.startswith("/cancel-reminder "):\n            raw_id = message.strip().split(maxsplit=1)[1]\n            if not raw_id.isdigit():\n                self._append("JARVIS", "Usage: /cancel-reminder ID")\n            elif self.reminders.cancel(int(raw_id)):\n                self._append("JARVIS", f"Cancelled reminder #{raw_id}.")\n            else:\n                self._append("JARVIS", f"No pending reminder found with ID {raw_id}.")\n            return True\n        if lowered.startswith("/remind "):\n            payload = message.strip()[len("/remind "): ]\n            if "|" not in payload:\n                self._append("JARVIS", "Usage: /remind YYYY-MM-DDTHH:MM:SS+05:30 | reminder text (time must include timezone)")\n                return True\n            due_at, content = payload.split("|", 1)\n            try:\n                reminder = self.reminders.create(due_at.strip(), content)\n            except (ValueError, OSError):\n                self._append("JARVIS", "Reminder not saved. Check the ISO date/time, timezone offset, and message.")\n                return True\n            self._append("JARVIS", f"Saved reminder #{reminder.reminder_id} for {reminder.due_at} (UTC).")\n            return True\n        return False\n\n    def _handle_memory_command(self, message: str) -> bool:
        stripped = message.strip()
        lowered = stripped.casefold()
        if lowered.startswith("/remember "):
            content = stripped[len("/remember "):].strip()
            try:
                item = self.memory.remember(content, source="explicit_user_command")
            except ValueError:
                self._append("JARVIS", "Memory not saved. Use /remember followed by 1–4000 characters.")
                return True
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
                self._append("JARVIS", f"Forgot memory #{raw_id}.")
            else:
                self._append("JARVIS", f"Memory #{raw_id} was not found.")
            return True
        if lowered == "/forget-all":
            if not messagebox.askyesno("Forget all memories", "Permanently delete ALL saved JARVIS memories?", parent=self.root):
                self._append("JARVIS", "Cancelled. Memories were kept.")
            else:
                count = self.memory.forget_all(confirmed=True)
                self._append("JARVIS", f"Forgot {count} saved memories.")
            return True
        return False

    def _set_provider(self, name: str) -> None:
        credentials = CredentialStore() if name == "gemini" else None
        provider = build_provider(ProviderConfig(name=name), credentials=credentials)
        self.provider = provider
        self.service = ChatService(provider)
        self.provider_name = name
        self.status.set(f"Provider selected: {'Google Gemini' if name == 'gemini' else 'Local Ollama'} · run Check AI status to test")

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
        self._append("Sir", message)\n        if self._handle_reminder_command(message):\n            return\n        app_name = parse_app_launch_request(message)\n        if app_name:
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
                self._post_event("action", event)

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
            self._post_event("response", response)

        threading.Thread(target=work, daemon=True).start()

    def _finish_action(self, success: bool, detail: str) -> None:
        if self.closing:
            return
        self._append("JARVIS", detail)
        self.busy = False
        self.send_button.configure(state="normal")
        self.status.set("Action: launch request accepted" if success else "Action: not completed")
        self.entry.focus_set()

    def _finish_response(self, response: str) -> None:
        if self.closing:
            return
        self._append("JARVIS", response)
        self.busy = False
        self.send_button.configure(state="normal")
        self.status.set(f"AI status: response finished · {self.provider_name}")
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
