# Folder language map / 中英目录映射

This file defines stable schema IDs and their physical English or Chinese folder names. Do not improvise alternate translations inside one project root.

## Canonical mapping

| Schema ID / English | 中文目录名 | Scope |
|---|---|---|
| `_Project-Inbox` | `_项目收件箱` | Projects root |
| `_Archive` | `_归档` | Projects root |
| `_Inbox` | `_收件箱` | Project family |
| `00_Context` | `00_上下文` | Project / family |
| `10_Source` | `10_源码` | L1 project |
| `20_Docs` | `20_文档` | L1 project |
| `10_Shared` | `10_共享` | L2 project family |
| `20_Subprojects` | `20_子项目` | L2 project family |
| `30_Assets` | `30_素材` | Project / family |
| `40_Builds` | `40_构建` | Project / family |
| `50_Data` | `50_数据` | Project / family |
| `60_Run-Release` | `60_运行发布` | Project / family |
| `70_References` | `70_参考` | Project / family |
| `90_History` | `90_历史` | Project / family; old versions and internal history |
| `99_Delete-Review` | `99_待删除复核` | Cleanup only |

Machine-contract filenames such as `NOW.md`, `HANDOFF.md`, `SKILL.md`, `.gitignore`, and source filenames are not translated by this folder-language rule.

## Backup before any mutation

Before creating, renaming, or moving folders in Chinese mode or during a language migration:

1. Resolve the Inbox name from the **current** layout. Create it if this is a new root.
2. Write the complete mapping to one of these paths:
   - Chinese layout: `$PROJECTS_ROOT/_项目收件箱/中英目录映射.md`
   - English layout: `$PROJECTS_ROOT/_Project-Inbox/folder-map.md`
3. If the mapping file already exists, append a dated snapshot. Never overwrite its earlier snapshots.
4. At the top of the same run's language-resolved move log (`cleanup-log.md` or `搬运日志.md`), copy the exact mapping snapshot and record:
   - timestamp;
   - project root;
   - previous language;
   - target language;
   - every old path → new path pair.
5. Show the mapping and move plan to the user. In plan mode, wait for confirmation. In direct mode, only High-confidence moves may proceed, but the mapping backup is still mandatory.
6. After moving, verify every mapped path exists at exactly one of the old/new locations. If both exist or neither exists, stop and report the mismatch.

## Snapshot template

```markdown
## 2026-07-30 14:30 — folder language snapshot

- project_root: /path/to/Projects
- previous_language: en
- target_language: zh

| Schema ID | Old path | New path | Status |
|---|---|---|---|
| 00_Context | Project/00_Context | Project/00_上下文 | planned |
| 10_Source | Project/10_Source | Project/10_源码 | planned |
```

The mapping is a recovery contract, not documentation decoration. Missing mapping backup means no folder-language mutation.
