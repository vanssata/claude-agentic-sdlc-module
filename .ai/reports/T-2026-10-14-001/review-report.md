# Review — T-2026-10-14-001 (ai-reviewer, BALANCED)

verdict: passed — no BLOCKER, no HIGH.

- MEDIUM: `install.sh` Codex path (607-628) and `block_size` (160) still double a legacy pair. Out of scope; recorded as known-risks "Legacy managed-block markers" (b).
- LOW: `find_block` fell through to a legacy pair beside a lone current start marker, leaving two start markers. Fixed in R1: half a current pair returns None (old append path); test "a lone current marker beside a legacy pair renames nothing".
- LOW: a CRLF legacy block surfaces its conflict on run 2 instead of run 1 (markers renamed, edit kept, no doubling). Accepted.
- LOW: a second legacy pair in one file is left in place. Same class as the ledger's "current then legacy" case. Accepted.
- LOW: untested paths — lowercase marker, successful three-way merge of a legacy block, legacy block found in history, CRLF. Accepted; the lowercase case is covered by the manager probe in the ledger.
- INFO: stale legacy content never in history classifies as "edited" and conflicts on later runs — the safe direction.

Examined and clean: the current-marker path is identical in outcome; the `ours == tpl` legacy write is one-shot (second run `0 automatic, 0 conflict`); the note slice yields exactly the marker name; "an edited block is never overwritten" holds.
