# Mishu 自动项目连续性 V1 设计

> **SUPERSEDED：** 本文仅保留为 Claude Code 方向的历史记录。当前 V1 以 `2026-08-11-codex-automatic-continuity-design.md` 为准。

- 日期：2026-08-10
- 状态：设计方向已批准；等待书面规格复核
- V1 宿主：Claude Code 本地 macOS / Linux 会话

## 1. 结果

每个本机 exact root 只需明确启用一次。之后，用户正常做事，不必记住“开工”或“收工”：

- 新会话静默恢复一个最小项目检查点；
- Agent 在正常最终回复前判断项目状态是否发生了有证据、且有连续性价值的变化；
- 有变化才刷新检查点，无变化就完全不写；
- 身份、授权、格式或文件版本不明确时停止自动化，不猜、不合并、不覆盖。

显式 `开工`、`收工`、`handoff` 仍保留，但只作为强制查看、强制判断和排障入口，不再是主流程。

V1 不承诺捕获没有 Agent 回合的事件，例如直接关窗、断电、进程被杀或 API 错误后没有恢复机会。

## 2. 第一性原则与 V1 选择

### 2.1 第一性原则

用户的任务是推进项目，不是操作秘书。连续性机制因此只做两件事：

1. 让下一位 Agent 知道现在该做什么；
2. 防止当前 Agent 把无证据的完成推断、已经过时或彼此冲突的状态留给下一位 Agent。

只有三条结果级不变量能从目标直接推出：

1. 下一位 Agent 必须能用有界上下文选择一个安全行动。
2. 自动写入只记录有证据、且会改变后续行动、关键假设或验收方式的信息。
3. 自动化不能越权；写前复检已可见的冲突必须拒写；提交不能留下半文件。

### 2.2 V1 工程选择

为满足上述不变量，V1 选择：一个项目根 `NOW.md`、当前选定的一个 `Next`、Claude Code `SessionStart`、Agent 语义判断与确定性 helper 硬门。这些是可替换的 V1 架构，不冒充普遍原理。

代码、测试、部署结果和用户决定是事实源；`NOW.md` 只是有证据支持的连续性检查点，不是“项目真相”。

## 3. V1 明确不做什么

V1 不增加：

- 后台 daemon、常驻监听器或额外模型；
- Claude Code `Stop` prompt hook；
- 通用 host adapter 框架；
- 全局项目 registry；
- 每轮 receipt、活动日志或冷档追加；
- `CLEAN/DIRTY` 持久状态、revision 字段或可配置状态机；
- 自动写 `SELF.md`、`POOL.md`、`SHELF.md` 或 legacy `HANDOFF.md`；
- 自动迁移、移动、改名或删除旧文件；
- 并行 Agent 的自动合并；
- 宽泛的 `Bash`、`Edit` 或绕过权限规则。

采用 `SessionStart` 而不采用 `Stop` 的原因是：Claude Code 官方把 `SessionStart` 定义为会话级事件，把 `Stop` 定义为每轮事件；prompt-based `Stop` 还会让会话继续并产生额外模型回合。持续为“也许需要交接”付费不符合低 token 目标。参考 [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)。

## 4. 唯一热文件

### 4.1 项目根

V1 只使用 Claude Code 解析出的 `${CLAUDE_PROJECT_DIR}`，取 realpath 后作为唯一项目根；`SessionStart.cwd` 只用于校验当前目录的 realpath 等于该根或位于其下。两者任一不安全，或 `cwd` 越出该根时进入 exception。不自行寻找 Git root，不向上扫描父目录，不扫描兄弟目录，也不从“最近项目”猜测。Claude Code 将 `${CLAUDE_PROJECT_DIR}` 定义为不受 hook 当前工作目录影响的 project root，见 [Reference scripts by path](https://code.claude.com/docs/en/hooks#reference-scripts-by-path)。

项目根在一个 epoch 内冻结。会话中执行 `cd` 不会切换连续性文件；如果主要工作已转到另一个项目，当前项目不自动 checkpoint，新项目需在自己的 Claude Code project root 新开或恢复会话。`resume`、`compact` 或 `fork` 产生新 epoch 时仍重新验证宿主 project root 与本地授权绑定。

一个 Claude Code 项目根就是一个 Mishu 项目。V1 不解释 monorepo 内的嵌套项目；要把子目录当独立项目，必须以该子目录作为新的 Claude Code 项目根单独启用。

### 4.2 路径与格式

唯一 canonical 路径为：

```text
<PROJECT_ROOT>/NOW.md
```

`NOW.md` 必须是项目根内的普通文件，不能是符号链接。项目根按 realpath 比较；V1 只支持提供 advisory lock 与同目录 atomic replace 语义的本地普通文件系统，网络盘和同步盘不在保证范围。

最小格式固定为：

```md
---
mishu: 1
---

# NOW

## Goal

<项目级、用户可见的结果；包含不可改变的边界>

## Verified now

<已有证据支持的当前事实，也明确保留关键未知>

## Next

<当前选定、权限范围内的一个安全动作>

## Done when

<证明 Next 完成的可观察条件>
```

`NOW.md` 整体由 Mishu 管理：frontmatter 只允许 `mishu: 1`，`# NOW` 与四个二级标题必须各出现一次且顺序固定，不允许自定义段落。标题是机器契约，正文使用用户选定的管理语言。用户附加说明放在其他项目文件；出现额外标题、字段或段落时 schema 无效并 fail closed，自动流程绝不清理或覆盖它们。

整个文件以原始 bytes 计算 fingerprint。文件超过 8 KiB 时不注入、不自动写，要求先由用户明确压缩；“约 500 token”仍是性能目标，不是解析规则。

### 4.3 字段边界

| 字段 | 只回答什么 | 不应包含什么 |
|---|---|---|
| `Goal` | 项目最终要产生的用户可见结果与稳定边界 | 当前任务、过程日志、未经用户同意的范围变化 |
| `Verified now` | 已验证结果、已验证失败、阻塞事实和关键未知 | 意图冒充交付、完整 transcript、原始工具输出 |
| `Next` | 当前选定、下一位 Agent 可立即执行的一个安全动作 | 多选清单、长期路线图、越权外部动作 |
| `Done when` | `Next` 的可观察完成谓词 | 抽象愿望、对整个项目的重复描述 |

阻塞不增加独立字段：阻塞事实写入 `Verified now`，解阻动作写入 `Next`，解阻证据写入 `Done when`。

活动项目四段都必须非空。已完成或用户明确取消的项目允许 `Next: None`、`Done when: N/A`，但 `Verified now` 必须包含相应的完成证据或用户决定。暂停项目仍写一个等待或解阻动作及其恢复条件。

`Goal` 只有用户明确改变项目结果或边界时才可更新；Agent 不能把自己的任务选择升级成项目目标。

## 5. 纳管与授权

项目文件与本机授权分开：

- `NOW.md` 中的 `mishu: 1` 只表示 Mishu schema v1；
- 当前项目的 `.claude/settings.local.json` 中，必须存在用户明确批准、指向已安装 Mishu adapter realpath 的唯一 `SessionStart` hook。hook 参数同时保存批准时的 project-root realpath；
- 同一 local settings 必须有一条精确 `permissions.allow`，只匹配该可信 helper 的 `update` 子命令与绑定 root。它不放行普通 Bash、任意 Python、任意文件编辑或其他项目路径；
- 同一 local settings 还必须有一个只匹配该 helper realpath 的 `PermissionRequest` guard。正常 allow 生效时它不会触发；如果宿主原本将要弹权限框，它在显示前拒绝这次自动调用，并把“未保存”原因交给 Agent，不替用户批准。

marker、SessionStart hook、窄权限与 permission guard 同时有效才算纳管。仓库自带或 clone 得到的 `mishu: 1` 不能证明本机用户同意；没有完整本地授权时，自动流程不成立。

一次启用可以在用户确认同一份预览后创建 canonical `NOW.md`，并原子地合并 project-local hook、窄权限与 guard。该确认只授权这次 setup 变更，以及之后由该 helper 自动最小更新此 root 的 `NOW.md`；不授权自动修改 marker、local settings、`SHELF.md`、`SELF.md`、`POOL.md`、其他项目文件或外部系统。

规则如下：

- 创建 marker、注册本地 adapter、加入窄权限与 guard 必须来自同一次明确用户同意；已有 `NOW.md`、`HANDOFF.md`、SHELF 行或历史使用记录都不等于纳管。
- 普通 `SessionStart` 不反复推销纳管。只有用户显式调用 Mishu、批准项目建立或要求交接时，才可提出一次启用建议。
- 已有但无 marker 的 `NOW.md` 视为用户文件。若它已完全符合四段 schema，先展示只增加 marker 的 diff；若不兼容，展示转换候选。不能无损映射的内容必须由用户先移到其他文件，自动流程不得丢弃。
- 自动流程不得创建、升级、修复或删除 marker。
- 正常停用同时移除项目本地 Mishu hook、窄权限与 guard；只移除 SessionStart hook 也会立即撤销功能。之后的 epoch 不再读取，当前 epoch 已进入模型的内容无法反向撤回。
- adapter 已运行但 marker 被删除或改变时，立即禁止后续写入，并在下个 epoch 不再注入；未知版本不是撤销，而是 exception。
- 三项本地 entry 中绑定的 root 必须与当前 `${CLAUDE_PROJECT_DIR}` 的 realpath 完全一致。项目移动或复制到不同 realpath 后即失效，必须在新 root 重新确认；Git clone 通常不会带上未跟踪的 local settings。Claude Code worktree 可能继承主 checkout 的本地规则，但 root binding 会使其 fail closed；V1 不自动纳管 worktree。marker 可以随项目文件保留。
- 三项本地 entry 必须指向已安装 Skill 内的可信 helper，不能指向项目内脚本或通用解释器。该本地配置若被 Git 跟踪，启用流程 fail closed。
- setup 最后必须通过真实 Claude Code Bash 权限层执行一次 byte-identical `update` 探针并得到 `NOOP`，且 permission guard 不得触发；否则项目保持 exception，不能宣称已自动纳管。Claude Code 的规则优先级为 deny、ask、allow；`PermissionRequest` 在即将显示权限提示时触发并可拒绝请求，见 [Configure permissions](https://code.claude.com/docs/en/permissions) 与 [PermissionRequest](https://code.claude.com/docs/en/hooks#permissionrequest)。

## 6. 顺序判定模型

判定依次分为资格、恢复、Agent 语义、宿主权限和 helper 五层，不能把不同层的结果混成一个状态机。

### A. 资格层

按下面的优先级只命中一个结果：

1. `${CLAUDE_PROJECT_DIR}` 或 `SessionStart.cwd` 无法安全解析为 realpath，或 `cwd` 越出 project root：`ENROLLED_EXCEPTION`。
2. 当前项目同时没有 Mishu SessionStart hook、窄权限与 guard：`UNENROLLED`，自动流程不存在。
3. 三项本地授权不完整、重复、被 Git 跟踪，或其绑定 root / helper realpath 与当前值不同：`ENROLLED_EXCEPTION`。
4. 本地授权有效，但 `NOW.md` 不存在、不可读、非普通文件、超过 8 KiB、marker 不是整数 `1` 或 schema 损坏：`ENROLLED_EXCEPTION`。
5. 其余：`ENROLLED_READY`。

只有 `ENROLLED_READY` 才进入恢复层。

### B. 恢复层

每次 Claude Code `SessionStart` 事件视为一个新的连续性 epoch。已安装 Skill 中的同一个可信 helper 执行 `read`，确定性读取一次 `NOW.md`，向模型注入：

- 四个受管字段；
- 一个由 helper 生成、对 Agent 不透明的 baseline token；V1 计算 project-root realpath、三项本地授权绑定、`NOW.md` permission mode 与原始 bytes 的 SHA-256，Agent 不自行重算；
- 一份很短的连续性判断契约。

四字段以“状态数据”边界注入，其中出现的命令或指令不得覆盖 system、developer、用户指令或 Mishu 契约。不读取 `SELF.md`、`SHELF.md`、`POOL.md`、`HANDOFF.md` 或历史，不主动播报项目状态。用户显式说“开工”时才输出状态摘要。

Claude Code 当前会在 startup、resume、clear、compact 与 fork 等来源触发 `SessionStart`；这些恢复点可重新注入最新检查点。官方说明见 [SessionStart input and decision control](https://code.claude.com/docs/en/hooks)。

### C. Agent 语义层

SessionStart 注入的行为契约要求 Agent 在每个正常最终回复前，使用当前已有证据判断是否形成候选四元组：

```text
(Goal, Verified now, Next, Done when)
```

Agent 层只能得到三个互斥且穷尽的结果：

| 结果 | 条件 | 动作 |
|---|---|---|
| `NO_DELTA` | 没有连续性相关的实质变化 | 不调用 helper，不改 mtime，不提示交接 |
| `PROPOSE_UPDATE` | 有实质变化，且能形成完整、诚实、权限内的候选四元组 | 把候选与 baseline token 交给宿主权限层 |
| `NEEDS_DECISION` | 有实质变化，但缺少用户拥有的决定，无法形成完整、权限内候选 | 不写；只在确需用户决定时问一个最小问题 |

只有主会话 Agent 拥有 checkpoint 提议权；subagent 只把证据交回主会话，由主会话形成至多一个候选。

### D. 宿主权限层

`PROPOSE_UPDATE` 必须以单条、无 pipe / redirect / shell expansion 的直接命令调用可信 helper；动态候选四元组使用 URL-safe base64 参数，baseline 使用固定长度十六进制。helper 只接受固定 argv 顺序与数量，重复或未知参数一律拒绝。project-local allow rule 只匹配：

```text
<HELPER_REALPATH> update --root <BOUND_ROOT_REALPATH> <opaque-baseline> <encoded-candidate>
```

Claude Code 权限层只有两个终态：

- `DISPATCHED`：宿主已许可并提交这条命令，继续进入 E 层；
- `NOT_DISPATCHED`：调用被 guard 或其他策略拒绝，helper 没有启动，零写入。

对这条固定 helper 命令，`PermissionRequest` 本身就表示窄 allow 没有形成零打扰路径。scoped guard 因此直接返回 deny，使自动路径确定性落到 `NOT_DISPATCHED`，不显示权限框、不保存健康状态文件，并把“权限需修复，本次未保存”交给 Agent。它只观察并拒绝 Mishu helper 的异常权限请求，不影响项目中的其他 Bash 权限流程。一次启用只有在 guard 未触发、终态为 `DISPATCHED` 且 E 层返回 `NOOP` 时才成功。

### E. helper 执行与硬门层

命令被 `DISPATCHED` 后，E 层只产生：

| 结果 | 含义 |
|---|---|
| `UPDATED` | 授权、schema 与 baseline 有效，已原子更新并复读验证 |
| `NOOP` | 候选受管正文与当前正文相同，文件与 mtime 不变 |
| `CONFLICT` | 本地授权、marker 或 NOW 在 baseline 后改变，不覆盖、不合并 |
| `ERROR` | helper 无法启动、输出无效，或路径、格式、大小、权限、I/O 不满足硬门；原文件不被半写 |

四个结果按固定优先级判定，保证同一输入只命中一个结果：

1. 三项本地授权或 baseline 相对初读发生变化：`CONFLICT`；
2. baseline 有效，但候选、路径、格式、大小、权限或 I/O 非法：`ERROR`；
3. baseline 有效且候选受管正文与当前正文相同：`NOOP`；
4. 其余在成功提交并复读后：`UPDATED`；helper 启动、提交、输出解析或复读失败则仍为 `ERROR`。

这里的边界不是“语气像结束了”，而是 final 前的行为契约。它不增加模型调用，但也不是宿主级强制 finalizer：helper 能确定性约束一次调用，不能证明模型每个 final 必然调用它。V1 必须以真实 E2E 测量遵从率；未达到可靠标准时只能标为实验性，不能宣传为确定性自动收工。若未来必须硬保证每轮检查，需要另行接受 `Stop`/外层 finalization gate 的 token 与复杂度成本。

显式 `收工/handoff` 只要求 Agent 立即运行同一套语义判断，不绕过证据、授权或 helper 硬门。

## 7. 什么算实质变化

新信息只有在会改变下一位 Agent 的行动、关键假设或验收方式时，才有连续性价值。字段变化不是触发器本身；有价值的信息再映射到四字段：

1. 用户明确改变了 `Goal` 或其稳定边界；
2. 新增了可观察结果、可观察失败、已确认阻塞或关键未知的验证状态；
3. 基于当前事实，当前选定的安全 `Next` 发生变化；
4. `Next` 的可观察 `Done when` 发生变化。

“文件确实已修改”与“约定测试尚未运行”都是可观察事实。如果它们让下一步变成运行验证，就应如实 checkpoint：`Verified now` 写“已修改，效果未知；测试未运行”，不能写成“已完成”。

以下情况明确为 `NO_DELTA`：

- 只有时间、Agent/runtime、格式或措辞变化；
- 普通问答、解释、翻译、查询、聊天或资料整理没有改变项目行动；
- 没有任何落地证据的计划、未采用方案或“看起来应该成功”；
- 与当前项目无关的工作；
- 相同语义已经写入。

验证失败本身可以是新事实，但必须按失败记录。未经验证的完成推断永远不能进入 `Verified now`。

## 8. 确定性写入门卫

自动更新必须走一个小型、无第三方依赖的项目检查点 helper；Agent 不直接整文件重写。helper 位于已安装的 Mishu Skill 目录，由 adapter 通过固定 realpath 调用，绝不从项目目录加载代码。它同时提供 `read` 与 `update`，只有三个职责：

1. 校验宿主 project root、`cwd` containment、三项 exact-root 本地授权、普通文件、8 KiB 上限、marker 与固定四段 schema；
2. 在同一个协作锁内比较不透明 baseline token，冲突时拒绝写入；
3. 生成完整 canonical 文件，并用同目录临时文件 + atomic replace 提交，保留原文件 permission mode，写后复读验证。

所有合规 Mishu writer 共用一个 advisory lock。锁文件固定为 `${TMPDIR}/mishu-now-locks/<sha256(realpath)>.lock`，不包含项目路径或内容，可由操作系统清理，不是第二份状态源。锁从重新读取 baseline 前一直持有到 atomic replace 与复读验证完成。由此保证两个合规 writer 最多一个成功，也保证不会覆盖写前复检时已经可见的外部变化；不遵守 advisory lock、且恰好发生在最后复检与 atomic replace 之间的外部写入竞态不在 V1 保证范围，也不承诺自动合并。

helper 严格执行第 6 节的结果优先级：baseline token 不同、任一本地授权变化、marker 改变或消失先返回 `CONFLICT`；baseline 有效时，非法候选或文件条件返回 `ERROR`，byte-identical 候选返回 `NOOP`；只有完成 atomic replace 与复读验证才返回 `UPDATED` 和新的 opaque baseline token，供同一会话后续 checkpoint 使用。

冲突后本轮绝不重试、自动合并或顺手更新其他 store。若用户在同一会话继续，下一次有状态工作前允许 helper 执行一次新的 `read`，建立新 epoch；旧候选丢弃，不能与新状态自动合并。

首次启用不属于自动更新。不存在 `NOW.md` 时，用户确认后以 exclusive create 建立；已存在时按第 5 节的采用规则处理。两个 setup 或 writer 竞争时采用 first-writer-wins，另一个返回 conflict，由用户决定继续使用哪个会话。

V1 至少保证内容完整与 permission mode；平台不支持复制的 ACL/xattr 不在保证内。登记时检测到依赖特殊文件元数据的 NOW，应 fail closed，而不是静默降级。

## 9. `HANDOFF.md` 的退出规则

`HANDOFF.md` 只作为 legacy 输入，不再是运行时热状态：

- 有有效 managed `NOW.md` 时，所有自动与显式连续性流程都完全忽略 `HANDOFF.md`；
- 只有 `HANDOFF.md` 时，自动路径不读、不迁移、不写；
- 用户显式要求启用或交接时，可以展示一次整文件迁移候选并等待确认；
- legacy `Moved` 与 `Still open` 整体进入 `Verified now`，`One next step` 进入 `Next`，`Landing condition` 进入 `Done when`；旧文件不能提供 `Goal`，必须由用户补充或确认；
- 迁移按完整来源进行，禁止从 `NOW.md` 取 `Next`、再从 `HANDOFF.md` 取 `Done when`；
- 如果无 marker 的 `NOW.md` 与 `HANDOFF.md` 同时存在，先让用户选择一个完整来源；不得自动决定优先级；
- legacy 文件缺字段或与本轮证据冲突时停止，不能填 `待确认` 冒充状态；
- 创建 `NOW.md` 后，旧 `HANDOFF.md` 保留原位但永远不再参与读取；移动、归档或删除仍需用户明确批准；
- 新流程绝不创建或更新 `HANDOFF.md`。

## 10. SHELF 的角色

`SHELF.md` 是跨项目入口与活动索引，不是项目当前行动的事实源。

V1 后它只保存或派生：项目名、真实根路径、最近活动、Agent 来源和活动状态。它不再保存或手写 `Next`、`Done when`，也不随 checkpoint 更新。

已有 SHELF 中的行动列视为 legacy cache：不再作为恢复输入，也不自动重写。下一次用户确认重建候选时才移除这些列。

因此：

- 当前项目恢复不读 SHELF；exact root 下的 managed `NOW.md` 足够；
- 跨项目状态由 SHELF 提供有限根列表，再按用户请求读取至多一个相关 `NOW.md`；只有用户明确要求全表细节时才扩展读取；
- `rebuild_shelf.py` 只从 session metadata 重建项目/路径/时间/Agent，不读取 NOW 或 HANDOFF 的行动字段；
- 新项目进入 SHELF、根路径纠正与候选重建仍需用户确认，因为这些是项目身份决定；
- NOW 更新成功与 SHELF 是否新鲜互不影响。

这同时消除当前 scanner 将 `NOW.md` 的一个字段与 `HANDOFF.md` 的另一个字段拼成“混血状态”的风险。

## 11. Claude Code adapter

V1 只实现并验证一个 thin adapter：

1. 用户为 exact root 明确批准 `.claude/settings.local.json` 中的 Mishu `SessionStart` hook、精确 helper-update allow rule 与 scoped `PermissionRequest` guard；三项都以字面参数绑定批准时的 project-root realpath；
2. hook 把 `${CLAUDE_PROJECT_DIR}`、`SessionStart.cwd` 与绑定 root 交给已安装 Skill 内的可信 helper；
3. helper 校验三者关系、完整本地授权与 managed `NOW.md`；有效时注入最小连续性契约、四字段和 opaque baseline token；
4. Agent 正常工作，并在 final 前按第 6、7 节作语义判断；
5. 只有 `PROPOSE_UPDATE` 才通过精确放行的直接命令调用 helper `update`；宿主原本需要询问时，guard 在提示前拒绝并走 `NOT_DISPATCHED`。

adapter 不触发可见“开工播报”，不读取全量 Mishu Skill，不调用额外模型，也不安装 `Stop`/`SessionEnd` 写入 hook。自动路径不依赖“每次项目工作都隐式激活 Mishu Skill”；否则完整 `SKILL.md` 会重新成为固定 token 税。

安装器可以展示包含 helper realpath、绑定 root、SessionStart hook、窄权限与 permission guard 的准确 project-local settings diff，但只有用户确认后才能合并，且不得改写全局 settings。Claude Code 官方把 `.claude/settings.local.json` 定义为单项目、本地且不共享的配置面，见 [Hook locations](https://code.claude.com/docs/en/hooks)。只有真实客户端完成以下证据链后，兼容文档才能写“自动连续性已验证”：

```text
installed → local hook + narrow allow + guard approved → prompt-free NOOP probe → SessionStart fired
→ marker/schema read → NOW injected → semantic no-op verified → automatic write verified
→ conflict stop verified
```

Codex、Hermes、WorkBuddy、Kimi、Qwen 等 V1 均保留显式命令和项目 `NOW.md` 的手动兼容，不宣称原生自动生命周期。

## 12. Token 与项目管理预算

V1 的热路径成本与项目数量、SHELF 大小和历史长度无关：

- 每个 continuity epoch：一份短契约 + 一个 NOW 四元组；
- 每个普通回合：不重复读取，不额外调用模型；
- 每个无变化 final：零文件工具调用；
- 每个真实变化 final：一次受控 checkpoint；
- POOL、SELF、SHELF、历史与 legacy 文件全部是按需冷层。

现有“NOW 约 500 token”保留为待测性能目标，不作为第一性公理，也不引入 tokenizer。8 KiB 是防止无界注入的机械安全上限，不是目标预算。验收应测完整自动路径的实际 input/output token，而不是只统计 `NOW.md`。

checkpoint 覆盖当前快照，不追加 session log。需要历史时使用项目已有冷档，自动连续性不负责创建它。

## 13. 错误与可见性

| 情况 | 自动行为 | 用户可见性 |
|---|---|---|
| 未纳管 | 静默退出 | 无提示、无推销 |
| 无实质变化 | 严格 no-op | 无“已更新”receipt |
| 只有未经验证的完成推断 | `NO_DELTA`，不写为完成 | 正常任务回复中如实说明验证缺口 |
| 已发生的工作使行动改变，但效果未验证 | 如实写“已改、效果未知、验证未运行” | 不得声称完成 |
| 本地授权/marker/schema/size/symlink 异常 | fail closed | 只有影响当前继续工作时才简短说明 |
| helper 原本需要权限提示 | guard 在提示前拒绝，`NOT_DISPATCHED`、零写入 | 说明本地权限需修复，本次检查点未保存 |
| helper 因其他策略未获宿主启动 | `NOT_DISPATCHED`，零写入 | 说明本次检查点未保存 |
| baseline 冲突 | 不覆盖、不合并 | 说明 NOW 已变化，本轮未覆盖 |
| 写入或复读验证失败 | 保留旧文件或完整新文件，不产生半文件 | 明确没有完成 checkpoint |
| 用户显式 handoff 但未纳管 | 展示一次启用/迁移候选 | 等用户确认后再创建 NOW |

普通成功更新不额外打印 receipt；Agent 的正常结果摘要已经告诉用户发生了什么。显式 handoff 仍可返回四字段摘要。

## 14. 验收

### 14.1 确定性检查

用标准库测试覆盖一个 helper 与 adapter 的最小矩阵：

1. clone 只有 marker、没有 project-local hook / allow / guard：自动流程不启动；
2. 任一本地 entry 绑定 root 与 `${CLAUDE_PROJECT_DIR}` 不同，或 `cwd` 越出 root：不读取 NOW、不写入；
3. 精确 allow 被 ask 抢先匹配：scoped guard 在提示前拒绝，`NOT_DISPATCHED`、零写入；deny 或无提示拒绝同样为 `NOT_DISPATCHED`；
4. 本地 hook、窄权限、guard、绑定 root 与有效 marker 同时存在：只返回四字段与 opaque baseline token；
5. 相同候选：内容和 mtime 均不变；
6. 有效 delta：生成 canonical 四字段，permission mode 保留，SHELF/HANDOFF 不变；
7. baseline、本地授权或 marker 在读取后改变：拒绝覆盖，外部版本逐字保留；
8. symlink、损坏 schema、额外标题、重复标题或超过 8 KiB：fail closed；
9. 两个合规 writer 使用同一 baseline：最多一个成功；
10. `rebuild_shelf.py` 不读取或拼接 NOW/HANDOFF 行动字段。

### 14.2 Agent 行为检查

最小行为案例必须区分：

- 已纳管 + 完整实质变化 → `PROPOSE_UPDATE`，helper `UPDATED`；
- 已纳管 + 无连续性变化 → `NO_DELTA`；
- 已纳管 + 观察到代码已改、验证未运行且 Next 改变 → 如实更新未知状态，不写成完成；
- 只有未经验证的成功推断 → `NO_DELTA`；
- 一次性问答 → `NO_DELTA`；
- 缺少用户拥有的决定 → `NEEDS_DECISION`；
- 文件版本冲突 → helper `CONFLICT`；
- 只有 legacy HANDOFF → 不自动读取或迁移。

prompt contract 只能锁住要求存在，不能证明模型真的执行。最终证据必须包含工具调用轨迹、文件 before/after 内容与 mtime、以及最终回复是否越权声称完成。

### 14.3 真实 Claude Code E2E

在隔离、脱敏项目上完成：

1. 新开会话，不说“开工”，Agent 能从一个 NOW 继续；
2. 从 project root 的子目录启动，并经历 `cd` 与 `compact`，仍只使用 host project root 下的同一 NOW；
3. 完成一个已验证的有状态任务，不说“收工”、不弹权限确认，NOW 在 final 前只更新一次；
4. 完成一个无状态问答，NOW 内容与 mtime 不变；
5. 修改代码但不运行约定验收，NOW 如实记录“已改、未验证”，且不写成完成；
6. 两个会话从同一 baseline 开始，一个先写后，另一个检测冲突并停止；
7. 记录完整自动路径 token，与现有 SELF + SHELF + NOW 开工路径比较；
8. 明确记录直接关窗/杀进程，以及不遵守 advisory lock 的外部瞬时写入竞态，不在 V1 保证内。

脚本测试、prompt contract、hook JSON 和真实客户端 E2E 是不同证据层，不能互相替代。

## 15. 预计实现面

设计获书面批准后，实施计划只应触及连续性相关表面：

- 精简 `skills/mishu/SKILL.md` 的主流程与触发描述；
- 把自动连续性核心放入一个短小的按需 reference；
- 修改 Claude `bootup-hook.sh`，只为 managed NOW 注入最小上下文；
- 增加一个标准库 checkpoint helper 和对应小测试；
- 增加 canonical NOW 中英正文模板；
- 让 `context-fold` 生成同一个四字段结构，不再维护另一种热区 schema；只有用户另行确认自动连续性时才加入 `mishu: 1`；
- 让 `rebuild_shelf.py` 与 SHELF 模板退出行动状态存储；
- 更新 hooks、test prompts、安装提示、README 与 host compatibility；
- 保留 legacy HANDOFF 模板，仅标记为迁移输入。

不改 `project-fold`、POOL growth、SELF memory policy、competition adapter，也不增加依赖。

## 16. 规格签字门

实现只有同时满足以下五句才算符合本设计：

1. 未同时验证 exact-root SessionStart hook、窄 update 权限、permission guard 与 `mishu: 1` schema，不把 NOW 正文送入模型，也不自动写。
2. 一次恢复只选择一个完整状态源，绝不拼接 NOW 与 HANDOFF。
3. 写入门卫复检时若发现初读后的本地授权、marker 或 NOW 已变化，本轮不覆盖、不合并、不写其他 store。
4. NOW 是唯一项目行动检查点；SHELF 只做根与活动索引，不能反向覆盖 NOW。
5. 没有真实 Agent turn 就没有语义判断；未经真实宿主 E2E 不宣传自动化。
