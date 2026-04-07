# Bug/Issue Entry Template

Use this template when appending to MEMORY.md or a topic file.
Replace all `<placeholders>` with actual content. Remove sections
that have no relevant content rather than leaving them blank.

---

```markdown
## [BUG] <Short descriptive title> — <YYYY-MM-DD>

**Symptoms:** <What the user observed. Error message, behavior, test failure.>

**Root cause:** <The actual underlying problem — not the symptom.>

**Fix:** <What changed. File path(s), function/class, what was wrong and what
replaced it. One paragraph max.>

**Files changed:**
- `<path/to/file.py>` — <what changed>
- `<path/to/test_file.py>` — <added/updated test>

**Pattern to avoid:**
> Never <do X> because <Y>. Always <do Z> instead when <condition>.

**Detection:** <How to find this class of issue in the future. Grep pattern,
test assertion, log signal, or manual check.>

**False leads:** <Wrong diagnoses that were tried first, if any. Saves time
next time.>
```

---

## Example Entry

```markdown
## [BUG] Schedule runner silently skips tracks when TVMaze returns 429 — 2026-04-05

**Symptoms:** Scheduled TV tracks stopped auto-downloading with no error in
logs. `next_check_at` was being updated normally but no searches were triggered.

**Root cause:** `_check_track()` caught the `requests.exceptions.HTTPError`
from TVMaze 429 responses but returned `None` silently instead of re-raising
or setting an error state. The caller treated `None` as a clean skip.

**Fix:** In `handlers/schedule.py::_check_track()`, changed the except block
to set `track.last_error = "TVMaze rate limited (429)"` and return early with
the error persisted. Added retry backoff in `clients/tv_metadata.py`.

**Files changed:**
- `patchy_bot/handlers/schedule.py` — error state written on 429
- `patchy_bot/clients/tv_metadata.py` — exponential backoff on 429/503
- `tests/test_schedule.py` — added test for 429 error state propagation

**Pattern to avoid:**
> Never silently return `None` from a track-check function that can fail.
> Always write an error string to the track record so the runner status table
> reflects the real state.

**Detection:** `grep -n "return None" patchy_bot/handlers/schedule.py` — any
bare `return None` in an except block is suspect. Test: mock TVMaze to return
429 and assert `track.last_error` is set.

**False leads:** Initially suspected the runner interval was too long. Checked
`next_check_at` timestamps — they were correct. The silent None return was only
found by adding debug logging to the caller.
```
