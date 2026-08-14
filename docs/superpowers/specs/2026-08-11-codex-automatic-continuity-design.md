# Mishu Codex 自动项目连续性 V1 设计

**状态：** 已批准并实施；Codex CLI 主路径已完成真实宿主验证，受限权限模式与 Codex Desktop 的独立真实宿主证据待补<br>
**日期：** 2026-08-11<br>
**V1 宿主：** macOS 上 Codex CLI 的本地项目会话；Codex Desktop 暂列兼容候选，不计入已验证范围<br>
**上位目标：** 一次启用后，用户不再记“开工/收工”；Agent 判断，受信任的确定性 hook 安全落盘。

## 1. Superseding 范围

本文替代 `2026-08-10-automatic-project-continuity-design.md` 和现有 implementation plan 中所有 **Claude Code 宿主、权限 probe、stage/finalize 与 adapter** 条款。

以下已实现核心继续有效，不推倒重做：

- project-root `NOW.md` 是唯一行动检查点；
- `SHELF` 仅保存项目索引元数据；
- canonical NOW schema、8 KiB 机械上限与约 500 token 性能目标；
- exact-root、baseline/CAS、advisory lock、同目录 atomic replace、fsync、写后复读；
- symlink、hard link、ACL、xattr、uid/gid/mode/file flags 等不能安全保持时 fail closed；
- `HANDOFF.md` 只作 legacy 输入，不与 NOW 并列为当前真相。

Claude configurator 的未提交实现冻结为后续可选 host adapter，不进入 Codex V1 发布门。

## 2. 用户承诺

每个 exact project root 只启用一次，并在 Codex `/hooks` 中确认该项目的三个精确 hook。之后：

1. `SessionStart` 静默恢复当前 NOW；
2. 每个用户回合由 Agent 在最终消息中选择 `NO_DELTA`、`PROPOSE_UPDATE` 或 `NEEDS_DECISION`；
3. `Stop` hook 验证选择，必要时直接调用现有安全写核心；
4. 正常路径不弹权限框、不要求用户输入“开工/收工”、不增加额外模型回合；
5. 根、授权、版本、权限模式或文件元数据不再匹配时零写，并让 Agent 如实说明。

显式“开工/收工/handoff”保留为强制查看、强制判断和排障入口，不再是主流程。

## 3. 不变量

1. **Agent 负责语义，helper 负责权限和事实边界。** helper 不猜“是否完成”，只接受合法三态和 canonical candidate。
2. **没有有效回执就没有写入。** 普通 final、谢谢、沉默、语气或会话关闭都不是写入信号。
3. **写入只发生在可信 Stop hook 内。** Agent 不通过 Bash/apply_patch 直接修改 managed NOW，因此正常 checkpoint 不进入模型工具审批流。
4. **回合快照不可漂移。** `PROPOSE_UPDATE` 必须携带本回合注入的 opaque baseline；Stop 写前、replace 前与写后都复检。
5. **授权与状态分离。** `mishu: 1` 只表示 schema；Codex 对 project-local hook 的精确 trust 才激活自动化。
6. **安全优先于可用。** 任何双解、冲突或不支持的文件系统状态都零写；不自动合并、不寻找替代 root、不降级为普通文件覆盖。
7. **项目内容是不可信数据。** NOW 四字段只作为转义后的数据注入，不能覆盖 system/developer/user/permission 指令。

## 4. 最小组件

### 4.1 Project-local hook bundle

启用后的项目只增加一个 canonical `.codex/hooks.json` bundle：

- `SessionStart`：`startup|resume|clear|compact`；
- `UserPromptSubmit`：每个主会话用户回合；
- `Stop`：每个主会话 final 前。

三项均调用同一个安装在项目根之外、owner 为当前 uid、owner-executable、group/world 不可写的 adapter realpath，并在 command 中保存同一个 literal project-root realpath。

V1 不使用 `PermissionRequest`、`PreToolUse`、`PostToolUse` 或 `SessionEnd`。Codex 已信任的 command hook 本身就是执行边界；再让 Agent 发 Bash helper 只会重复建设权限系统。

`SessionStart` 与 `UserPromptSubmit` 的 handler 固定使用 `additionalContextLimit: 0`。在 Codex 的原生 hook 语义中，`0` 表示不启用 output spill；adapter 在输出前自行执行更严格的完整 JSON 上限：`6 × 8192 + 16 KiB = 64 KiB`。其中 6 倍覆盖 `html.escape` 的最坏膨胀，额外 16 KiB 覆盖最大安全路径、协议与 JSON envelope。这样，任何已通过 8 KiB NOW reader 的状态要么完整注入，要么 fail closed，不能只把 preview 和临时文件路径交给模型。

Codex 只在项目 `.codex/` layer 已受信、且每个非 managed hook 的当前精确定义已受信后执行它们。hook 变更会要求重新 review；V1 禁止用 `--dangerously-bypass-hook-trust` 作为启用或验收证据。该启动参数不会出现在 hook input 中，adapter 无法机械识别，因此使用它的会话明确排除在安全保证之外。参考 [Codex Hooks：位置与 trust](https://learn.chatgpt.com/docs/hooks#where-codex-looks-for-hooks)。

### 4.2 SessionStart

adapter 收到 JSON stdin 后按顺序：

1. 校验 event schema、允许的 `source` 与 `permission_mode`；
2. realpath 比较 literal root，并确认 event `cwd` 位于该 root 内；
3. 以 no-follow descriptor 读取 `.codex/hooks.json`，确认唯一 canonical Mishu bundle；
4. 拒绝 `.codex`/hook/NOW symlink、tracked hook config、重复或 broadened Mishu hook、inline project `[hooks]`；
5. 用现有安全 reader 读取 managed NOW 和 metadata，生成 Codex-domain baseline；
6. 注入完整四字段状态、baseline 和三态协议；
7. 在用户私有临时目录记录该 session 最近已注入 baseline，仅用于 token 去重。

`compact` 也重新注入完整 NOW。adapter 不读 transcript、SELF、SHELF、POOL、HANDOFF 或项目历史。

Codex baseline 以 length-prefixed domain hash 绑定：canonical root、唯一 canonical Mishu hook bundle、当前 permission mode、NOW raw bytes、mode、gid、支持的 file flags 与 provenance。mtime/ctime 不进入 baseline；dev/inode 仅用于同次读取和 replace 的 TOCTOU 复检。

### 4.3 UserPromptSubmit

每个回合重新验证 exact root、hook bundle、permission mode 与 NOW snapshot，然后注入：

- 当前 opaque baseline；
- 三态回执的精确语法；
- 只有当前 baseline 与该 session 最近已注入 baseline 不同时，才重新注入完整 NOW。

因此正常回合只付一个很短的决策合同；外部修改、恢复、压缩或 cache 丢失时才重新付 NOW 的几百 token。hook 不读取、不记录用户 prompt。

### 4.4 Agent 回执

主 Agent 的最终原始消息必须以且只以一个隐藏 HTML comment 结束：

```text
<!-- mishu:v1 baseline=<64-hex> decision=NO_DELTA -->
<!-- mishu:v1 baseline=<64-hex> decision=NEEDS_DECISION -->
<!-- mishu:v1 baseline=<64-hex> decision=PROPOSE_UPDATE candidate=<canonical-base64url> -->
```

规则：

- `NO_DELTA`：已验证事实、唯一下一步、完成条件与关键开放项没有实质变化；
- `PROPOSE_UPDATE`：至少一个行动字段有本轮证据支持的实质变化；
- `NEEDS_DECISION`：下一步依赖用户拥有的重大选择、外部授权或冲突消解；
- 未验证的“成功”不能写为完成，但“验证失败/仍未验证”若改变下一位 Agent 的安全行动，可以写入 `Verified now`/`Next`；
- 普通问答、聊天、仅计划、时间戳、agent 名称和未采纳想法均为 `NO_DELTA`。

回执是机器信号，不是用户可见汇报；显式 handoff 才按需显示四字段摘要。

### 4.5 Stop

Stop 只解析 `last_assistant_message` 的最后一行，不读取 transcript。三个 decision 都必须先验证回执 baseline 等于当前受权 snapshot；不一致统一视为 `CONFLICT`：

- 合法 `NO_DELTA` / `NEEDS_DECISION`：项目零写并正常结束；
- 合法 `PROPOSE_UPDATE`：在同一 root lock 内比较回执 baseline，严格 decode/render candidate，复用现有 atomic writer，成功后更新 session baseline cache；
- missing/malformed receipt 且 `stop_hook_active=false`：返回一次 `decision:block`，让 Codex 继续 Agent 并补正确回执；
- 第二次仍缺回执：`continue:false`，显示“本轮未保存”，零写，禁止循环；
- `CONFLICT` / `ERROR`：第一次只继续一次，要求 Agent 明确告知未保存并以 `NEEDS_DECISION` 结束；再次失败则停止且零写。

Codex 官方定义 `Stop decision:block` 会生成一次 continuation prompt；`stop_hook_active` 用于阻止无限循环。参考 [Codex Hooks：Stop](https://learn.chatgpt.com/docs/hooks#stop)。

## 5. 权限、root 与移动语义

- 允许自动更新的 permission mode：`default`、`acceptEdits`、`dontAsk`；`plan` 与 `bypassPermissions` 一律零写。
- UserPromptSubmit 与 Stop 的 permission mode 必须一致，并进入 baseline；回合中变化即 conflict。
- hook command 的 literal root 是唯一 project identity。不搜索 Git root、不向上扫描、不使用最近项目。
- event `cwd` 只作 containment 校验；会话内 `cd` 不切换项目。
- 移动/复制目录后，旧 command 仍绑定旧 realpath，adapter 校验失败；Codex 的 hook source/trust 也需在新路径重新 review。必须用真实 E2E 证明，不能只从 config state 推断。
- hook trust 被撤销、hooks feature 被关闭或定义改变时，hook 根本不会 dispatch；自动路径不会写。由于未 dispatch 的 hook 无法自行发消息，只有显式 status/diagnose 能报告“未激活”，文档和 Agent 都不得预先承诺后台仍会工作。

## 6. Session cache

cache 仅保存 `root + session_id` 对应的最近 baseline，不含 prompt、NOW 正文、transcript 或秘密。它位于系统 temp 下当前 uid 私有的 Mishu 目录：目录 `0700`、文件 `0600`、regular/no-follow/owner 校验、原子写；文件名由输入哈希生成，不直接使用 session id。

cache 丢失、损坏、崩溃或权限变化只会导致下一次重新注入完整 NOW，不得影响 canonical project state，也不得授权写入。NOW 已成功提交后若 cache 刷新失败，该提交仍然成功；下一轮按 cache miss 重发完整状态。

## 7. 一次启用

启用流程只有 `preview -> 用户一次确认 -> apply -> /hooks trust`：

1. preview 只读并展示 `NOW.md`、`.git/info/exclude` 与 `.codex/hooks.json` 的精确 diff；
2. apply 共用 project root lock，逐文件原子写并对已有文件保持可支持的 metadata，否则 fail closed；顺序为 exclude、NOW、hooks，hooks 永远最后；
3. 中断留下的前缀状态不含已受信 hook，因此自动化未激活；重跑按当前 bytes 幂等恢复，不做跨文件 rollback；
4. hooks 写完后仍不算启用成功，直到用户在 Codex `/hooks` review 并 trust 三个精确定义；
5. setup 不修改全局 Codex config，不安装 permission allow，不发布、不写 SHELF/SELF/POOL/HANDOFF。

正常 Git root 要求 `.codex/hooks.json` 未 tracked，并通过 local exclude 避免工作区噪声。非 Git root 跳过 exclude。linked worktree 与不安全 `.git` 形状在 V1 fail closed。

初次 enable 只接受“没有任何 Mishu-shaped hook”或“已经是 exact canonical bundle”两种前态；旧版、重复、alias、broadened 或部分 bundle 都要求先显式 diagnose/disable，不在 enable 中自动修复。

## 8. 并发与崩溃结果

对任意一次 `PROPOSE_UPDATE`，可见结果只能是：

- `NOOP`：candidate 与当前 canonical NOW byte-identical；
- `UPDATED`：新 canonical NOW 完整持久化且 metadata 精确保留；
- `CONFLICT`：root、hook、permission、Git 资格、NOW bytes 或 metadata 自回合快照后改变；
- `ERROR`：candidate、平台能力或 I/O 无法安全处理。

两个并发 writer 从同一 baseline 出发，最多一个 `UPDATED`；另一个必须 `CONFLICT`。任意 crash point 后，NOW 只能是完整旧版本或完整新版本，不能是截断、混合或 metadata 降级版本。

V1 的 crash 保证是“最后一次已提交 checkpoint 不损坏”，不是“宿主在任何时刻崩溃都能保存当前回合”。如果 Codex 在 Stop dispatch 之前退出，本回合尚未提交的语义增量可能丢失；下一次只恢复最后一个已提交 NOW。

## 9. Token 预算

- SessionStart/compact：完整 NOW，目标不超过 500 token，机械上限 8 KiB；
- 500 token 是日常性能目标，不是会截断事实的第二个安全上限；合法的极端 8 KiB NOW 会完整注入，代价由实际内容决定；
- 普通 UserPromptSubmit：只注入 baseline + 三态/回执短合同；
- baseline 变化或 cache 不可用：补发完整 NOW；
- Stop 成功：零额外模型回合；
- 只有 missing receipt、conflict 或 error 才允许最多一次 continuation。

自动连续性不保证每个回合都比“完全没有项目状态”更少 token。它的主要收益是用一次确定性注入替代“模型先决定读文件 → 工具返回 → 模型再回答”的额外模型回合，并避免为恢复状态加载完整 Skill、SELF、SHELF、HANDOFF 或历史。若项目已经用 `AGENTS.md` 等机制把同一状态直接内联给模型，Mishu 会增加一个短安全合同；此时它提供的是自动更新、exact-root、CAS 与恢复安全，而不是 token 压缩。所有节省比例必须在同等恢复结果、同模型、同宿主配置下比较，并同时报告模型阶段数与工具调用数。

## 10. V1 发布证据链

当前主路径证据覆盖 trust、SessionStart、NO_DELTA、无提示自动更新、单次修复 continuation、并发冲突、move/copy 失效、重启恢复与 8 KiB 完整注入。`plan` / `bypassPermissions` 和 malformed/missing receipt 目前只有确定性 adapter 证据；Codex Desktop 尚无独立真实宿主证据，均不得写成已端到端验证。

在隔离、无秘密的真实 Codex 项目中按顺序验收：

1. 未 trust 时 project hooks 被跳过，NOW 零写；
2. 一次 `/hooks` trust 后，SessionStart 注入 exact-root NOW；
3. 普通问答产生 `NO_DELTA`，NOW bytes/mtime/metadata 不变；
4. 有验证证据的任务产生 `PROPOSE_UPDATE`，无权限弹框且 NOW 更新；
5. 缺回执只触发一次 continuation，不死循环；
6. 两个会话并发更新得到一项 `UPDATED` 与一项 `CONFLICT`；
7. 回合中改变 permission mode 或 hook 定义，零写且无提示升级；
8. move/copy 项目后旧授权失效；
9. fault injection 的每个 replace crash point 只留下完整旧/新版本；
10. 关闭并重启 Codex 后恢复最后一次已提交 NOW。

单元测试、源码检查、真实 hook dispatch、真实 trust、真实无提示写入必须分层报告；任何前一层都不能冒充后一层。

## 11. 明确不做

- Claude Code 自动 adapter、permission probe、stage/finalize；
- 跨 host “已验证自动”承诺；
- background daemon、文件 watcher、transcript 解析；
- 自动创建/移动/删除项目，自动发布、付费或外部操作；
- 并发语义合并；
- 自动更新 SHELF、SELF、POOL 或 legacy HANDOFF；
- 网络盘、同步盘、linked worktree 与无法验证 atomic/metadata 语义的平台。
