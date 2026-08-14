# Mishu Codex Automatic Continuity V1 Implementation Plan

> **For Codex:** Execute serially in the current task. Do not dispatch implementation subagents before the first real Codex E2E; after that, use one architecture reviewer only.

**Goal:** Ship a Codex-first, exact-root, no-prompt project-continuity path in which the Agent emits one semantic receipt and a trusted `Stop` hook safely commits canonical `NOW.md`.

**Architecture:** One project-local `.codex/hooks.json` invokes one installed Python adapter for `SessionStart`, `UserPromptSubmit`, and `Stop`. The adapter validates the exact root and hook bundle, injects compact state, parses a final hidden receipt, and reuses the existing NOW reader/CAS/lock/atomic writer. A non-authoritative per-session baseline cache avoids re-injecting NOW on unchanged turns.

**Tech Stack:** Python 3 standard library, Codex command hooks, existing assert-style tests, Git, macOS filesystem primitives already exercised by `checkpoint.py`.

**Scope stop:** Only defects that violate the approved Codex design or the ten-item acceptance chain block V1. Claude adapter work, new hosts, network filesystems, linked worktrees, background daemons, semantic merge, transcript parsing, and speculative hook surfaces stay frozen.

---

## Task 1: Expose the existing safe core through four host-neutral seams

**Objective:** Let the Codex adapter reuse safe reads, installed-path trust, baseline hashing, and metadata snapshots without importing private names or duplicating CAS logic.

**Files:**

- Modify: `skills/mishu/scripts/checkpoint.py`
- Modify: `tests/test_checkpoint.py`

**Step 1 — RED:** Add assertions for these public functions and exports:

```python
checkpoint.read_bounded_regular(path, limit=8192)
checkpoint.read_managed_now(root)
checkpoint.trusted_installed_path(root, adapter_path)
checkpoint.host_baseline_token(
    "codex-v1", root, authorization, permission_mode, mode, raw, metadata
)
```

Tests must prove that the host baseline changes with root, authorization, permission mode, NOW bytes, mode, gid, supported flags, and provenance, but not mtime.

**Step 2 — Verify RED:**

```bash
python3 tests/test_checkpoint.py
```

Expected: `AttributeError` for the first missing public seam.

**Step 3 — GREEN:** Add thin public wrappers around the existing `_read_regular_at`, `_read_now`, `_trusted_installed_paths` validation, and length-prefixed `_baseline_token`. Do not create a second reader, lock, metadata validator, or atomic writer.

**Step 4 — Verify and commit:**

```bash
python3 tests/test_checkpoint.py
python3 tests/test_rebuild_shelf.py
git add skills/mishu/scripts/checkpoint.py tests/test_checkpoint.py
git commit -m "refactor: expose host-neutral checkpoint seams"
```

Expected: both PASS lines; dirty Claude Task 5 files remain untracked and untouched.

## Task 2: Define the exact Codex hook bundle and enrollment classifier

**Objective:** Produce and validate exactly one root-bound Mishu entry for each of the three Codex lifecycle events.

**Files:**

- Create: `skills/mishu/scripts/codex_continuity.py`
- Create: `tests/test_codex_continuity.py`

**Step 1 — RED:** Add tests for:

- canonical `SessionStart`, `UserPromptSubmit`, and `Stop` command entries;
- literal adapter realpath and literal canonical root in every command;
- exact READY, no-Mishu UNENROLLED, and partial/duplicate/alias/broadened EXCEPTION;
- unrelated hooks preserved;
- `.codex`/`hooks.json` symlink, non-regular file, unsafe owner/mode, tracked config, linked worktree, and project inline `[hooks]` rejected;
- cwd outside root and move/copy with the old literal root rejected.

**Step 2 — Verify RED:**

```bash
python3 tests/test_codex_continuity.py
```

Expected: import/file-not-found failure for `codex_continuity.py`.

**Step 3 — GREEN:** Implement only pure bundle construction, Mishu-shaped entry detection, safe project config reads, Git eligibility, exact-root containment, and event-independent snapshot qualification. Use `json`, `shlex`, `tomllib`, and Task 1 seams only.

The canonical command is one shell-safe string:

```text
<adapter-realpath> hook --root <canonical-root>
```

**Step 4 — Verify and commit:**

```bash
chmod 755 skills/mishu/scripts/codex_continuity.py
python3 tests/test_codex_continuity.py
python3 tests/test_checkpoint.py
git add skills/mishu/scripts/codex_continuity.py tests/test_codex_continuity.py
git commit -m "feat: validate Codex continuity enrollment"
```

## Task 3: Implement SessionStart/UserPromptSubmit context with token deduplication

**Objective:** Inject full NOW once per continuity epoch and a short baseline/receipt contract on ordinary turns.

**Files:**

- Modify: `skills/mishu/scripts/codex_continuity.py`
- Modify: `tests/test_codex_continuity.py`

**Step 1 — RED:** Cover valid and malformed JSON events, every documented `source`/`permission_mode`, exact hook-specific output names, XML/HTML escaping of only NOW field bodies, literal safe root, 8 KiB input and bounded complete JSON output, compact re-injection, and zero reads of prompt/transcript/SHELF/SELF/POOL/HANDOFF.

Add cache tests for `0700` directory, `0600` regular file, hashed filename, owner/no-follow checks, atomic write, cache miss/corruption/full-state fallback, unchanged-turn short context, and post-update cache failure remaining non-authoritative.

**Step 2 — Verify RED:** Expected first assertion failure at missing event dispatch/context.

**Step 3 — GREEN:** Implement:

```python
def session_start(event, root): ...
def user_prompt_submit(event, root): ...
def read_cached_baseline(root, session_id): ...
def write_cached_baseline(root, session_id, baseline): ...
```

Do not store prompt, NOW text, transcript path, or assistant messages. A cache failure emits full state but never changes authorization.

**Step 4 — Verify and commit:**

```bash
python3 tests/test_codex_continuity.py
python3 tests/test_checkpoint.py
git add skills/mishu/scripts/codex_continuity.py tests/test_codex_continuity.py
git commit -m "feat: inject compact Codex continuity context"
```

## Task 4: Implement final receipt parsing and Stop control flow

**Objective:** Require one exact final-line receipt, continue at most once when it is missing, and never write for `NO_DELTA` or `NEEDS_DECISION`.

**Files:**

- Modify: `skills/mishu/scripts/codex_continuity.py`
- Modify: `tests/test_codex_continuity.py`

**Step 1 — RED:** Test the three exact receipt shapes plus leading/trailing text, code fence, duplicate receipt, malformed baseline/candidate, wrong event/root/session mode, missing receipt on first Stop, and missing receipt with `stop_hook_active=true`.

Expected outputs:

```json
{"continue":true}
{"decision":"block","reason":"...one repair continuation..."}
{"continue":false,"stopReason":"mishu_receipt_missing","systemMessage":"...not saved..."}
```

Assert project bytes/mtime/metadata remain unchanged for both non-write decisions and all invalid receipts.

**Step 2 — Verify RED:** Expected failure at missing receipt parser/Stop dispatcher.

**Step 3 — GREEN:** Parse only the final raw line with one anchored ASCII regex. Recompute the current baseline for all three decisions. On conflict/error, continue once with an honest failure instruction; if already active, stop with zero write.

**Step 4 — Verify and commit:** Run focused and checkpoint tests; commit as `feat: enforce Codex continuity receipts`.

## Task 5: Connect PROPOSE_UPDATE to the existing atomic writer

**Objective:** Commit one verified candidate without a model tool call while preserving all existing concurrency, crash, and metadata guarantees.

**Files:**

- Modify: `skills/mishu/scripts/codex_continuity.py`
- Modify: `tests/test_codex_continuity.py`

**Step 1 — RED:** Add NOOP/UPDATED/CONFLICT/ERROR cases; decode-side-effect and pre-replace hook/Git/permission changes; two-process same-baseline race; source symlink/hard-link/ACL/xattr/gid/UF_HIDDEN/UF_IMMUTABLE; cache update success/failure; and no temporary files left after every failure.

**Step 2 — Verify RED:** Expected PROPOSE path to return the not-implemented failure with NOW unchanged.

**Step 3 — GREEN:** Under `checkpoint.root_lock(root)`:

1. qualify exact enrollment and snapshot;
2. compare receipt baseline before candidate decode;
3. strict decode/render;
4. requalify after decode;
5. return byte-identical NOOP or call `checkpoint.atomic_replace_now` with a pre-replace authorization callback;
6. re-read/parse/metadata-check after replace;
7. refresh cache best-effort only after commit.

Do not retry, merge, or call the Claude CLI path.

**Step 4 — Verify and commit:** Run `test_codex_continuity.py` twice, then checkpoint/rebuild, `py_compile`, `sh -n`, and `git diff --check`; commit as `feat: checkpoint NOW from Codex Stop hooks`.

## Task 6: Prove the vertical slice in a real isolated Codex project

**Objective:** Establish real host dispatch/trust/no-prompt evidence before building the setup installer.

**Files:**

- Create only if needed: `tests/codex_e2e_fixture.py`
- Record evidence in: `docs/plans/2026-08-11-codex-automatic-continuity-implementation.md` under an appended “E2E evidence” section

**Step 1 — Prepare:** Use a temporary, secret-free normal Git root with canonical managed NOW and canonical hooks generated by the adapter. Record Codex version, OS, adapter realpath, root, initial hashes/mode/gid/flags/xattrs, and hook source.

**Step 2 — Trust boundary:** Run Codex without `--dangerously-bypass-hook-trust`; prove untrusted hooks are skipped and NOW unchanged. Then use the real `/hooks` review flow once. Do not edit trust state by hand and do not count bypass mode as evidence.

**Step 3 — Host cases:** Run real sessions for SessionStart restore, NO_DELTA unchanged, verified PROPOSE_UPDATE without an approval UI, one missing-receipt continuation, permission-mode fail-close, move/copy invalidation, close/restart restore, and two-session conflict. Keep adapter-process concurrency and atomic fault injection labeled separately from host evidence.

**Step 4 — Gate:** If SessionStart context, raw HTML receipt preservation, Stop continuation, or hook-write permission behaves differently from the official contract, stop and revise the design before any installer work. Otherwise commit the optional fixture/evidence only.

### E2E evidence — 2026-08-11

Real-host evidence was collected in a secret-free temporary Git project on macOS 27.0 (26A5406e) with `codex-cli 0.147.0-alpha.6.5`. The adapter was invoked from its real source path and no hook-trust bypass flag was used.

- **Trust boundary:** Before approval, thread `019ff049-76d1-75f1-b611-869d3721071c` returned the ordinary sentinel `UNTRUSTED_CHECK`, emitted no Mishu receipt, and left the initial `NOW.md` hash `e53046b5c702beb1ebe30b2fd3fb96a5ffc5ab436a9d5caf1c45ba17bce4de35` unchanged. In the real `/hooks` review UI, only the exact project-local SessionStart, UserPromptSubmit, and Stop entries were approved; seven unrelated pending hooks were not approved.
- **Automatic write:** Thread `019ff051-d9dd-7122-b99f-e4fecf54583e` received restored state, verified a 40-byte one-LF milestone, emitted a raw final-line `PROPOSE_UPDATE`, and the Stop hook changed `NOW.md` to hash `ce99b499530456bf166f5022d05333ef8403d8e412110b4ec8bf47128478cf81` without a permission prompt. Mode `0644`, uid `501`, gid `0`, flags `0`, link count `1`, and the `com.apple.provenance` bytes were preserved; no `.mishu-NOW.*` file remained.
- **Fresh restore and token hot path:** Thread `019ff057-949a-7792-ba56-6ebc34546898` started fresh, answered directly from the injected four fields with zero tool calls, emitted `NO_DELTA`, and left the same NOW hash and metadata unchanged. It used 28,726 input tokens. The earlier stale-Skill thread's 594,283 figure was cumulative across 11 model stages, so it is not a valid before/after comparison; it is retained only as evidence that avoidable model round trips dominate total input usage.
- **Move/copy invalidation:** A full project copy retained the old literal bound root. Thread `019ff059-9ad3-7ae2-a13f-236ee109253f` in the copied path returned only `MOVED_CHECK`, with no Mishu receipt; both original and copied NOW files remained at hash `ce99b499530456bf166f5022d05333ef8403d8e412110b4ec8bf47128478cf81`.
- **Two-session conflict:** Threads `019ff05f-b1c0-7641-9682-f1adedfff9dd` and `019ff05f-b1c0-7811-8007-843aaadb50c0` started from the same baseline and proposed different successors. B2 was the sole committed winner; A2 received a real Stop repair continuation, reported `CONFLICT`, and did not retry. Final NOW hash was `54bc5b2127a21c24e2de2e838dd32095237381e316c5402cc598e3c2ac9ddd51`, contained only B2, preserved the same metadata/xattr, and left no temporary file.
- **Host-discovered correction:** Two earlier competing sessions independently encoded conventional sorted-key compact JSON and were safely rejected by the former hidden field-order rule. Candidate canonicalization was therefore changed to lexicographically sorted keys and exposed in the injected contract before the passing race above.
- **Architecture-review repair:** The single final reviewer found one P1: the 8 KiB reader accepted a larger state domain than the former 9,500-byte hook-output gate could inject after HTML escaping, while positive Codex `additionalContextLimit` values could spill the rest to a file. The repair keeps the shared Claude gate unchanged, gives Codex a derived 64 KiB complete-JSON gate, and sets only the two context-producing Codex handlers to `additionalContextLimit: 0`. Deterministic tests now require a pathological exact-8192-byte managed NOW and the calculated worst-case envelope to remain complete.
- **8 KiB real-host boundary:** In a new temporary project, only the exact three project hooks were approved in `/hooks`; unrelated pending hooks remained untrusted. Thread `019ff0f8-1531-7e91-a35a-38f9b6eb74cb` received the terminal marker `TERMINAL-8K-MARKER` from an exact 8,192-byte managed NOW and returned `EIGHT_K_RESTORED` plus `NO_DELTA` with zero tool calls. The run used 44,629 input tokens and 65 output tokens. NOW remained byte-identical at SHA-256 `e4e12783b15b3dc9fb13c2dc6115bac2077d2b8d5cb37847462658029e9b2977`; mode `0644`, uid `501`, gid `0`, flags `0`, link count `1`, size, and mtime were unchanged. No `hook_outputs` spill directory or spill notice was produced.

### Token A/B evidence — 2026-08-11

One real-host, outcome-equivalent A/B/C was run with the same Codex version, model, global configuration, user prompt, and 303–307-byte project state. All three runs saw the same MCP/network startup failures and WebSocket-to-HTTPS retry path; only each final `turn.completed` usage record was compared. This is a controlled case, not a population benchmark.

| Variant | Recovery path | Model stages | Tool calls | Input tokens | Total tokens |
|---|---|---:|---:|---:|---:|
| A — Mishu | exact-root SessionStart/UserPromptSubmit injection from managed NOW | 1 | 0 | 28,714 | 29,063 |
| B — manual file | project rule tells the Agent to read the equivalent `PROJECT_STATE.md` | 2 | 1 | 55,832 | 55,956 |
| C — bespoke inline | equivalent state is hard-coded directly in `AGENTS.md` | 1 | 0 | 27,860 | 27,896 |

- A versus B saved 27,118 input tokens (48.6%) and 26,893 total tokens (48.1%) by avoiding the second model stage. Thread IDs: A `019ff145-e109-7463-8df0-4c332cebda83`; B `019ff147-fe88-7ab1-b082-9bb7ce7ca3b4`.
- A versus C cost 854 additional input tokens (3.1%) and 1,167 total tokens (4.2%). This is the safety/decision-contract tax when another mechanism already injects the same state without a read round. Thread C: `019ff14a-bfa0-70f1-9b2c-0af0341b6e99`.
- In A, the complete SessionStart context was 1,595 characters and the first-turn UserPromptSubmit contract was 1,258 characters. The enrolled fast path made no tool call and did not load the 20,449-byte Mishu `SKILL.md` merely to recover state.

The defensible expectation is therefore conditional: about 40–55% input-token reduction for a cold restore that would otherwise require one file-read round; more when several sequential read rounds are replaced; no token saving—and roughly a 3–5% first-turn tax in this environment—against an already-inline, bespoke state injection. The product value remains low-friction and safe continuity in every case; token saving comes from eliminating model round trips and large recovery documents, not from the presence of a Skill by itself.

The real host run proves trust gating, SessionStart injection, raw receipt preservation, no-prompt Stop writes, one repair continuation, restart restore, exact-root move/copy invalidation, and concurrent conflict handling. Malformed/missing receipt, `plan`/`bypassPermissions`, filesystem fault injection, ACL/xattr/flags/hard-link rejection, and process-level lock matrices remain deterministic adapter/core evidence rather than claimed UI E2E. Restricted-mode regression coverage now proves SessionStart, UserPromptSubmit, NO_DELTA, and blocked PROPOSE_UPDATE create no cache or project write and always inject the complete hot state. `--ignore-user-config` was excluded from evidence because it also disables the project hook path.

## Task 7: Add one-time preview/apply/disable after the E2E gate

**Objective:** Make activation reversible and low-friction without recreating Claude stage/probe/finalize.

**Files:**

- Modify: `skills/mishu/scripts/codex_continuity.py`
- Modify: `tests/test_codex_continuity.py`

**Step 1 — RED:** Cover deterministic zero-write preview tokens; fresh/exact-idempotent enable; partial/broadened rejection; unmarked/missing NOW candidate; normal Git/non-Git; exclude/hook/NOW before-state changes; symlink/linked-worktree/tracked config; crash after each prefix; hooks-last order; metadata-preserving existing-file writes; and disable removing only exact Mishu entries while retaining NOW and unrelated hooks.

**Step 2 — GREEN:** Add `preview-enable`, `apply-enable`, `preview-disable`, `apply-disable`, and `status`. Reuse one root lock and safe readers. Per-file atomic writes bind exact before bytes/mode/metadata; hooks are written last and host trust remains the activation barrier. Do not add rollback or a second permission system.

**Step 3 — Verify and commit:** Run focused twice plus all existing tests; commit as `feat: configure Codex automatic continuity`.

## Task 8: Align the Skill and public boundaries

**Objective:** Make “开工/收工” optional in enrolled Codex projects and report host evidence honestly.

**Files:**

- Modify: `skills/mishu/SKILL.md`
- Modify: `skills/mishu/references/hooks.md`
- Modify: `skills/mishu/references/agent-compatibility.md`
- Create: `skills/mishu/references/automatic-continuity.md`
- Modify: `skills/mishu/test-prompts.json`
- Modify: `tests/test_rebuild_shelf.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Step 1 — RED:** Require the three Agent decisions, exact-root rules, managed NOW-only write, Codex evidence label, no Claude/cross-host automatic claim, explicit enable/disable/status, and representative no-delta/unverified/needs-decision/conflict prompt cases.

**Step 2 — GREEN:** Keep the hot injected contract self-contained. Load the longer reference only for setup/status/diagnose/disable. Preserve explicit start/handoff as escape hatches.

**Step 3 — Verify and commit:** Run all three assert suites and commit as `docs: enable Codex automatic continuity workflow`.

## Task 9: One final architecture review and release check

**Objective:** Catch only structural or security defects that can violate the approved contract, then stop.

**Files:** No planned production files; fixes only for concrete P0/P1 against the current spec.

**Step 1:** Invoke `agent-architecture-review` once with the approved design, final diff, unit evidence, and real E2E evidence.

**Step 2:** Fix confirmed blockers serially with one regression test per root cause. Do not expand host/platform scope.

**Step 3:** Run:

```bash
python3 tests/test_checkpoint.py
python3 tests/test_codex_continuity.py
python3 tests/test_rebuild_shelf.py
python3 -m py_compile skills/mishu/scripts/checkpoint.py skills/mishu/scripts/codex_continuity.py
git diff --check
git status --short
```

Expected: all PASS, only intentionally frozen Claude files remain untracked, and the evidence report clearly distinguishes deterministic tests from real Codex behavior.
