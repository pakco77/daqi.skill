# Portable growth and wrap-up hooks

These are the portable behavioral hooks shared by every Agent Skills host. A native adapter may automate the same decisions, but it must keep one canonical project state and must not invent another store format.

## Growth hook

### Trigger

Explicit daqi action at the start of the message:

- `达奇，记下…` / `/daqi 记个点子…`
- `达奇，我想做…` / `达奇，我有个想法…` / `达奇，我想搞…` / `/daqi 我发现…`
- `Daqi: remember…` / `/daqi idea…`
- `Daqi: I want to build…` / `Daqi: I have an idea…` / `/daqi I noticed…`

If the user states an observation or idea without invoking daqi — in any of the growth-hook phrasings (`我发现/我注意到/我有个想法/我想做/我想搞/我打算做`；`I noticed/I found/I have an idea/I want to build`) — offer once: “要记进营地账本吗？这是情报还是点子？” / “Log this in the camp ledger — intel or idea?” Do not write until confirmed.

### Write contract

1. Read POOL and look for the same observation or intent, not merely the same wording.
2. Check schema before interpreting stages. `schema_version: 3` uses `intel/idea`（痛点/点子）；旧 `plan` 行归并为 `idea`（被执行的点子去马厩）。No version, or `schema_version: 1` / `2` (the old mishu-era camp), means legacy: preview `seed → idea`, `signal → idea`, and `candidate → idea`; a legacy `signal` that is a raw observation with no direction maps to `intel`. Ask before rewriting the legacy POOL.
3. Treat `我发现…` / `I noticed…` / `I found…` as a pain point or observation. If no intent matches, add one compact `intel`; never invent a solution direction. If an idea or plan matches, attach the evidence without regressing its stage.
4. Treat `我想做…` / `I want to build…` as intent. If new, add one compact `idea`; if it supplies a direction for matching intel, merge them into that idea rather than duplicating them.
5. There is no plan stage: when the boss wants to execute an idea, `立项` moves it into SHELF with a NOW main line.
6. Record only:
   - stage;
   - one-line pain point or intent;
   - why it appeared now;
   - latest evidence or recurrence;
   - smallest next probe.
7. Never create a project folder or SHELF row without explicit `立项 / promote` approval.

### Receipt

Reply with one line: what was saved, its maturity (情报 / 点子 / 计划), and whether it competes with an unfinished main line.

## Wrap-up hook

### Trigger

- `达奇，收工` / `达奇，交接`
- `/daqi wrap up` / `Daqi: handoff`

### Required facts

Recover from verified work in the current session:

- project root or stable project identity;
- visible result delivered;
- open issue or uncertainty;
- exactly one next step;
- landing condition that proves the next step is done;
- current Agent/runtime when known.

Do not mark an intended or structurally plausible result as delivered.

### Write order

1. Update the project's canonical `NOW.md` if the user explicitly requested handoff or the project already uses that contract. A legacy-only `HANDOFF.md` may be imported whole after review; never splice it with NOW or keep both live.
2. Update or rebuild the matching SHELF row only as metadata: path, last active, activity band, and Agent. Do not duplicate next step or landing condition there.
3. Update POOL only if the session created or strengthened intel, an idea, or a plan.
4. Update SELF only when the session revealed a stable, non-sensitive profile trait that passes the evidence gate.
5. Return a compact receipt: **moved / still open / next / landing condition**.

If the project identity or root is ambiguous, ask one question before writing. Never dump the transcript into a store.

When creating a new continuity contract, use `context-fold` to create canonical `NOW.md`. The bundled HANDOFF templates exist only for legacy interoperability. A hot file is a replaceable current-state snapshot, not an append-only session log; detailed history belongs in the project's existing cold log.

### Enrolled Codex exception

When the turn already contains the exact `Daqi automatic continuity v1.` contract, do not run the portable write order and do not edit NOW or SHELF directly. Decide only:

- `NO_DELTA` when the four action fields have no evidence-backed semantic change;
- `PROPOSE_UPDATE` when goal, verified now, next, or done when materially changes;
- `NEEDS_DECISION` when a material user-owned choice prevents a truthful checkpoint.

Append exactly one receipt from the injected contract as the final raw line. The exact-root Stop adapter is the only writer; it validates the baseline, serializes concurrent writes, preserves supported metadata, and reports conflict without retrying or overwriting another Agent.

## Native host adapters

- Codex: after one exact-root setup and review in Codex `/hooks`, the verified SessionStart/UserPromptSubmit/Stop adapter restores and checkpoints NOW automatically. See [`automatic-continuity.md`](automatic-continuity.md).
- Claude Code: the bundled SessionStart hook is partial and does not prove automatic wrap-up.
- Other hosts: use the explicit commands above unless a native adapter is separately documented and tested.
- A native hook must never bypass project enrollment, exact-root binding, user-owned decisions, privacy exclusions, or evidence gates.
