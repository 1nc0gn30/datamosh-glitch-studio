"""Tests for FastMCP JSON-RPC 2.0 protocol and stdio tools."""

import base64
import json
import pytest
from datamosh_glitch_studio.mcp_server import MCPServer
from datamosh_glitch_studio.frame_io import ImageFrame


def test_mcp_initialize():
    server = MCPServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    res_str = server.handle_request(req)
    res = json.loads(res_str)
    assert res["id"] == 1
    assert "serverInfo" in res["result"]
    assert res["result"]["serverInfo"]["name"] == "datamosh-glitch-studio"


def test_mcp_tools_list():
    server = MCPServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    res = json.loads(server.handle_request(req))
    tools = res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "datamosh_apply" in tool_names
    assert "datamosh_generate_sequence" in tool_names
    assert "datamosh_presets" in tool_names
    assert "datamosh_corrupt_bytes" in tool_names
    assert "datamosh_diagnostics" in tool_names


def test_mcp_tool_datamosh_apply():
    server = MCPServer()
    # Test card generation with datamosh
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "datamosh_apply",
            "arguments": {
                "preset": "cyberpunk_vcr",
                "width": 64,
                "height": 48,
                "seed": 42
            }
        }
    })
    res = json.loads(server.handle_request(req))
    content_text = res["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert data["status"] == "success"
    assert "image_base64" in data
    assert data["width"] == 64
    assert data["height"] == 48


def test_mcp_tool_datamosh_sequence():
    server = MCPServer()
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "datamosh_generate_sequence",
            "arguments": {
                "frame_count": 3,
                "preset": "h264_iframe_drop"
            }
        }
    })
    res = json.loads(server.handle_request(req))
    data = json.loads(res["result"]["content"][0]["text"])
    assert data["status"] == "success"
    assert len(data["frames_base64"]) == 3


def test_mcp_tool_datamosh_corrupt():
    server = MCPServer()
    raw = b"HEADER1234567890TESTDATA" * 5
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "datamosh_corrupt_bytes",
            "arguments": {
                "data_base64": base64.b64encode(raw).decode("ascii"),
                "rate": 0.1,
                "header_skip": 10
            }
        }
    })
    res = json.loads(server.handle_request(req))
    data = json.loads(res["result"]["content"][0]["text"])
    assert data["status"] == "success"
    assert "corrupted_base64" in data


def test_mcp_diagnostics():
    server = MCPServer()
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "datamosh_diagnostics",
            "arguments": {}
        }
    })
    res = json.loads(server.handle_request(req))
    data = json.loads(res["result"]["content"][0]["text"])
    assert data["status"] == "HEALTHY"
    assert data["zero_dependencies"] is True
