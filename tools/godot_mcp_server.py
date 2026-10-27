#!/usr/bin/env python3
"""
Godot 4.7 Visual & Scene Inspector MCP Server (tools/godot_mcp_server.py)

Zero-dependency Model Context Protocol (MCP) JSON-RPC 2.0 stdio server exposing:
  1. godot_capture_screenshot(view_mode: str = "helm", frames: int = 45)
  2. godot_inspect_scene_tree(scene_path: str = "res://scenes/overworld.tscn")
  3. godot_check_scripts(script_paths: list[str])
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "godot-inspector"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = WORKSPACE_ROOT / ".mcp_captures"
LATEST_FRAME_PATH = CAPTURE_DIR / "latest_frame.png"
SCENE_STATE_PATH = CAPTURE_DIR / "scene_state.json"
SCENE_TREE_PATH = CAPTURE_DIR / "scene_tree.json"

FALLBACK_GODOT_PATHS = [
    r"C:\Users\olema\Downloads\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64_console.exe",
    r"C:\Users\olema\Downloads\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64.exe",
]


def resolve_godot_binary() -> str:
    """Locate the Godot 4.7 executable via environment, PATH, or local workspace fallbacks."""
    env_bin = os.environ.get("GODOT_BIN", "").strip()
    if env_bin and Path(env_bin).is_file():
        return env_bin

    which_bin = shutil.which("godot") or shutil.which("godot4")
    if which_bin:
        return which_bin

    for candidate in FALLBACK_GODOT_PATHS:
        if Path(candidate).is_file():
            return candidate

    return "godot"


def to_res_path(path_str: str) -> str:
    """Normalize a workspace-relative or res:// path into res:// format."""
    cleaned = path_str.strip().replace("\\", "/")
    if cleaned.startswith("res://"):
        return cleaned
    try:
        abs_p = (WORKSPACE_ROOT / cleaned).resolve()
        rel = abs_p.relative_to(WORKSPACE_ROOT.resolve())
        return "res://" + str(rel).replace("\\", "/")
    except ValueError:
        return "res://" + cleaned.lstrip("/")


def parse_compiler_diagnostics(raw_output: str) -> list[dict[str, Any]]:
    """Extract structured script/shader errors and warnings from Godot CLI output."""
    diagnostics: list[dict[str, Any]] = []
    lines = raw_output.splitlines()

    script_err_re = re.compile(
        r"^(SCRIPT ERROR|USER ERROR|ERROR|WARNING|SHADER ERROR):\s*(.*)$",
        re.IGNORECASE,
    )
    at_loc_re = re.compile(r"^\s*at:\s*(.*?)\s*\((res://[^:)]+):(\d+)\)")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = script_err_re.match(line)
        if m:
            severity = "warning" if "WARN" in m.group(1).upper() else "error"
            message = m.group(2).strip()
            file_path = ""
            line_num = 0
            context = ""
            if i + 1 < len(lines):
                loc_m = at_loc_re.match(lines[i + 1])
                if loc_m:
                    context = loc_m.group(1).strip()
                    file_path = loc_m.group(2).strip()
                    line_num = int(loc_m.group(3))
                    i += 1
            diagnostics.append(
                {
                    "severity": severity,
                    "message": message,
                    "file": file_path,
                    "line": line_num,
                    "context": context,
                }
            )
        i += 1
    return diagnostics


def parse_tscn_static_fallback(tscn_file: Path, res_scene_path: str) -> dict[str, Any]:
    """Static fallback parser for .tscn files if headless runtime instantiation is skipped."""
    if not tscn_file.is_file():
        return {"error": f"Scene file not found: {res_scene_path}"}

    content = tscn_file.read_text(encoding="utf-8", errors="replace")
    ext_resources: dict[str, dict[str, str]] = {}
    nodes: list[dict[str, Any]] = []

    ext_re = re.compile(r'\[ext_resource\s+([^\]]+)\]')
    attr_re = re.compile(r'(\w+)="([^"]*)"')

    for match in ext_re.finditer(content):
        attrs = dict(attr_re.findall(match.group(1)))
        res_id = attrs.get("id", "")
        if res_id:
            ext_resources[res_id] = {
                "type": attrs.get("type", ""),
                "path": attrs.get("path", ""),
            }

    sections = re.split(r"(?=\[(?:node|sub_resource|ext_resource|gd_scene|connection)\b)", content)
    for sec in sections:
        if not sec.startswith("[node "):
            continue
        lines = sec.splitlines()
        header = lines[0]
        attrs = dict(attr_re.findall(header))
        node_info: dict[str, Any] = {
            "name": attrs.get("name", ""),
            "type": attrs.get("type", "PackedSceneInstance"),
            "parent": attrs.get("parent", ""),
        }
        if "instance" in header:
            inst_m = re.search(r'instance=ExtResource\("([^"]+)"\)', header)
            if inst_m and inst_m.group(1) in ext_resources:
                node_info["instance_scene"] = ext_resources[inst_m.group(1)]["path"]

        props: dict[str, str] = {}
        for body_line in lines[1:]:
            body_line = body_line.strip()
            if not body_line or "=" not in body_line:
                continue
            k, v = body_line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "script":
                scr_m = re.search(r'ExtResource\("([^"]+)"\)', v)
                if scr_m and scr_m.group(1) in ext_resources:
                    node_info["script"] = ext_resources[scr_m.group(1)]["path"]
                else:
                    node_info["script"] = v
            else:
                props[k] = v
        if props:
            node_info["properties"] = props
        nodes.append(node_info)

    return {
        "scene_path": res_scene_path,
        "ext_resources": ext_resources,
        "nodes": nodes,
    }


def tool_godot_capture_screenshot(view_mode: str = "helm", frames: int = 45) -> dict[str, Any]:
    """Run tools/mcp_capture_frame.gd to render a 4K frame and dump scene metrics."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    godot_bin = resolve_godot_binary()
    safe_view = (view_mode or "helm").strip().lower()
    safe_frames = max(2, min(int(frames), 600))

    cmd = [
        godot_bin,
        "--path",
        str(WORKSPACE_ROOT),
        "-s",
        "res://tools/mcp_capture_frame.gd",
        "--",
        f"--view={safe_view}",
        f"--frames={safe_frames}",
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        timeout=90,
        encoding="utf-8",
        errors="replace",
    )

    combined_out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    cli_diagnostics = parse_compiler_diagnostics(combined_out)

    scene_state: dict[str, Any] = {}
    if SCENE_STATE_PATH.is_file():
        try:
            scene_state = json.loads(SCENE_STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            scene_state = {"json_parse_error": str(exc)}

    return {
        "status": "ok" if proc.returncode == 0 and LATEST_FRAME_PATH.is_file() else "error",
        "exit_code": proc.returncode,
        "screenshot_res_path": "res://.mcp_captures/latest_frame.png",
        "screenshot_absolute_path": str(LATEST_FRAME_PATH.resolve()),
        "scene_state_res_path": "res://.mcp_captures/scene_state.json",
        "scene_state_absolute_path": str(SCENE_STATE_PATH.resolve()),
        "view_mode": safe_view,
        "frames_settled": safe_frames,
        "compiler_diagnostics": cli_diagnostics,
        "scene_metrics": {
            "viewport_size": scene_state.get("viewport_size", [3840, 2160]),
            "rendering_device": scene_state.get("rendering_device", ""),
            "active_camera": scene_state.get("active_camera", {}),
            "environment": scene_state.get("environment", {}),
            "lights_count": scene_state.get("lights_count", 0),
            "lights": scene_state.get("lights", []),
            "ui_controls": scene_state.get("ui_controls", []),
            "active_nodes_count": scene_state.get("active_nodes_count", 0),
            "runtime_diagnostics": scene_state.get("diagnostics", []),
        },
    }


def tool_godot_inspect_scene_tree(scene_path: str = "res://scenes/overworld.tscn") -> dict[str, Any]:
    """Inspect a .tscn scene hierarchy, attached scripts, and exported properties."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    res_path = to_res_path(scene_path or "res://scenes/overworld.tscn")
    godot_bin = resolve_godot_binary()

    cmd = [
        godot_bin,
        "--headless",
        "--path",
        str(WORKSPACE_ROOT),
        "-s",
        "res://tools/mcp_capture_frame.gd",
        "--",
        f"--inspect-scene={res_path}",
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=45,
            encoding="utf-8",
            errors="replace",
        )
        combined_out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        cli_diagnostics = parse_compiler_diagnostics(combined_out)

        if proc.returncode == 0 and SCENE_TREE_PATH.is_file():
            tree_json = json.loads(SCENE_TREE_PATH.read_text(encoding="utf-8"))
            tree_json["compiler_diagnostics"] = cli_diagnostics
            return tree_json
    except Exception:
        pass

    local_rel = res_path.removeprefix("res://")
    return parse_tscn_static_fallback(WORKSPACE_ROOT / local_rel, res_path)


def tool_godot_check_scripts(script_paths: list[str]) -> dict[str, Any]:
    """Run `godot --headless --check-only` across specified GDScript files."""
    godot_bin = resolve_godot_binary()
    if not script_paths:
        script_paths = ["res://scripts/boat_controller.gd"]

    results: list[dict[str, Any]] = []
    all_passed = True

    for raw_path in script_paths:
        res_path = to_res_path(raw_path)
        cmd = [
            godot_bin,
            "--headless",
            "--path",
            str(WORKSPACE_ROOT),
            "--check-only",
            "-s",
            res_path,
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        diags = parse_compiler_diagnostics(combined)
        passed = proc.returncode == 0 and not any(d["severity"] == "error" for d in diags)
        if not passed:
            all_passed = False

        results.append(
            {
                "script": res_path,
                "passed": passed,
                "exit_code": proc.returncode,
                "diagnostics": diags,
                "raw_output": combined,
            }
        )

    return {
        "all_passed": all_passed,
        "checked_count": len(results),
        "results": results,
    }


TOOLS_MANIFEST: list[dict[str, Any]] = [
    {
        "name": "godot_capture_screenshot",
        "description": (
            "Launches Godot 4.7 with tools/mcp_capture_frame.gd, waits for volumetric fog, "
            "Gerstner ocean waves, and UI to settle, saves a 4K screenshot to "
            "res://.mcp_captures/latest_frame.png, and dumps live scene/lighting telemetry to "
            "res://.mcp_captures/scene_state.json."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "view_mode": {
                    "type": "string",
                    "description": "Camera preset: 'helm', 'first_person', 'harbor_ui', or 'bow_light'.",
                    "enum": ["helm", "first_person", "harbor_ui", "bow_light"],
                    "default": "helm",
                },
                "frames": {
                    "type": "integer",
                    "description": "Number of frames to wait before capturing (default: 45).",
                    "default": 45,
                },
            },
        },
    },
    {
        "name": "godot_inspect_scene_tree",
        "description": (
            "Instantiates and inspects a Godot scene (.tscn), returning the full node hierarchy, "
            "attached script paths, transforms, light energies, and exported properties as JSON."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scene_path": {
                    "type": "string",
                    "description": "Resource path to the scene (e.g. 'res://scenes/overworld.tscn').",
                    "default": "res://scenes/overworld.tscn",
                }
            },
            "required": ["scene_path"],
        },
    },
    {
        "name": "godot_check_scripts",
        "description": (
            "Runs `godot --headless --path . --check-only -s <script>` across the specified "
            "GDScript paths and returns structured compiler/type diagnostics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of GDScript paths (e.g. ['res://scripts/boat_controller.gd']).",
                }
            },
            "required": ["script_paths"],
        },
    },
]


def handle_rpc_request(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Process a single JSON-RPC 2.0 request or notification."""
    method = msg.get("method", "")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications have no id and expect no response
    if req_id is None:
        return None

    if method == "initialize":
        client_proto = params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_proto,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS_MANIFEST},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            if tool_name == "godot_capture_screenshot":
                view_mode = str(args.get("view_mode", "helm"))
                frames = int(args.get("frames", 45))
                payload = tool_godot_capture_screenshot(view_mode=view_mode, frames=frames)
            elif tool_name == "godot_inspect_scene_tree":
                scene_path = str(args.get("scene_path", "res://scenes/overworld.tscn"))
                payload = tool_godot_inspect_scene_tree(scene_path=scene_path)
            elif tool_name == "godot_check_scripts":
                script_paths = args.get("script_paths", [])
                if isinstance(script_paths, str):
                    script_paths = [script_paths]
                payload = tool_godot_check_scripts(script_paths=list(script_paths))
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(payload, indent=2),
                        }
                    ],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"error": str(exc)}, indent=2),
                        }
                    ],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    }


def serve_stdio() -> None:
    """Main JSON-RPC 2.0 loop supporting both newline-delimited JSON and Content-Length framing."""
    stdin_buf = sys.stdin.buffer
    stdout_buf = sys.stdout.buffer

    while True:
        first_line = stdin_buf.readline()
        if not first_line:
            break

        stripped = first_line.strip()
        if not stripped:
            continue

        use_content_length = False
        raw_json_bytes = b""

        if stripped.lower().startswith(b"content-length:"):
            use_content_length = True
            content_length = int(stripped.split(b":", 1)[1].strip())
            while True:
                header_line = stdin_buf.readline()
                if not header_line or header_line.strip() == b"":
                    break
            raw_json_bytes = stdin_buf.read(content_length)
        else:
            raw_json_bytes = stripped

        try:
            msg = json.loads(raw_json_bytes.decode("utf-8"))
        except Exception as parse_err:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {parse_err}"},
            }
            out_bytes = (json.dumps(err_resp) + "\n").encode("utf-8")
            stdout_buf.write(out_bytes)
            stdout_buf.flush()
            continue

        resp = handle_rpc_request(msg)
        if resp is not None:
            resp_str = json.dumps(resp)
            if use_content_length:
                body = resp_str.encode("utf-8")
                header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
                stdout_buf.write(header + body)
            else:
                stdout_buf.write((resp_str + "\n").encode("utf-8"))
            stdout_buf.flush()


if __name__ == "__main__":
    serve_stdio()
