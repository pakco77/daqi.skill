# SELF profile policy / 你的档案规则

SELF is a compact working model of the user **as the boss of the camp**. Its purpose is to avoid repeatedly re-explaining stable operating preferences. It is not a biography, personality test, transcript archive, or secret store.

Frontmatter fields such as `management_language`, `folder_language`, and the explicitly confirmed `default_projects_root` are operational configuration, not profile traits, and do not count toward the 12-trait hot-zone limit. The default root is for new projects and unassigned material only; existing project paths belong in SHELF and do not trigger relocation.

## What belongs in SELF

Record only durable, operationally useful traits:

- explicitly provided industry and occupation when they change domain context;
- an explicitly provided age band when it changes accessibility, pace, or communication; never infer age or store a birthday;
- stable life routines only when they affect timing, interruptions, or work cadence;
- decision style and how much autonomy Agents may take;
- quality bar and the user's definition of a visible result;
- preferred communication density, tone, and reporting shape;
- recurring approval boundaries and risk tolerance;
- stable project taste, prioritization rules, and trade-off preferences;
- repeated working patterns that change how an Agent should collaborate;
- durable goals only when the user wants them treated as global context.

Good entries are instructions that save future context:

```text
- [explicit] Treat installation as incomplete until the target client discovers and uses the Skill. last_confirmed: 2026-07-31
- [observed] Prefer short manager-ready status over process narration. evidence: repeated correction x2; last_confirmed: 2026-07-31
```

## Evidence gate

- Explicit statement or correction: record immediately.
- Inferred trait: require the same operational pattern in at least two independent interactions.
- Industry, occupation, age band, and life routines: explicit statements only; never infer them from writing, files, location, or behavior.
- One-off mood, isolated choice, or speculative interpretation: do not record.
- User correction wins: replace the old entry; do not preserve a contradictory history in the hot profile.

Write observations as collaboration rules, never diagnoses. Prefer “wants structural proof separated from live verification” over “is distrustful”.

## Never store

- passwords, API keys, access tokens, cookies, private keys, recovery codes, or credentials;
- identity numbers, private contact details, exact home/work addresses, or precise live location;
- bank, payment, tax, medical, legal-case, family, relationship, or other sensitive private details;
- private facts about third parties without their approval;
- full transcripts, raw emails, message bodies, or large copied documents;
- local paths or repository contents unless they are the explicitly confirmed `default_projects_root` or already part of an approved project entry in SHELF;
- anything the user asks not to remember.

When useful context is mixed with sensitive content, extract only the non-sensitive operating rule. If that cannot be done safely, store nothing.

## Token discipline

- Keep the profile hot zone to at most 12 active entries and roughly 800 tokens, including background fields.
- Merge duplicates and replace stale statements instead of appending history.
- Read only the sections relevant to the current action.
- Project-specific facts belong in SHELF, NOW, or HANDOFF; immature intel, ideas, and plans belong in POOL.
- If the limit is reached, ask the user before removing a still-valid trait.

## Review contract

SELF remains user-owned and editable. During `/daqi status`, mention at most one new or changed inferred trait, and accept correction without debate.
