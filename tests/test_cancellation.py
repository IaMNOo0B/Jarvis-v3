import unittest

from jarvis.cancellation import CancellationToken, OperationCancelled


class CancellationTests(unittest.TestCase):
    def test_token_starts_active_and_can_be_cancelled(self):
        token = CancellationToken()
        self.assertFalse(token.cancelled)
        token.cancel()
        self.assertTrue(token.cancelled)

    def test_cancelled_token_raises_at_checkpoint(self):
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(OperationCancelled):
            token.raise_if_cancelled()


if __name__ == "__main__":
    unittest.main()
