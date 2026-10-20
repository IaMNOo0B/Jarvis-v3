"""Minimal text-only entry point for the first vertical slice."""

from jarvis.intents import parse_intent


def respond(text: str) -> str:
    intent = parse_intent(text)
    if intent.name == "empty":
        return "Please enter a message."
    if intent.name == "help":
        return "Available commands: /help, /exit. Desktop actions are not enabled yet."
    if intent.name == "exit":
        return "Goodbye, Sir."
    return "The text core is ready, but no AI provider is configured yet."


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
