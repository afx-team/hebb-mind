# PersonaMem

PersonaMem is a preference-tracking benchmark where the system must reason about *why* a user changed their mind across sessions. We run it in `mode=raw` (no consolidation) to isolate the retrieval layer.

## Hebb Mind on PersonaMem

| Hebb Mind config | Score | Source |
|---|---|---|
| **v0.1.1 raw, judge = Kimi-K2.5** | **67.6%** QA acc (37q, 3 scenarios) | `eval/reports/personamem/v1/run-1/personamem.md` |

Per-category, strongest on `track_full_preference_evolution` (88.9%), weakest on `recall_user_shared_facts` (40.0%) — i.e. the system tracks *change* better than it remembers individual *facts*. The same verbatim-preservation lever that drove LoCoMo's 90%+ result should help here too.

## Per-competitor comparisons

PersonaMem is recent enough that we have not found published numbers from mem0, Letta, MemPalace, or Zep on it. This section will populate as comparisons appear; open a PR if you have a public number to add.

| System | Score | Source |
|---|---|---|
| mem0 | TBD | — |
| Letta | TBD | — |
| MemPalace | TBD | — |
| Zep | TBD | — |
