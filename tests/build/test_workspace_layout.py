#!/usr/bin/env python3
"""Keep the Dev Container layout and the pages that describe it in step.

The container mounts the parent folder of the repository at /workspace, so the
west workspace is /workspace and the repository is /workspace/<repo folder>.
Recorded evidence and history pages keep the old path on purpose and are not
checked.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = "/workspaces/crux"
HISTORICAL = {"docs/baseline.md", "docs/implementation-status.md"}


def described_files():
    files = list((ROOT / ".devcontainer").rglob("*"))
    files.append(ROOT / "README.md")
    files += (ROOT / "samples").rglob("*.md")
    files += (ROOT / "docs").glob("*.md")
    for path in files:
        if path.is_file() and path.relative_to(ROOT).as_posix() not in HISTORICAL:
            yield path


class WorkspaceLayoutTest(unittest.TestCase):
    def test_no_page_or_container_file_names_the_old_mount(self):
        hits = [
            path.relative_to(ROOT).as_posix()
            for path in described_files()
            if OLD in path.read_text(encoding="utf-8")
        ]
        self.assertEqual([], hits)

    def test_devcontainers_mount_the_parent_folder_at_workspace(self):
        configs = list((ROOT / ".devcontainer").rglob("devcontainer.json"))
        self.assertTrue(configs)
        for config in configs:
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertIn("target=/workspace,", data["workspaceMount"], config)
            self.assertTrue(data["workspaceFolder"].startswith("/workspace/"), config)
            self.assertEqual("/workspace", data["containerEnv"]["CRUX_WORKSPACE"], config)
            self.assertEqual(data["workspaceFolder"], data["containerEnv"]["CRUX_REPO"], config)
            self.assertNotIn("/workspaces/", json.dumps(data), config)


if __name__ == "__main__":
    unittest.main()
