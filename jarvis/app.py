"""Minimal text-only entry point using explicit local provider configuration."""

from jarvis.chat_service import ChatService
from jarvis.intents import parse_intent
from jarvis.provider_config import build_provider


# Local-only provider construction; no cloud fallback and no desktop actions.
_service = ChatService(provider=build_provider())


def respond(text: str) -> str:
    return _service.respond(text, timeout_seconds=120.0)


def main() -> None:
    print("JARVIS v3 — local Ollama text core. Type /help or /exit.")
    print("Model: qwen2.5:7b-instruct-q4_K_M. No desktop actions are enabled.")
    while True:
        try:
            message = input("Sir> ")
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break
        response = respond(message)
        print(f"JARVIS> {response}")
        if parse_intent(message).name == "exit":
            break


if __name__ == "__main__":
    main()
