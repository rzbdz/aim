#!/usr/bin/env python3
"""The MCP wrapper contract: one writer, one identity, one tool per verb."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HERE = Path(__file__).resolve().parent.parent
AIM = HERE / "bin" / "aim"


def cli_verbs(root):
    done = subprocess.run(
        [sys.executable, str(AIM), "--help"],
        env=os.environ | {"AIM_ROOT": str(root)},
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    match = re.search(r"\{([^}]+)\}", done.stdout)
    if not match:
        raise AssertionError("aim --help printed no top-level command list")
    return [choice.strip() for choice in match.group(1).split(",") if choice.strip()]


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@unittest.skipUnless(importlib.util.find_spec("mcp"), "the official MCP SDK is not installed")
class MCPWrapperTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aim-mcp-"))
        self.decoy_root = Path(tempfile.mkdtemp(prefix="aim-mcp-decoy-"))
        self.env = os.environ | {"AIM_ROOT": str(self.root)}
        for argv in (
            ["init"],
            ["register", "--as", "human", "--kind", "human"],
            ["register", "--as", "codex", "--kind", "codex"],
            ["new-channel", "--id", "t", "--topic", "mcp contract",
             "--participants", "codex", "--leader", "human"],
        ):
            done = subprocess.run(
                [sys.executable, str(AIM), *argv],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(done.returncode, 0, done.stderr)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.decoy_root, ignore_errors=True)

    async def test_wrapper_identity_tools_and_refusals(self):
        from mcp import Client
        from aimboard.mcp import create_server

        os.environ["AIM_ROOT"] = str(self.decoy_root)
        try:
            async with Client(create_server(self.root, AIM, "codex")) as client:
                listed = await client.list_tools()
                self.assertEqual([tool.name for tool in listed.tools], cli_verbs(self.root))

                created = await client.call_tool(
                    "task",
                    {"argv": ["new", "--channel", "t", "--title", "identity is server-side",
                              "--as", "attacker"]},
                )
                self.assertFalse(created.is_error)
                self.assertIn("--as", created.structured_content["argv"])
                self.assertIn("codex", created.structured_content["argv"])
                self.assertNotIn("attacker", created.structured_content["argv"])
                task_events = jsonl(self.root / "channels" / "t" / "tasks.jsonl")
                self.assertEqual(task_events[-1]["actor"], "codex")

                before = [row for row in jsonl(self.root / "channels" / "t" / "ledger.jsonl")
                          if row.get("event") == "refusal"]
                refused = await client.call_tool(
                    "task",
                    {"argv": ["new", "--channel", "t", "--title", "leak",
                              "--visibility", "published", "--as", "attacker"]},
                )
                after = [row for row in jsonl(self.root / "channels" / "t" / "ledger.jsonl")
                         if row.get("event") == "refusal"]
                self.assertTrue(refused.is_error)
                self.assertEqual(refused.structured_content["exitCode"], 2)
                self.assertIn("REFUSED", refused.structured_content["stderr"])
                self.assertEqual(len(after), len(before) + 1)
                self.assertEqual(after[-1]["agent"], "codex")

                self.assertTrue((self.root / "registry.json").exists())
                self.assertFalse((self.decoy_root / "registry.json").exists())
        finally:
            os.environ["AIM_ROOT"] = str(self.root)


if __name__ == "__main__":
    unittest.main()
