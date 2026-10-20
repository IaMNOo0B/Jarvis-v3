"""Minimal text-only entry point, wired to the configured local Ollama model."""

from jarvis.chat_service import ChatService
from jarvis.intents import parse_intent
from jarvis.providers.ollama import OllamaProvider


# This configures a loopback-only provider. It does not download or launch Ollama.
# If Ollama is stopped or the model is missing, ChatService reports the failure.
_service = ChatService(provider=OllamaProvider())


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
