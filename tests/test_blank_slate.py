import unittest

from sol.engine import Engine


class BlankSlateTests(unittest.TestCase):
    def test_distribution_has_no_bundled_models(self):
        self.assertEqual(Engine().models(include_drafts=True), [])


if __name__ == "__main__":
    unittest.main()
