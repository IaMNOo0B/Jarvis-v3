"""Small no-console Windows chat window with explicitly approved app launching."""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from jarvis.chat_service import ChatService
from jarvis.desktop_actions import launch_allowlisted_app, parse_app_launch_request
from jarvis.health import check_provider
from jarvis.provider_config import build_provider


class JarvisWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JARVIS v3")
        self.root.geometry("760x560")
        self.root.minsize(560, 400)
        self.provider = build_provider()
        self.service = ChatService(self.provider)
        self.busy = False
        self.closing = False
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()

        shell = ttk.Frame(root, padding=12)
        shell.pack(fill="both", expand=True)
        heading = ttk.Frame(shell)
        heading.pack(fill="x")
        ttk.Label(heading, text="JARVIS v3", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(heading, text="Check AI status", command=self.check_status).pack(side="right")
        self.status = tk.StringVar(value="AI status: not checked · Ollama local model")
        ttk.Label(shell, textvariable=self.status).pack(anchor="w", pady=(8, 6))
        self.transcript = scrolledtext.ScrolledText(shell, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.transcript.pack(fill="both", expand=True, pady=(0, 8))
        compose = ttk.Frame(shell)
        compose.pack(fill="x")
        self.entry = ttk.Entry(compose)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send)
        self.send_button = ttk.Button(compose, text="Send", command=self.send)
        self.send_button.pack(side="right")
        ttk.Label(shell, text="App launching supports Notepad/Chrome with confirmation. No microphone is active.").pack(anchor="w", pady=(8, 0))
        self._append("JARVIS", "Ready. Ask a question or use /help. Say “open Notepad” or “open Chrome” to request an approved app launch.")
        self.entry.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(40, self._drain_events)

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

    def send(self, event=None) -> None:
        if self.busy or self.closing:
            return
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, "end")
        self._append("Sir", message)
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
                    result = launch_allowlisted_app(app_name)
                    event = (result.success, result.detail)
                except Exception:
                    event = (False, "Unexpected launch error. No further action was taken.")
                self._post_event("action", event)

            threading.Thread(target=launch, daemon=True).start()
            return

        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.set("AI status: generating response…")

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
        self.status.set("AI status: response finished · Ollama local model")
        self.entry.focus_set()

    def check_status(self) -> None:
        if self.busy or self.closing:
            self.status.set("AI status: busy; wait for the current request")
            return
        self.busy = True
        self.send_button.configure(state="disabled")
        self.status.set("AI status: testing with a real generation request…")

        def work():
            try:
                result = check_provider(self.provider, timeout_seconds=15.0)
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
