"""Validate the distributed adapters and opt-in configuration without running them."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PackageTest(unittest.TestCase):
    def test_release_versions_match(self):
        versions = {json.loads((ROOT / name).read_text())["version"] for name in
                    ["plugin.json", ".claude-plugin/plugin.json", "gemini-extension.json"]}
        self.assertEqual(versions, {"2.1.0"})

    def test_opt_in_configs_reference_shipped_scripts_and_native_servers(self):
        for name, script in [("codex/hooks.json", "kedeka.py"),
                             ("claude/settings.json", "kedeka_claude.py")]:
            data = json.loads((ROOT / "integrations" / name).read_text())
            self.assertIn("PreToolUse", data["hooks"])
            self.assertIn("Stop", data["hooks"])
            self.assertIn("SessionEnd", data["hooks"])
            for entries in data["hooks"].values():
                for entry in entries:
                    for hook in entry["hooks"]:
                        if hook["type"] == "command":
                            self.assertIn(".agents/hooks/" + script, hook["command"])
                            self.assertTrue((ROOT / ".agents/hooks" / script).is_file())
                            subprocess.run(["sh", "-n", "-c", hook["command"]], check=True)
                        else:
                            self.assertEqual(hook["type"], "mcp_tool")
                            self.assertEqual(hook["server"], "kedeka")
                            self.assertEqual(hook["tool"], "create_record")
                            self.assertEqual(hook["input"]["entity"], "agent_hook")
        # A business plugin install must not silently activate repository edit guards.
        self.assertFalse((ROOT / "hooks/hooks.json").exists())
        self.assertNotIn("hooks", json.loads((ROOT / ".claude-plugin/plugin.json").read_text()))


if __name__ == "__main__":
    unittest.main()
