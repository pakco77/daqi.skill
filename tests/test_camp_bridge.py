"""camp_bridge scan/commit contract tests (agent-brain fallback)."""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "skills" / "daqi" / "scripts" / "camp_bridge.py"

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
"""

FAKE_AGENT = """import json
print(json.dumps([{"type": "idea", "title": "FakeBrain 点子", "line": "来自本机 Agent 的提炼", "why_now": "test", "evidence": "test", "probe": "test"}]))
"""


class Bridge:
    def __init__(self, store: Path, home: Path, port: int = 8793):
        self.proc = subprocess.Popen(
            [sys.executable, str(BRIDGE), "--store", str(store), "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=dict(os.environ, HOME=str(home)),
        )
        self.base = f"http://127.0.0.1:{port}"
        time.sleep(1)

    def post(self, path: str, payload: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())

    def close(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=10)


def check_scan_pipeline_with_agent_brain() -> None:
    base = Path(tempfile.mkdtemp(prefix="daqi-bridge-scan-"))
    store = base / "store"
    ws = base / "ws"
    store.mkdir()
    ws.mkdir()
    (store / "POOL.md").write_text(POOL)
    (store / "SHELF.md").write_text(SHELF)
    (ws / "README.md").write_text("# 测试工作区\n\n有点子要挖。\n")
    fake = base / "fake_agent.py"
    fake.write_text(FAKE_AGENT)
    (store / "config.json").write_text(json.dumps({
        "agent": {"command": sys.executable, "args": [str(fake)]},
        "llm": {"base_url": "https://api.deepseek.com", "model": "DeepSeek-v4-flash0731", "api_key": ""},
    }))

    home = base / "home"
    (home / ".claude/projects/enc").mkdir(parents=True)
    (home / ".claude/projects/enc/a.jsonl").write_text(
        f'{{"cwd":"{ws}","timestamp":"2026-08-15T10:00:00Z"}}\n'
    )
    bridge = Bridge(store, home)
    try:
        code, ping = bridge.post("/ping", {})
        assert code == 200 and ping["brain"].startswith("agent:"), ping

        code, scanned = bridge.post("/scan", {})
        assert code == 200 and scanned["candidates"] >= 1, scanned

        code, read = bridge.post("/scan", {"select": str(ws), "depth": "deep"})
        assert code == 200 and read["proposals"] >= 1, read

        state = json.loads((store / ".scan-state.json").read_text())
        token = state["token"]
        assert any("FakeBrain" in p.get("title", "") for p in state["proposals"])

        code, committed = bridge.post("/scan-commit", {"token": token})
        assert code == 200 and committed["pool_entries"] >= 1, committed
        assert "FakeBrain 点子" in (store / "POOL.md").read_text()

        code, bad = bridge.post("/scan-commit", {"token": "deadbeef"})
        assert code == 409
    finally:
        bridge.close()


def main() -> None:
    check_scan_pipeline_with_agent_brain()
    print("PASS: bridge scan pipeline with installed-agent brain, token commit, conflict")


if __name__ == "__main__":
    main()
