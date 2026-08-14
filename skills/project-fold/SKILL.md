---
name: project-fold
description: 给 Vibe Builder 的项目文件归位与升级判断 skill。用于把 AI 生成文件、用户手动导入文件、源码、素材、构建产物、过程资料、历史版本和未归属文件，按“先 Inbox、再归位、装不下再升级”的原则，折进普通项目或项目族。触发：整理项目文件、收纳、归类、归档、把文件归位、项目太乱、下载文件夹太乱、散文件不知道放哪、帮我把这堆文件分类。
license: MIT
metadata:
  version: "0.2.0-candidate"
---

# 项目文件自动收纳

skill 名：`project-fold`
版本：`v0.2.0-candidate`
中文名：项目文件自动收纳
定位：给 Vibe Builder 的项目文件归位与升级判断 skill

第一性原理：**升级**。

默认用最小可用结构；只有当现有结构装不下真实复杂度时，才升级目录形态。目录服务做成，不服务洁癖。

## 目录语言与中英映射

开始扫描前先确定本次项目根使用 `zh` 还是 `en`：

1. 作为 daqi 子 Skill 使用时，先按 `DAQI_HOME`（若已设置）或 `~/.daqi` 解析 store 根，再读取 `SELF.md` 的 `folder_language`。
2. 独立使用且语言未知时，先问用户用中文目录还是英文目录；中文目录和双语映射通常会多消耗一点 token。
3. 同一个 Projects 根只用一套实际目录名，不能中英混建。正文里的英文目录名是稳定的 schema ID；真正执行时按所选语言映射。
4. 中文模式或语言迁移时，执行任何创建、改名或移动之前，必须读取并遵守 [`references/folder-names.md`](references/folder-names.md)：先写完整映射文件，再把本轮映射快照写进搬运日志。
5. 机器契约文件 `NOW.md`、`HANDOFF.md`、`SKILL.md` 不翻译，避免跨 Agent 发现失败。

## 根目录规则

当 `project-fold` 由 daqi 调用时，`default_projects_root` 只是新项目和未归属资料的默认落点。已有项目即使位于其他位置，也先在原地只读盘点；不得因为设置了默认根目录就搬迁。只有用户确认集中整理，并看过 move plan 后，才执行可逆移动。

Projects 第一层只允许三类：

```text
Projects/
  <Project>/
  _Project-Inbox/
  _Archive/
```

`<Project>` 是一个可持续推进、复盘、归档的开发目标。不要让散文件、下载名、临时 demo、单个构建包、过程文档或旧仓库副本占据第一层。

归档语义只有两层，名称不重复：Projects 根的 `_Archive/` 只接收**整个退役项目容器**；项目内部旧版本、旧 demo 和历史副本只进入 `90_History/`。

非开发目标不要留在 Projects 第一层。素材、参考图、字体、截图等去全局 Assets 或项目 `30_Assets/` / `70_References/`；不确定就进 `_Project-Inbox/`。

## 升级阶梯

### L0 Inbox

未判断归属的 AI 生成文件或用户手动导入文件先进入：

```text
_Project-Inbox/
```

不要让用户先想分类。Agent 后续二次分类。

Inbox 边界：

```text
_Project-Inbox/      = 不知道属于哪个项目
<Project>/_Inbox/    = 知道属于这个项目，但不知道放哪个意图目录
<ProjectFamily>/_Inbox/ = 知道属于这个项目族，但不知道属于共享级还是子项目级
```

### L1 普通项目

默认形态。一个目标，一个主要开发对象。

最小结构：

```text
<Project>/
  00_Context/
  10_Source/
  20_Docs/
  90_History/
```

按需生长（**不预建全套**，按“文件意图判断表”长出真实需要的目录）：

```text
30_Assets/
40_Builds/
50_Data/
60_Run-Release/
70_References/
```

清理任务才加：

```text
99_Delete-Review/
```

当同一项目内出现多份源码、多类素材、构建产物、数据、运行/发布流程时，**不新建项目、不升级层级，只补对应目录**。这仍是 L1，只是长胖了。

### L2 项目族

当一个目标下面出现 **2 个以上会独立演化的输出形态**，才升级为项目族。

项目族比普通项目多两个核心判断点：

```text
<ProjectFamily>/
  00_Context/
  10_Shared/
  20_Subprojects/
  _Inbox/
  90_History/
```

**注意编号语义变了**：项目族用 `10_Shared/20_Subprojects` **替代** L1 的 `10_Source/20_Docs`，同一层不并存。子项目内部才重新回到 L1 的 `10_Source/20_Docs` 逻辑。

按需增加普通项目目录，如 `30_Assets/`、`40_Builds/`、`50_Data/`、`60_Run-Release/`。

铁律：

- 共享的放 `10_Shared/`
- 独立演化的放 `20_Subprojects/`
- 不确定的放 `_Inbox/`
- 子项目内部继续按普通项目逻辑整理

示例：一个 vibe builder 用户的同一目标下同时出现 Web App、Browser Extension、Landing Site、Skill Pack，才升级为项目族。只有一个 Web demo 时保持普通项目。

## 文件意图判断表

先按层级选对 schema：**L1 普通项目**用 `10_Source/20_Docs`；**L2 项目族根**用 `10_Shared/20_Subprojects`。两套不并存。下表「层级」列标明各目录适用哪一层。

| 目录 | 层级 | 放什么 | 不放什么 / 冲突判断 |
|---|---|---|---|
| `00_Context/` | L1 / L2 通用 | 当前开工必读的最小真相：项目定义、当前状态、下一步、关键决策 | 历史长文不放这里；如果每次开工都要读，提炼进 Context，原文留 Docs |
| `10_Source/` | 仅 L1（或子项目内） | 会改变产品本体的源头：代码仓库、worktree、App/Web/CLI 工程、skill 源目录 | 多个 Git 仓库不合并，先用 `local-worktree/`、`public-repo/` 等标身份 |
| `10_Shared/` | 仅 L2 根 | 项目族里跨子项目复用的源头、协议、模板、代码、可编辑规范 | 媒体素材去 Assets；外部参考去 References；决策边界去 Context |
| `20_Subprojects/` | 仅 L2 根 | 项目族里会独立开发、发布、演化的子项目 | 只共享资源不算子项目 |
| `20_Docs/` | 仅 L1（或子项目内） | 过程资料：PRD、讨论记录、复盘、方案、说明、分析结论 | 当前必读去 Context；机器数据去 Data |
| `30_Assets/` | L1 / L2 通用 | 项目会直接使用的素材：logo、截图、视频、设计稿、发布媒体 | 只作参考的外部素材去 References |
| `40_Builds/` | L1 / L2 通用 | 可再生成或对外交付的成品：app、dmg、zip、导出 HTML、release | 源码不放这里 |
| `50_Data/` | L1 / L2 通用 | CSV/JSON/测试数据/用户记录/清洗中间结果/分析输入输出 | 分析结论文档去 Docs |
| `60_Run-Release/` | L1 / L2 通用 | 怎么运行和发布：部署、签名、公证、server、环境说明 | token、证书、私钥、`.env` 去敏感复核区 |
| `70_References/` | L1 / L2 通用 | 外部参考：竞品、模板、第三方示例、设计参考 | 会进入交付物的素材去 Assets |
| `90_History/` | L1 / L2 通用 | 项目内部的旧版本、旧 demo、历史副本、合并前备份 | 当前入口不从这里开始；整个退役项目才进入 Projects 根的 `_Archive/` |
| `99_Delete-Review/` | L1 / L2 通用 | 只在清理任务中放准备删除但要复核的候选 | 普通整理不主动创建 |

## 备份与版本泛滥处理

一堆同源文件（版本号、日期、"备份/backup/副本/copy/_bak/_old"、"xxx前备份"）是整理里最占地方、最不敢删的东西。规则：**识别一族 → 留最新 → 旧的收进待删除区 → 永不自动删 → 用户复核**。

识别「同源族」：主名相同、只差版本或备注后缀。例：

```text
CAM需求清单_v2.7.xlsx
CAM需求清单_v2.7_修改前备份.xlsx
CAM需求清单_v2.7_版本号统一前备份.xlsx
CAM需求清单_v2.8.xlsx
CAM需求清单_v2.9.xlsx      <- 最新，留在正常目录
```

处理：

- **保留活口**：版本号最高 / 时间最新的一份留在正常目录；无法判断谁最新时，全族留 Inbox 并说明。
- **旧版收待删除区**：其余进 `99_Delete-Review/<族名>/`（或用户项目已有的备份目录，如 `09_备份/`——**沿用用户现有约定，不新造**）。
- **只归置不删除**：待删除区是「候选」，删不删由用户在复核后决定；skill 自己绝不删。
- **运行期垃圾**单列：`*.sqlite-wal`/`-shm`、`__pycache__/`、`*-recovery-backups/`、`Thumbs.db`、`.DS_Store` 等是工具运行残留，不是资料，进 `99_Delete-Review/_runtime/` 或列为待删除复核候选；不要当项目文件归档，Skill 自己不删除。
- 待删除区的每一次归置照样写进搬运日志，能还原。

## AI 生成与手动导入的二次分类

不要只按文件后缀分类。先判断归属层级，再判断文件意图。

顺序：

0. 先剥离备份/版本族（见「备份与版本泛滥处理」）：留最新，旧的入待删除区，再对剩下的判归属。
1. 属于哪个项目或项目族？
2. 是项目级、共享级，还是子项目级？
3. 是 Context、Source、Docs、Assets、Builds、Data、Run-Release、References、History、Delete-Review 哪一种？
4. 置信度够不够？
5. 不够就留 Inbox，不硬搬。

置信度：

```text
High   -> 可建议直接移动
Medium -> 列入 move plan，等用户确认
Low    -> 留在 Inbox，并说明缺什么信息
```

示例：

```text
index.html
```

可能是 `10_Source/`、`40_Builds/`、`90_History/` 或 `_Project-Inbox/`；看相邻文件、引用关系、文件名和用户意图再定。

```text
logo.png
```

可能是项目 `30_Assets/`、项目族 `30_Assets/`、子项目 `30_Assets/` 或 `70_References/`；不要只因后缀是 png 就移动。

Mini case：

```text
导入文件：
  landing.html
  app-demo.mp4
  logo.png
  prompt.md
  old-v1.zip

判断：
  landing.html -> 10_Source 或 40_Builds，看是否还会继续编辑
  app-demo.mp4 -> 30_Assets
  logo.png     -> 30_Assets
  prompt.md    -> 00_Context 或 20_Docs，看是否定义项目行为
  old-v1.zip   -> 90_History
```

## 两种模式

起手先判断走哪种模式，别默认闷头整理。

- **方案模式（默认）**：首次整理、或用户第一次接触这套框架时。**先理解现状再写方案**——只读扫描完、看懂文件之间的归属关系后，再落笔。方案要**极简**：只列真正要动的文件（移哪个→到哪、置信度、一句为什么），不堆砌不解释显而易见的项，让用户几眼扫完就能确认。确认后才执行。宁可多问一句，不要擅自搬动。
- **直接模式**：满足以下**任一**条件才启用，跳过方案直接执行——
  - 用户明示「现在马上整理 / 直接执行 / 不用给我看方案」；
  - 目标目录已经是这套结构（目录名可为映射表中的中文或英文；第一层只有项目容器、Inbox、Archive），说明用户在用这套框架，只是日常归位。
  - 即便直接模式，High 置信度才真移动；Medium/Low 仍留 Inbox 并在日志里说明。

判断不了走哪种，就默认方案模式。

## 工作流程

1. 判断模式（见「两种模式」）：不确定或首次 → 方案模式。
2. 先与用户确认 Projects 根路径，记为 `$PROJECTS_ROOT`；不假设、不硬猜。
3. 只读扫描 `$PROJECTS_ROOT` 第一层和 Inbox。
4. 让用户确认项目名；不从仓库名硬推项目名。
5. 移动 Git 仓库前先跑 `git status --short`；有未提交内容时只按身份包裹，不合并、不删除。
6. 默认建普通项目（L1）容器。
7. 只有出现多个独立演化输出时，升级为项目族（L2）。
8. 散文件按“归属层级 + 文件意图 + 置信度”生成 move plan。
9. 执行移动：方案模式必须先给用户看 plan、确认后才移；直接模式跳过确认，但只移 High 置信度，Medium/Low 一律留 Inbox。
10. 项目内部历史副本进所选语言对应的 `90_History` / `90_历史`；只有整个项目退役时，项目容器才进入 Projects 根的 `_Archive` / `_归档`。不要删除。
11. 所有移动写入搬运日志（复原兜底）：每条记录 `原路径 -> 新路径`、时间、置信度，确保能逐条反向还原。没有用户指定输出目录时，英文模式放 `$PROJECTS_ROOT/_Project-Inbox/cleanup-log.md`，中文模式放 `$PROJECTS_ROOT/_项目收件箱/搬运日志.md`。格式示例：

```text
## 2026-07-07 14:30 整理
- ./landing.html -> ./Tuck/10_Source/landing.html  [High]
- ./old-v1.zip   -> ./Tuck/90_History/old-v1.zip    [High]
- ./mystery.dat  留 _Project-Inbox（Low：无法判断归属）
```
11. 完成后验证：

```bash
find "$PROJECTS_ROOT" -maxdepth 1 -type f -not -name '.DS_Store' -not -name '.localized' -print
find "$PROJECTS_ROOT" -maxdepth 1 -mindepth 1 -not -name '.DS_Store' -not -name '.localized' -print
```

第一条应为空；第二条应只显示项目容器以及所选语言对应的 Inbox、Archive。

## 真实文件系统坑

- macOS 默认大小写不敏感：`tuck` 和 `Tuck` 视为同一路径。遇到只改大小写或同名容器包裹时，必须用临时名中转：`tuck -> __tmp_tuck_source -> Tuck/10_Source/local-workspace`。
- `.DS_Store` 和 `.localized` 是系统噪音；验证时忽略，只提示用户可清理或列入待删除复核，Skill 自己不删除。
- 普通目录不能因为名字像编号就留在 Projects 第一层；它必须是用户确认的开发目标，否则进 `_Archive/`、`_Project-Inbox/` 或项目内 `70_References/`。
- 移动同名项目容器时，先把旧内容包进 `90_History/<old-name>/`，再建立新结构。

## 安全边界

- 每次整理必写搬运日志（`原路径 -> 新路径`），这是复原兜底；没有日志的移动等于不可逆，不允许。
- 中文模式或语言迁移时，映射文件与日志中的映射快照都写好之后才能移动；映射不完整就停手。
- 不删除。
- 不自动清 `node_modules`、`.next`、`.build`、模型、venv。
- 不移动系统目录、隐藏配置目录、`bin`。
- 不合并 Git 仓库；多个仓库先用 `local-worktree/`、`github-repo/`、`public-repo/` 标身份。
- 不把证书、token、`.env`、私钥放进项目仓库；放敏感复核区。
- 不把应用本体塞进 `/Applications`，除非它是明确的 `.app` 安装包且用户要求。
