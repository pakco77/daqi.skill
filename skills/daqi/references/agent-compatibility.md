# Agent compatibility

Daqi follows the open [Agent Skills folder contract](https://agentskills.io/specification). One canonical `skills/daqi/` implementation is shared across hosts; installation paths and lifecycle hooks remain host-specific.

Daqi is a rename of the mishu-era implementation of the same mechanism (SELF/SHELF/POOL, growth hooks, exact-root Codex continuity). The evidence rows below were recorded against the mishu build; after the rename, re-run the discovery and trigger checks once per host before claiming the renamed skill verified.

## Recommended install

```sh
npx skills add pakco77/daqi.skill
```

The interactive installer lets the user select `daqi`, `context-fold`, and `project-fold`, then one or more detected hosts. Use `npx skills add pakco77/daqi.skill --list` for a discovery-only check. Do not recommend `--agent '*'`: it installs into every directory known to the CLI, whether that client is used or not.

For unattended installation, use an exact identifier from the [`skills` CLI supported-agent table](https://github.com/vercel-labs/skills#supported-agents). If the installer does not support a host, import the repository through its documented Skills interface or copy all three complete Skill folders into its documented Skill directory.

## What “supported” means

Manual Skill compatibility evidence has four levels:

1. **Installed** — the complete Skill folder reached the host's documented directory.
2. **Discovered** — the host listed or loaded `daqi`.
3. **Triggered** — an explicit invocation ran Daqi's instructions.
4. **Store read** — the host read the shared `DAQI_HOME` / `~/.daqi` store.

An installer target proves only level 1. Automatic continuity has four additional, separate proof layers: **configured** (the exact project hook bundle exists), **trusted** (the user reviewed it in the host UI), **dispatched** (the real host emitted the lifecycle event), and **checkpointed** (the real host restored or updated canonical NOW). Never collapse one layer into another.

## Current host status

| Host named by users | CLI identifier / route | Current evidence | Honest status |
|---|---|---|---|
| Codex CLI | `codex` | Manual workflow verified. On `codex-cli 0.147.0-alpha.6.5` / macOS 27.0, a real temporary project was configured and reviewed in Codex `/hooks`; SessionStart restored NOW without tool reads, Stop wrote an evidence-backed update without prompting, an exact-root move/copy invalidated enrollment, and two real concurrent Agents produced one winner plus one reported conflict without overwrite. | **End-to-end verified for the listed main path after setup and hook review**; restricted permission modes and malformed/missing receipts have deterministic adapter coverage only; `status` still reports `CONFIGURED_NEEDS_HOOKS_REVIEW` because trust is observable only in Codex UI |
| Codex Desktop | bundled Codex project hooks | No independent real-host run is recorded | **Compatibility candidate**; do not inherit the CLI end-to-end claim |
| Claude Code | `claude-code` | Installed and discovered; bundled SessionStart adapter exists | **Partially verified**; real trigger and store read remain |
| Hermes Agent | `hermes-agent` | Installed and listed by `hermes skills list` | **Partially verified**; real trigger and store read remain |
| Kimi Code CLI | `kimi-code-cli` | Isolated installer path verified | **Install-compatible**; discovery, trigger, and store read remain |
| Cursor | `cursor` | Isolated installer path verified; official basic Agent Skills support | **Contract-compatible candidate**; discovery, trigger, and store read remain |
| Trae / Trae CN | `trae` / `trae-cn` | Isolated Trae installer path verified; both are official targets | **Contract-compatible candidates**; discovery, trigger, and store read remain |
| Qoder / Qoder CN | `qoder` / `qoder-cn` | Isolated Qoder installer path verified; both are official targets | **Contract-compatible candidates**; discovery, trigger, and store read remain |
| Pi | `pi` | Isolated installer path verified; official basic Agent Skills support | **Contract-compatible candidate**; discovery, trigger, and store read remain |
| Grok Build | `grok` | Isolated installer path verified | **Install-compatible candidate**; discovery, trigger, and store read remain |
| OpenClaw | `openclaw` | Isolated installer path verified; official basic Agent Skills support | **Contract-compatible candidate**; discovery, trigger, and store read remain |
| WorkBuddy | Copy complete folders to `~/.workbuddy/skills/`; do not rely on `npx skills -g` for PromptScript | Manual install, dynamic discovery, explicit `达奇 项目进度` trigger, fixture read, and real `~/.daqi` read verified | **End-to-end verified for the manual workflow**; no native lifecycle claim |
| “QoderWork” | Confirm whether this means Qoder, Qoder CN, or another product | No exact current CLI identifier | **Ambiguous; do not claim support yet** |
| “QClaw” | Confirm whether this means OpenClaw or another product | No exact current CLI identifier | **Ambiguous; OpenClaw is installable, QClaw is not proven** |

Host documentation: [Claude Code](https://code.claude.com/docs/en/skills), [Codex](https://developers.openai.com/codex/skills), [Cursor](https://cursor.com/docs/context/skills), [Kimi Code CLI](https://moonshotai.github.io/kimi-code/en/customization/skills), [Trae](https://docs.trae.ai/ide/skills), [Qoder](https://docs.qoder.com/cli/Skills), [Pi](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md), [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills), and [OpenClaw](https://docs.openclaw.ai/tools/skills).

WorkBuddy-specific live evidence: its Skill tool dynamically discovered and loaded `daqi` after the three complete folders were copied from `~/.agents/skills/` to `~/.workbuddy/skills/`; no new session was required. `达奇 项目进度` then triggered the Skill and read both a redacted fixture and the real default store. The preceding `npx skills ... -g` attempt had written to `~/.agents/skills/` and reported `PromptScript does not support global skill installation`, so that route must not be reported as a successful WorkBuddy install. This test also exposed two portability defects now covered by the contract: never substitute another store when an explicit path is missing, and never turn default status into a full dashboard or moralizing coaching.

## Shared-store boundary

Daqi's default global store is `~/.daqi`, or the directory explicitly set by `DAQI_HOME`. Cross-Agent continuity therefore works when the clients run as the same local user or are deliberately pointed at the same accessible store. A cloud or sandboxed Agent that cannot read that path cannot share the local stores merely because its Skill was installed.

Every host must preserve:

- first-run management-language choice plus an optional, confirmed default home for new project material;
- SELF as a compact, non-sensitive profile;
- POOL signal/seed/sprout deduplication, schema compatibility, and explicit project promotion;
- one canonical project hot state (`NOW.md` for V1); HANDOFF is legacy import only and SHELF is metadata-only;
- user confirmation before SHELF reconstruction writes or folder moves;
- no claim of automatic hooks without a host-specific live test.

The bundled SHELF scanner currently understands Claude Code and Codex metadata only. Other hosts remain usable through explicit start, growth, status, and wrap-up actions, but their session history must not be guessed or advertised as automatically reconstructable. Codex automatic continuity is project-local and exact-root bound; copying or moving a project does not carry live enrollment, and configuring hook JSON is not itself proof that the user trusted it.
