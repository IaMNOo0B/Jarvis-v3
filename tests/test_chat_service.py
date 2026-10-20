import unittest

from jarvis.chat_service import ChatService
from jarvis.providers.base import ChatRequest, ChatResponse, ProviderError


class FakeProvider:
    name = "fake"

    def __init__(self, result="Hello, Sir.", error=None):
        self.result = result
        self.error = error
        self.requests = []

    def generate(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        return ChatResponse(text=self.result, provider=self.name)


class ChatServiceTests(unittest.TestCase):
    def test_commands_do_not_call_provider(self):
        provider = FakeProvider()
        service = ChatService(provider)
        self.assertIn("/help", service.respond("help"))
        self.assertEqual(provider.requests, [])

    def test_chat_is_sent_to_provider(self):
        provider = FakeProvider()
        self.assertEqual(ChatService(provider).respond("hello"), "Hello, Sir.")
        self.assertEqual(provider.requests[0].message, "hello")

    def test_timeout_budget_is_passed_through(self):
        provider = FakeProvider()
        ChatService(provider).respond("hello", timeout_seconds=12)
        self.assertEqual(provider.requests[0].timeout_seconds, 12)

    def test_provider_failure_is_honest(self):
        provider = FakeProvider(error=ProviderError("offline"))
        reply = ChatService(provider).respond("hello")
        self.assertIn("provider failed", reply)
        self.assertIn("no action was performed", reply)

    def test_empty_provider_response_is_not_success(self):
        self.assertIn("empty response", ChatService(FakeProvider(result="  ")).respond("hi"))

    def test_unconfigured_provider_does_not_claim_ai_response(self):
        self.assertIn("No AI provider", ChatService().respond("hello"))


if __name__ == "__main__":
    unittest.main()
