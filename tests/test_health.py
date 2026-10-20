import unittest

from jarvis.health import check_provider
from jarvis.providers.base import ChatResponse, ProviderError


class FakeProvider:
    name = "fake"
    def __init__(self, result=None, error=None): self.result, self.error = result, error
    def generate(self, request):
        if self.error: raise self.error
        return self.result


class HealthTests(unittest.TestCase):
    def test_health_requires_successful_generation(self):
        result = check_provider(FakeProvider(result=ChatResponse("OK", "fake")))
        self.assertTrue(result.healthy)
        self.assertEqual(result.detail, "Real generation request succeeded.")

    def test_provider_error_is_unhealthy(self):
        result = check_provider(FakeProvider(error=ProviderError("private details")))
        self.assertFalse(result.healthy)
        self.assertNotIn("private details", result.detail)

    def test_empty_response_is_unhealthy(self):
        result = check_provider(FakeProvider(result=ChatResponse("  ", "fake")))
        self.assertFalse(result.healthy)

    def test_nonpositive_timeout_is_rejected(self):
        result = check_provider(FakeProvider(), timeout_seconds=0)
        self.assertFalse(result.healthy)


if __name__ == "__main__": unittest.main()
