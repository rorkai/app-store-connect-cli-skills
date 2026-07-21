from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate-plugin-packaging.py"
SPEC = importlib.util.spec_from_file_location("validate_plugin_packaging", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class PackagingValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        skill = self.root / "skills" / "asc-example"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: asc-example\ndescription: Example\n---\n", encoding="utf-8")
        self.codex = {
            "name": "asc",
            "version": "1.0.0",
            "description": "Example Codex package",
            "author": {"name": "Example", "url": "https://example.com"},
            "homepage": "https://example.com/plugin",
            "repository": "https://example.com/repository",
            "license": "MIT",
            "skills": "./skills/",
            "interface": {
                "displayName": "ASC",
                "shortDescription": "ASC skills",
                "longDescription": "App Store Connect skills",
                "developerName": "Example",
                "category": "Developer Tools",
                "capabilities": ["Interactive"],
                "defaultPrompt": ["Prepare my release"],
            },
        }
        self.claude = {
            "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
            "name": "asc",
            "version": "1.0.0",
            "description": "Example Claude package",
            "author": {"name": "Example", "url": "https://example.com"},
            "homepage": "https://example.com/plugin",
            "repository": "https://example.com/repository",
            "license": "MIT",
        }
        self.marketplace = {"name": "example", "plugins": [{"name": "asc", "source": "./"}]}
        self.write_manifests()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifests(self) -> None:
        for directory, name, payload in (
            (".codex-plugin", "plugin.json", self.codex),
            (".claude-plugin", "plugin.json", self.claude),
            (".claude-plugin", "marketplace.json", self.marketplace),
        ):
            path = self.root / directory / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_valid_cross_host_package(self) -> None:
        self.assertEqual([], VALIDATOR.validate(self.root, 1))

    def test_rejects_cross_host_version_drift(self) -> None:
        self.claude["version"] = "1.1.0"
        self.write_manifests()
        self.assertIn(
            "Codex and Claude manifests must use the same version",
            VALIDATOR.validate(self.root, 1),
        )

    def test_rejects_cross_host_name_drift(self) -> None:
        self.codex["name"] = "asc-codex"
        self.write_manifests()
        self.assertIn(
            "Codex and Claude manifests must use the same name",
            VALIDATOR.validate(self.root, 1),
        )

    def test_rejects_wrong_skill_count(self) -> None:
        self.assertIn("expected 2 skills, found 1", VALIDATOR.validate(self.root, 2))

    def test_rejects_non_root_claude_source(self) -> None:
        self.marketplace["plugins"][0]["source"] = "."
        self.write_manifests()
        self.assertIn(
            "Claude marketplace plugin source must be `./` so the repository root is loadable",
            VALIDATOR.validate(self.root, 1),
        )


if __name__ == "__main__":
    unittest.main()
