# Codex automatic continuity

Load this reference only when the user asks to enable, inspect, diagnose, or disable automatic project continuity. A normal enrolled turn already receives the complete hot-state contract from Codex hooks and must not load this file.

## Invariant

- Enrollment belongs to one exact project root and one trusted installed adapter outside that root. Never choose a root by recent use or directory-name similarity.
- `NOW.md` is the sole hot project truth. It contains goal, verified now, one next step, and done when. Keep it compact; do not copy transcripts.
- `HANDOFF.md` is legacy import material only. When both unmarked NOW and HANDOFF exist, stop for one source choice; never merge individual fields.
- `SHELF.md` is a derived metadata index, not a second copy of next or done when.
- Moving or copying the project invalidates enrollment. Enable the new exact project root separately.

## One-time enablement

Resolve `ADAPTER` to the installed Skill's trusted, executable `scripts/codex_continuity.py` realpath. It must be owned by the current user, not group/world writable, and outside the exact project root. Resolve `PROJECT_ROOT` to the user's explicit project root; do not substitute another directory.

1. If canonical or unmarked `NOW.md` exists, preserve its four fields whole. If no NOW exists, derive a truthful four-field candidate from evidence, encode it with the installed `checkpoint.encode_candidate`, and pass the same token to preview and apply. A candidate is not permission to mark unverified work complete.
2. Run the zero-write preview:

   ```sh
   "$ADAPTER" preview-enable --root "$PROJECT_ROOT"
   "$ADAPTER" preview-enable --root "$PROJECT_ROOT" --candidate "$CANDIDATE"
   ```

   Use the first form when NOW already exists and the second only when a new canonical NOW is required. Show the returned exact file diffs and ask for one confirmation. Do not run apply in the same unconfirmed step.
3. After confirmation, reuse the unchanged preview token, root, and optional candidate:

   ```sh
   "$ADAPTER" apply-enable --root "$PROJECT_ROOT" --preview "$PREVIEW_TOKEN"
   "$ADAPTER" apply-enable --root "$PROJECT_ROOT" --preview "$PREVIEW_TOKEN" --candidate "$CANDIDATE"
   ```

   A stale token fails with `preview_conflict`; preview again rather than guessing or overwriting.
4. `CONFIGURED_NEEDS_HOOKS_REVIEW` means the exact project files were configured, not that Codex trusts them. Ask the user to open Codex `/hooks` in that project and review exactly three project hooks: SessionStart, UserPromptSubmit, and Stop. Do not edit global Codex configuration or add a broad shell allow rule.

Codex decides hook trust in its UI. Daqi cannot mechanically turn `CONFIGURED_NEEDS_HOOKS_REVIEW` into a trusted claim. The first real lifecycle dispatch is stronger evidence than configuration; a real automatic NOW update is stronger evidence than dispatch.

## Per-turn decisions

The injected contract is self-contained. The Agent works from its four fields and emits exactly one final receipt:

- `NO_DELTA`: no evidence-backed semantic change. Ordinary chat, thanks, timestamps, intentions, a claimed but unverified success, or identical normalized fields do not write.
- `PROPOSE_UPDATE`: goal, verified now, next, or done when materially changed and every changed fact is supported by the turn. The Stop adapter performs the write.
- `NEEDS_DECISION`: a user-owned material choice or a truth gap prevents a safe checkpoint. Ask one question; do not manufacture a candidate.

The adapter serializes writers under one root lock, compares the injected baseline, writes through a same-directory temporary file, syncs, atomically replaces, reads back, and preserves supported mode, owner, group, flags, provenance, and ACL/xattr state. A stale Agent gets `CONFLICT`, reports that its checkpoint was not saved, and does not retry. Unsupported or changing metadata fails closed.

In Codex permission modes `default`, `acceptEdits`, and `dontAsk`, an already reviewed project hook may run without another prompt. In `plan` and `bypassPermissions`, the adapter performs zero writes. Missing, malformed, duplicate, untrusted, moved, or permission-changed enrollment also fails closed.

## Status and disablement

Status is read-only:

```sh
"$ADAPTER" status --root "$PROJECT_ROOT"
```

`CONFIGURED_NEEDS_HOOKS_REVIEW` always retains its literal meaning: configured locally, trust still checked in Codex `/hooks`.

Disablement also uses preview then one confirmed apply:

```sh
"$ADAPTER" preview-disable --root "$PROJECT_ROOT"
"$ADAPTER" apply-disable --root "$PROJECT_ROOT" --preview "$PREVIEW_TOKEN"
```

Disable removes only the exact Daqi hook groups. It preserves canonical NOW, Git exclude metadata, and unrelated project hooks. Never claim this Codex evidence for Claude Code or another host; each native adapter needs its own real end-to-end proof.
