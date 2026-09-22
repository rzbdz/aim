"""MCP wrapper around `bin/aim`.

The MCP server is deliberately boring: it lists tools derived from the CLI and
runs the CLI. It never appends to a log, never records a refusal and never
decides whether a command is legal. `bin/aim` owns all of that; this module owns
only the MCP translation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def _run_cli(aim_bin: Path, argv: list[str], root: Path, timeout: float = 30):
    """Run one aim command. The wrapper's only privileged operation."""
    env = os.environ | {"AIM_ROOT": str(root)}
    return subprocess.run([str(aim_bin), *argv], capture_output=True, text=True,
                          timeout=timeout, env=env, check=False)


def _choices(help_text: str) -> list[str]:
    match = re.search(r"\{([^}]+)\}", help_text)
    if not match:
        return []
    return [choice.strip() for choice in match.group(1).split(",") if choice.strip()]


def cli_verbs(aim_bin: Path, root: Path) -> list[str]:
    """Parse the CLI's own top-level choices, not a hand-maintained list."""
    done = _run_cli(aim_bin, ["--help"], root)
    if done.returncode != 0:
        raise RuntimeError(f"aim --help failed: {done.stderr.strip()}")
    verbs = _choices(done.stdout)
    if not verbs:
        raise RuntimeError("aim --help printed no top-level command list")
    return verbs


def _supports_actor(aim_bin: Path, root: Path, prefix: list[str], seen: set[tuple[str, ...]]) -> bool:
    """Does this verb (or one of its subcommands) accept --as?

    `task` is the reason this is recursive: the top-level `task --help` has no
    `--as`, while every `task <subcommand>` does. Appending the identity at the
    wrong level would turn every task tool call into an argparse error.
    """
    key = tuple(prefix)
    if key in seen:
        return False
    seen.add(key)
    done = _run_cli(aim_bin, [*prefix, "--help"], root)
    if done.returncode != 0:
        return False
    if "--as" in done.stdout:
        return True
    return any(_supports_actor(aim_bin, root, [*prefix, choice], seen)
               for choice in _choices(done.stdout))


def tool_specs(aim_bin: Path, root: Path) -> list[dict[str, Any]]:
    """Build one MCP tool per top-level verb, derived from `aim --help`."""
    specs = []
    for verb in cli_verbs(aim_bin, root):
        done = _run_cli(aim_bin, [verb, "--help"], root)
        help_text = done.stdout.strip() if done.returncode == 0 else ""
        specs.append({
            "name": verb,
            "description": (
                f"Run `aim {verb}`. `argv` is the list of strings that follow the verb; "
                "`bin/aim` validates every option. Where the verb accepts an actor, the "
                "server appends its own `--as` identity and drops any caller-supplied one."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"arguments after `aim {verb}`",
                    },
                },
                "additionalProperties": False,
            },
            "supportsActor": _supports_actor(aim_bin, root, [verb], set()),
            "help": help_text,
        })
    return specs


def _strip_actor(argv: list[str]) -> list[str]:
    """Remove a caller's --as claim; identity is not an argument here."""
    cleaned, skip = [], False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == "--as":
            skip = True
            continue
        if arg.startswith("--as="):
            continue
        cleaned.append(arg)
    return cleaned


def command_result(done: subprocess.CompletedProcess[str], argv: list[str]) -> dict[str, Any]:
    return {
        "ok": done.returncode == 0,
        "exitCode": done.returncode,
        "argv": argv,
        "stdout": done.stdout,
        "stderr": done.stderr,
    }


def create_server(root: Path, aim_bin: Path, actor: str):
    """Create the low-level MCP server. Requires the official `mcp` package."""
    from mcp import types
    from mcp.server import Server

    specs = tool_specs(aim_bin, root)
    by_name = {spec["name"]: spec for spec in specs}
    tools = [
        types.Tool(
            name=spec["name"],
            description=spec["description"],
            inputSchema=spec["inputSchema"],
            _meta={"supportsActor": spec["supportsActor"], "help": spec["help"]},
        )
        for spec in specs
    ]

    async def list_tools(_context, _params):
        return types.ListToolsResult(tools=tools)

    async def call_tool(_context, params):
        spec = by_name.get(params.name)
        if spec is None:
            return _error(f"unknown tool: {params.name}")
        arguments = params.arguments or {}
        argv = arguments.get("argv", [])
        if not isinstance(argv, list) or any(not isinstance(arg, str) for arg in argv):
            return _error("argv must be an array of strings")
        cleaned = _strip_actor(argv) if spec["supportsActor"] else argv
        full_argv = [spec["name"], *cleaned]
        if spec["supportsActor"]:
            full_argv += ["--as", actor]
        try:
            done = _run_cli(aim_bin, full_argv, root)
            result = command_result(done, full_argv)
        except subprocess.TimeoutExpired as exc:
            return _error(f"aim {spec['name']} did not finish in 30s: {exc}")
        except Exception as exc:
            return _error(f"wrapper failed without running aim: {exc}")
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))],
            structuredContent=result,
            isError=done.returncode != 0,
        )

    def _error(message: str):
        result = {"ok": False, "exitCode": None, "argv": [], "stdout": "", "stderr": message}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))],
            structuredContent=result,
            isError=True,
        )

    return Server(
        "aim",
        version="1",
        description="Thin MCP wrapper around the aim CLI; bin/aim remains the only writer.",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def main(argv=None):
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Serve aim over MCP stdio.")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="fabric root served and passed to bin/aim as AIM_ROOT")
    parser.add_argument("--as", dest="actor", required=True,
                        help="identity this MCP server writes as; callers cannot change it")
    parser.add_argument("--aim-bin", type=Path, default=here / "bin" / "aim")
    args = parser.parse_args(argv)

    from mcp.server.stdio import stdio_server

    async def run():
        server = create_server(args.root.resolve(), args.aim_bin.resolve(), args.actor)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
