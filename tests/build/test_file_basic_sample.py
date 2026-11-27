"""Check that samples/file/basic expects the greeting that its source writes, in every scenario and its README."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "samples/file/basic"
GREETING = "Hello from Crux File API"


class FileBasicSampleTest(unittest.TestCase):
    def test_source_writes_the_greeting(self):
        source = (SAMPLE / "zephyr/src/main.c").read_text()
        self.assertIn(f'static const char greeting[] = "{GREETING}";', source)

    def test_scenarios_and_readme_expect_its_length_and_text(self):
        lines = [f"Wrote {len(GREETING)} bytes to greeting.txt", f"Read {len(GREETING)} bytes: {GREETING}"]
        manifest = (SAMPLE / "zephyr/sample.yaml").read_text()
        self.assertEqual(len(re.findall(r"^  crux\.sample\.file\.basic\.\w+:$", manifest, re.MULTILINE)), 2)
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(manifest.count(f'- "{line}"\n'), 2)
                self.assertGreaterEqual((SAMPLE / "README.md").read_text().count(line + "\n"), 2)


if __name__ == "__main__":
    unittest.main()
