"""Validate the distributed package: matching versions and no hook adapters."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PackageTest(unittest.TestCase):
    def test_release_versions_match(self):
        versions = {json.loads((ROOT / name).read_text())["version"] for name in
                    ["plugin.json", ".claude-plugin/plugin.json", "gemini-extension.json"]}
        self.assertEqual(versions, {"2.2.1"})

    def test_package_ships_no_hooks_or_edit_guards(self):
        for path in ["hooks", ".agents/hooks", "integrations"]:
            self.assertFalse((ROOT / path).exists(), path)
        self.assertNotIn("hooks", json.loads((ROOT / ".claude-plugin/plugin.json").read_text()))

    def test_track_work_skill_keeps_tracking_optional(self):
        skill = (ROOT / "skills/track-work/SKILL.md").read_text()
        self.assertIn("never a condition", skill)
        for word in ["lifecycle_hooks", "agent_hook", "PreToolUse"]:
            self.assertNotIn(word, skill)


if __name__ == "__main__":
    unittest.main()
