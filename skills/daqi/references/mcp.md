# MCP interface / MCP 接口

`skills/daqi/scripts/daqi_mcp.py` 把营地的同一套逻辑暴露成 MCP stdio server——一份达奇的大脑，服务所有支持 MCP 的宿主。

## 运行

```sh
python3 <skill-dir>/scripts/daqi_mcp.py --store ~/.daqi
```

工具（v1）：

| 工具 | 动作 | 写 store？ |
|---|---|---|
| `daqi_record` | 记一条情报/点子进账本（去重） | **是**（唯一写工具，用户显式调用） |
| `daqi_camp` | 渲染营地页 + 清点摘要 | 否（只写生成物 camp.html） |
| `daqi_status` | 马厩总览 / 某项目 NOW 主线 | 否 |
| `daqi_scan` | 候选列表 / 选中深读提炼（shallow/deep） | 否（方案 + token，提交留在聊天） |
| `daqi_organize_preview` | 一键整理 move plan + token | 否（执行留在聊天） |

## 宿主配置

- **Claude Code / Claude Desktop**：`claude mcp add daqi -- python3 <skill-dir>/scripts/daqi_mcp.py --store ~/.daqi`（Desktop 等价于 `claude_desktop_config.json` 里加 `mcpServers.daqi` 条目）。
- **Cursor**：`.cursor/mcp.json` 注册同样的 stdio 命令。
- **DSH / WorkBuddy**：把下面的实例写进 profile 的 `cordis.patch.yml`（本机已写入 `~/.dsh/profiles/web/cordis.patch.yml`，重启 DSH 生效），工具注册为 `mcp__daqi__<工具名>`：

  ```yaml
  [
    {
      name: mcp-client,
      config: {
        transport: stdio,
        serverName: daqi,
        command: python3,
        args: [
          /Users/pakco/.agents/skills/daqi/scripts/daqi_mcp.py,
          --store,
          /Users/pakco/.daqi,
        ],
      },
    },
  ]
  ```
- 其它宿主：任何支持 MCP stdio 的客户端都能直接连。

## Codex 实测记录（2026-08-15，已验收）

注册：`~/.codex/config.toml` 的 `[mcp_servers.daqi]`（command = `python3`，args = 脚本路径 + `--store ~/.daqi`）。

验证命令（注意 Git 信任检查）：

```sh
codex mcp list                       # 应看到 daqi enabled
codex exec --skip-git-repo-check "用 daqi_status 看一下营地，再报告"
```

直接在未受信任目录跑 `codex exec` 会被 `Not inside a trusted directory and --skip-git-repo-check was not specified.` 拦住——这是 Codex 的工作区信任检查，不是 daqi 的问题；要么加 `--skip-git-repo-check`，要么在受信任的 Git 工作区执行。

已实测通过：`mcp: daqi/daqi_status started → completed`，exit 0；`daqi_status` 只读，不修改任何 store。

## 诚实边界

- stdio 服务只在发起它的那台机器上可用；云/沙箱宿主连不到本机营地。
- 扫描候选的**提交**、一键整理的**执行**、单条**删除**不在 MCP 里——这些写动作必须由用户在聊天里确认后走 token 流程（或营地页二次确认），MCP 只负责读和提方案。
- `daqi_record` 是唯一例外：它是用户显式调用的记账工具，写的就是用户自己说出口的那一条。
- 永不读对话记录；扫描只读会话 cwd + 时间戳。
