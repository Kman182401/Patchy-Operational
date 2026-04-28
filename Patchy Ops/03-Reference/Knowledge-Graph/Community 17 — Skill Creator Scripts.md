# Community 17 — Skill Creator Scripts

**47 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `generate_review.py` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L1` | 10 |
| `run_loop()` | `skills/patchy-bot/skill-creator/scripts/run_loop.py:L47` | 9 |
| `ReviewHandler` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L308` | 7 |
| `parse_skill_md()` | `skills/patchy-bot/skill-creator/scripts/utils.py:L7` | 6 |
| `improve_description()` | `skills/patchy-bot/skill-creator/scripts/improve_description.py:L50` | 6 |
| `find_runs()` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L60` | 6 |
| `generate_html()` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L250` | 6 |
| `build_run()` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L85` | 5 |
| `main()` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L387` | 5 |
| `main()` | `skills/patchy-bot/skill-creator/scripts/run_loop.py:L244` | 4 |
| `run_eval.py` | `skills/patchy-bot/skill-creator/scripts/run_eval.py:L1` | 4 |
| `find_project_root()` | `skills/patchy-bot/skill-creator/scripts/run_eval.py:L22` | 4 |
| `run_eval()` | `skills/patchy-bot/skill-creator/scripts/run_eval.py:L184` | 4 |
| `main()` | `skills/patchy-bot/skill-creator/scripts/run_eval.py:L259` | 4 |
| `embed_file()` | `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py:L149` | 4 |

## Connected Communities

- [[Community 3 — Malware Scanning]] (2 edges)
- [[Community 4 — Parsing & Utilities]] (1 edges)

## All Nodes (47)

- `generate_review.py` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (10)
- `run_loop()` — `skills/patchy-bot/skill-creator/scripts/run_loop.py` (9)
- `ReviewHandler` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (7)
- `parse_skill_md()` — `skills/patchy-bot/skill-creator/scripts/utils.py` (6)
- `improve_description()` — `skills/patchy-bot/skill-creator/scripts/improve_description.py` (6)
- `find_runs()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (6)
- `generate_html()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (6)
- `build_run()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (5)
- `main()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (5)
- `main()` — `skills/patchy-bot/skill-creator/scripts/run_loop.py` (4)
- `run_eval.py` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (4)
- `find_project_root()` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (4)
- `run_eval()` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (4)
- `main()` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (4)
- `embed_file()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (4)
- `load_previous_iteration()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (4)
- `run_loop.py` — `skills/patchy-bot/skill-creator/scripts/run_loop.py` (3)
- `split_eval_set()` — `skills/patchy-bot/skill-creator/scripts/run_loop.py` (3)
- `improve_description.py` — `skills/patchy-bot/skill-creator/scripts/improve_description.py` (3)
- `_call_claude()` — `skills/patchy-bot/skill-creator/scripts/improve_description.py` (3)
- `main()` — `skills/patchy-bot/skill-creator/scripts/improve_description.py` (3)
- `_find_runs_recursive()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (3)
- `_kill_port()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (3)
- `.do_GET()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (3)
- `Shared utilities for skill-creator scripts.` — `skills/patchy-bot/skill-creator/scripts/utils.py` (2)
- `utils.py` — `skills/patchy-bot/skill-creator/scripts/utils.py` (2)
- `run_single_query()` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (2)
- `get_mime_type()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (2)
- `Parse a SKILL.md file, returning (name, description, full_content).` — `skills/patchy-bot/skill-creator/scripts/utils.py` (1)
- `Split eval set into train and test sets, stratified by should_trigger.` — `skills/patchy-bot/skill-creator/scripts/run_loop.py` (1)
- `Run the eval + improvement loop.` — `skills/patchy-bot/skill-creator/scripts/run_loop.py` (1)
- `Run `claude -p` with the prompt on stdin and return the text response.      Prom` — `skills/patchy-bot/skill-creator/scripts/improve_description.py` (1)
- `Call Claude to improve the description based on eval results.` — `skills/patchy-bot/skill-creator/scripts/improve_description.py` (1)
- `Find the project root by walking up from cwd looking for .claude/.      Mimics h` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (1)
- `Run a single query and return whether the skill was triggered.      Creates a co` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (1)
- `Run the full eval set and return results.` — `skills/patchy-bot/skill-creator/scripts/run_eval.py` (1)
- `BaseHTTPRequestHandler` — `` (1)
- `.__init__()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `.do_POST()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `.log_message()` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Recursively find directories that contain an outputs/ subdirectory.` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Build a run dict with prompt, outputs, and grading data.` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Read a file and return an embedded representation.` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Load previous iteration's feedback and outputs.      Returns a map of run_id ->` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Generate the complete standalone HTML page with embedded data.` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Kill any process listening on the given port.` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
- `Serves the review HTML and handles feedback saves.      Regenerates the HTML on` — `skills/patchy-bot/skill-creator/eval-viewer/generate_review.py` (1)
