"""Validate the distributed package: matching versions and no hook adapters."""
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release_claude", ROOT / "release_claude.py")
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


class PackageTest(unittest.TestCase):
    def test_release_versions_match(self):
        versions = {json.loads((ROOT / name).read_text())["version"] for name in
                    ["plugin.json", ".claude-plugin/plugin.json", "gemini-extension.json"]}
        self.assertEqual(versions, {"2.2.4"})

    def test_claude_distribution_excludes_development_and_other_host_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            RELEASE.build(ROOT, output)
            files = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            expected = set(RELEASE.STATIC_FILES)
            expected.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "skills").rglob("*.md"))
            self.assertEqual(files, expected)
            self.assertEqual(len(list((output / "skills").glob("*/SKILL.md"))), 9)
            for name in files:
                self.assertEqual((output / name).read_bytes(), (ROOT / name).read_bytes())
            for name in ["tests", "release_claude.py", "plugin.json", "mcp.json",
                         "gemini-extension.json", ".claude-plugin/marketplace.json"]:
                self.assertFalse((output / name).exists(), name)

    def test_claude_distribution_rejects_executable_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            for name in RELEASE.STATIC_FILES:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            skill = source / "skills/unsafe/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("#!/bin/sh\necho unsafe\n")
            with self.assertRaisesRegex(ValueError, "Executable or non-text"):
                RELEASE.build(source, Path(directory) / "output")

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
