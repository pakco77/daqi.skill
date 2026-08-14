"""daqi MCP server contract tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "daqi" / "scripts" / "daqi_mcp.py"

POOL = """---
schema_version: 3
---

# POOL —— 营地账本

## 当前情报、点子与计划

<空>
"""

SHELF = """# SHELF —— 马厩

## 🟢 在跑

| 项目 | 地址 | 最后活跃 | Agent |
|---|---|---|---|
| testproj | {proj} | 2026-08-14 | DSH |
"""


class Client:
    def __init__(self, store: Path):
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--store", str(store)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
        )
        self.msg_id = 0

    def send(self, method: str, params: dict | None = None, expect_id: bool = True) -> dict | None:
        payload = {"jsonrpc": "2.0", "method": method}
        if expect_id:
            self.msg_id += 1
            payload["id"] = self.msg_id
        if params is not None:
            payload["params"] = params
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        if not expect_id:
            return None
        line = self.proc.stdout.readline()
        assert line, "server closed before responding"
        return json.loads(line)

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.terminate()
        self.proc.wait(timeout=10)


def check_handshake_and_camp() -> None:
    store = Path(tempfile.mkdtemp(prefix="daqi-mcp-"))
    proj = store / "proj"
    proj.mkdir()
    (store / "POOL.md").write_text(POOL)
    (store / "SHELF.md").write_text(SHELF.format(proj=proj))
    client = Client(store)
    try:
        init = client.send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        assert init["result"]["protocolVersion"] == "2024-11-05"
        assert init["result"]["serverInfo"]["name"] == "daqi"
        client.send("notifications/initialized", expect_id=False)

        listed = client.send("tools/list")
        names = {t["name"] for t in listed["result"]["tools"]}
        assert {"daqi_record", "daqi_camp", "daqi_status", "daqi_scan", "daqi_organize_preview"} <= names

        camp = client.send("tools/call", {"name": "daqi_camp", "arguments": {}})
        text = camp["result"]["content"][0]["text"]
        assert "营地清点完毕" in text and (store / "camp.html").exists()

        # record writes exactly one entry; duplicate is refused
        pool_bytes = (store / "POOL.md").read_bytes()
        rec = client.send("tools/call", {"name": "daqi_record", "arguments": {"stage": "idea", "text": "跨 Agent 复盘器"}})
        assert "点子王" in rec["result"]["content"][0]["text"]
        assert "阶段：点子｜跨 Agent 复盘器" in (store / "POOL.md").read_text()
        dup = client.send("tools/call", {"name": "daqi_record", "arguments": {"stage": "idea", "text": "跨 Agent 复盘器"}})
        assert "已经有这条" in dup["result"]["content"][0]["text"]
        assert (store / "POOL.md").read_text().count("跨 Agent 复盘器") == 1

        bad = client.send("tools/call", {"name": "daqi_record", "arguments": {"stage": "nope", "text": "x"}})
        assert bad["result"]["isError"] is True

        # camp/status are read-only for SHELF/POOL
        shelf_bytes = (store / "SHELF.md").read_bytes()
        status = client.send("tools/call", {"name": "daqi_status", "arguments": {}})
        assert "testproj" in status["result"]["content"][0]["text"]
        assert (store / "SHELF.md").read_bytes() == shelf_bytes

        org = client.send("tools/call", {"name": "daqi_organize_preview", "arguments": {"project": "testproj"}})
        assert "token:" in org["result"]["content"][0]["text"]
    finally:
        client.close()


def check_unknown_method() -> None:
    store = Path(tempfile.mkdtemp(prefix="daqi-mcp-"))
    (store / "POOL.md").write_text(POOL)
    (store / "SHELF.md").write_text(SHELF.format(proj=store))
    client = Client(store)
    try:
        client.send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        resp = client.send("nope")
        assert "error" in resp
    finally:
        client.close()


def main() -> None:
    check_handshake_and_camp()
    check_unknown_method()
    print("PASS: mcp handshake, tools, record/dedupe, readonly, errors")


if __name__ == "__main__":
    main()
