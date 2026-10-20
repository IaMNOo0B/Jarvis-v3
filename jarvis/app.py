"""Minimal text-only entry point for the first vertical slice."""

from jarvis.chat_service import ChatService
from jarvis.intents import parse_intent


_service = ChatService()


def respond(text: str) -> str:
    return _service.respond(text)


def main() -> None:
    print("JARVIS v3 — text-only foundation. Type /help or /exit.")
    while True:
        try:
            message = input("Sir> ")
        except (EOFError, KeyboardInterrupt):
            print("\\nSession ended.")
            break
        response = respond(message)
        print(f"JARVIS> {response}")
        if parse_intent(message).name == "exit":
            break


if __name__ == "__main__":
    main()
