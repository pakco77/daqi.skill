#!/usr/bin/env python3
"""daqi 本地小桥：让静态营地页直接把大脑 API key 写进 <store>/config.json。

key 只落本地文件（0600），永不进入聊天或任何网络请求。营地页的「设置」
面板通过 POST /set-key 调它；没有桥时页面会提示启动。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
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

    def _ping(self) -> None:
            cfg = {}
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from camp_scan import agent_command, load_config

                cfg = load_config(self.store)
                agent = agent_command() or str((cfg.get("agent") or {}).get("command", ""))
            except Exception:
                agent = ""
            has_key = bool(str((cfg.get("llm") or {}).get("api_key", "")).strip())
            self._send(200, {"ok": True, "store": str(self.store),
                             "brain": "deepseek" if has_key else ("agent:" + agent if agent else "shallow")})

    def do_GET(self) -> None:
        if self.path == "/ping":
            self._ping()
            return
        self._send(404, {"ok": False})

    def do_POST(self) -> None:
        if self.path == "/ping":
            self._ping()
            return
        if self.path == "/delete":
            self._delete()
            return
        if self.path == "/deep-dive":
            self._deep_dive()
            return
        if self.path == "/scan":
            self._scan()
            return
        if self.path == "/scan-commit":
            self._scan_commit()
            return
        if self.path == "/stage":
            self._stage()
            return
        if self.path == "/link":
            self._link()
            return
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

    def _delete(self) -> None:
        """Remove one exact line from POOL.md or SHELF.md, then re-render camp.html."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        file = str(payload.get("file", ""))
        line = str(payload.get("line", ""))
        if file not in ("POOL.md", "SHELF.md") or not line:
            self._send(400, {"ok": False, "error": "bad target"})
            return
        path = self.store / file
        if not path.is_file():
            self._send(404, {"ok": False, "error": "missing file"})
            return
        lines = path.read_text().splitlines()
        if line not in lines:
            self._send(404, {"ok": False, "error": "line not found"})
            return
        lines.remove(line)
        path.write_text("\n".join(lines).rstrip("\n") + "\n")
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from camp_status import build_page

            (self.store / "camp.html").write_text(build_page(self.store))
        except Exception as error:  # delete succeeded; page refresh is best-effort
            print(f"warning: camp refresh failed: {error}", file=sys.stderr)
        self._send(200, {"ok": True})

    def _scan(self) -> None:
        """Drive the scan pipeline server-side: candidates, or read+distill on select."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import camp_scan

            select = str(payload.get("select", "")).strip()
            depth = str(payload.get("depth", "shallow"))
            if depth not in ("shallow", "deep"):
                depth = "shallow"
            if not select:
                camp_scan.render_camp_page(self.store)
                candidates = camp_scan.scan_metadata(self.store)
                camp_scan.write_state(self.store, {
                    "phase": "select", "percent": 30,
                    "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "items": [], "candidates": candidates,
                })
                camp_scan.render_camp_page(self.store)
                self._send(200, {"ok": True, "candidates": len(candidates)})
                return
            proposals, token = camp_scan.scan_flow(self.store, select, depth)
            self._send(200, {"ok": True, "proposals": len(proposals), "token": token})
        except Exception as error:
            self._send(500, {"ok": False, "error": str(error)})

    def _link(self) -> None:
        """把点子行挂到一个痛点（第 6 段 = 关联痛点）。"""
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        line = str(payload.get("line", ""))
        pain = str(payload.get("pain", "")).strip()
        path = self.store / "POOL.md"
        text = path.read_text()
        if not pain or line not in text:
            self._send(404, {"ok": False, "error": "line not found"})
            return
        parts = re.split(r"[｜|]", line)
        # 阶段：X 在第 0 段；重组成 6 段（text/why/evidence/probe/link/last_seen）
        body = parts[1:] if len(parts) > 1 else []
        while len(body) < 5:
            body.append("—")
        body[4] = pain
        new_line = parts[0] + "｜" + "｜".join(body)
        path.write_text(text.replace(line, new_line, 1))
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from camp_status import build_page

            (self.store / "camp.html").write_text(build_page(self.store))
        except Exception as error:
            print(f"warning: camp refresh failed: {error}", file=sys.stderr)
        self._send(200, {"ok": True})

    def _stage(self) -> None:
        """把账本里一条的阶段改成 idea/plan（主链流转）。"""
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        file = str(payload.get("file", ""))
        line = str(payload.get("line", ""))
        stage = str(payload.get("stage", ""))
        label = {"idea": "点子"}.get(stage, "")
        if file != "POOL.md" or not line or not label:
            self._send(400, {"ok": False, "error": "bad target"})
            return
        path = self.store / file
        text = path.read_text()
        if line not in text:
            self._send(404, {"ok": False, "error": "line not found"})
            return
        new_line = re.sub(r"^(-\s*阶段[:：]\s*)(痛点|点子)(?=[｜|])", rf"\g<1>{label}", line)
        path.write_text(text.replace(line, new_line, 1))
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from camp_status import build_page

            (self.store / "camp.html").write_text(build_page(self.store))
        except Exception as error:
            print(f"warning: camp refresh failed: {error}", file=sys.stderr)
        self._send(200, {"ok": True})

    def _scan_commit(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import camp_scan

            keep = payload.get("keep")
            if isinstance(keep, list):
                keep_indices = [int(v) for v in keep if str(v).isdigit() and int(v) >= 0]
            else:
                keep_indices = None
            wrote, shelf_added = camp_scan.commit_scan(self.store, str(payload.get("token", "")), keep_indices)
            if wrote < 0:
                self._send(409, {"ok": False, "error": "token 不匹配"})
                return
            self._send(200, {"ok": True, "pool_entries": wrote, "shelf_added": shelf_added})
        except Exception as error:
            self._send(500, {"ok": False, "error": str(error)})

    def _deep_dive(self) -> None:
        """Read one project's context deeper and distill findings; display only."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        root = Path(str(payload.get("path", "")))
        if not root.is_dir():
            self._send(404, {"ok": False, "error": "project dir not found"})
            return
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from camp_scan import call_brain, heuristic, load_config, read_context

            previews = read_context(root, 12000)
            cfg = load_config(self.store)
            findings = call_brain(cfg, previews) if cfg["llm"].get("api_key") else []
            if not findings:
                findings = heuristic(root, previews)
            lines = []
            if previews:
                files = "、".join(p["file"] for p in previews[:8])
                lines.append(f"读了 {len(previews)} 份上下文（{files}）：")
            for f in findings:
                lines.append(f"[{f.get('type')}] {f.get('title')} — {(f.get('line') or '')[:120]}")
            if not lines:
                lines.append("没有读到上下文文件。")
            text = "\n".join(lines) + "\n（看完就完了，账本没动。）"
            self._send(200, {"ok": True, "text": text})
        except Exception as error:
            self._send(500, {"ok": False, "error": str(error)})

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
