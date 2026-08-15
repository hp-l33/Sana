import unittest

from sol.cli import parse_args


class CliTests(unittest.TestCase):
    def test_model_arguments_follow_explicit_separator(self):
        args = parse_args(
            [
                "inspect",
                "demo",
                "--preset",
                "balanced",
                "--target",
                "cpu",
                "--set",
                "cache.threshold=0.15",
                "--",
                "--prompt",
                "hello",
            ]
        )
        self.assertEqual(args.preset, "balanced")
        self.assertEqual(args.target, "cpu")
        self.assertEqual(args.arguments, ["--prompt", "hello"])
        self.assertEqual(args.set, ["cache.threshold=0.15"])


if __name__ == "__main__":
    unittest.main()
