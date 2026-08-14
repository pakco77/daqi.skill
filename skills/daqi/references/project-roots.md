# Default project home / 默认项目资料根目录

`default_projects_root` is the confirmed default home for **newly approved projects and unassigned material**. It is not the only valid project location and never authorizes moving existing projects.

## First-use contract

- Ask for language and the default project home in one compact onboarding message.
- Language is required. The project home may be a confirmed path, `帮我选 / help me choose`, or `稍后设置 / later`.
- Keep `default_projects_root` blank when deferred. That does not block SELF, SHELF, POOL, status, idea capture, or handoff.
- Before an action needs a new folder or unassigned-material Inbox, require a confirmed root.
- Normalize a confirmed path for the current platform before saving it. Do not publish it or copy it into examples.

## Help-me-choose contract

Recommend exactly one candidate and wait for confirmation. Do not silently create it, scan the whole disk, or select removable, network, temporary, or cloud-synced storage by default.

- Windows: prefer a user-confirmed non-system fixed drive such as `D:\Projects` when one is available. If only `C:` is suitable, say so and suggest a user-level path such as `%USERPROFILE%\Projects` or `%USERPROFILE%\Documents\Projects`; never promise that `C:` can always be avoided.
- macOS: suggest `~/Projects` or `~/Documents/Projects`. Use `/Volumes/<disk>/Projects` only after the user confirms that disk.
- Linux: suggest `~/Projects`. Use a mounted data path only after the user confirms it.

Never default to a drive root, system directory, Downloads, Desktop, an external disk, or a synced folder merely because it exists.

## Two entry paths

### New project from zero

1. Capture a pain point as intel or an intent as an idea in POOL.
2. Let a clear direction turn intel into an idea; let evidence plus a clear user, deliverable, and next test turn the idea into a plan.
3. Ask for explicit `出发 / promote` approval.
4. If no project root was supplied, propose a folder under `default_projects_root`.
5. Create only the minimum real structure after confirmation.

### Existing project intake

1. Require the exact existing project root; do not search for a substitute.
2. Inventory read-only and identify the visible deliverable, current state, next step, and landing condition.
3. Show a candidate SHELF entry before writing it.
4. Keep the project in place by default, even when it is outside `default_projects_root`.
5. If files need reorganization, call `project-fold`; show the bilingual map and move plan before any move.

If an existing project spans several roots, show the inventory and ambiguity first. Do not consolidate until the user approves one destination and a reversible move plan.
