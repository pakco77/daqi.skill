#!/usr/bin/env python3
"""daqi 本地小桥：让静态营地页直接把大脑 API key 写进 <store>/config.json。

key 只落本地文件（0600），永不进入聊天或任何网络请求。营地页的「设置」
面板通过 POST /set-key 调它；没有桥时页面会提示启动。
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def config_path(store: Path) -> Path:
    return store / "config.json"


class Handler(BaseHTTPRequestHandler):
    store: Path = Path.home() / ".daqi"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/ping":
            self._send(200, {"ok": True, "store": str(self.store)})
        else:
            self._send(404, {"ok": False})

    def do_POST(self) -> None:
        if self.path != "/set-key":
            self._send(404, {"ok": False})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        key = str(payload.get("api_key", "")).strip()
        if not key:
            self._send(400, {"ok": False, "error": "empty key"})
            return
        path = config_path(self.store)
        cfg: dict = {}
        if path.is_file():
            try:
                cfg = json.loads(path.read_text())
            except json.JSONDecodeError:
                cfg = {}
        llm = cfg.setdefault("llm", {})
        llm["api_key"] = key
        llm.setdefault("base_url", "https://api.deepseek.com")
        llm.setdefault("model", "DeepSeek-v4-flash0731")
        tmp = path.with_suffix(".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        self._send(200, {"ok": True, "model": llm["model"], "base_url": llm["base_url"]})

    def log_message(self, *args: object) -> None:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="daqi 本地小桥（营地页设置面板的写 key 通道）")
    ap.add_argument("--store", default=os.environ.get("DAQI_HOME") or str(Path.home() / ".daqi"))
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args(argv)
    Handler.store = Path(args.store)
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"daqi bridge: http://127.0.0.1:{args.port} → {config_path(Handler.store)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
