# Work split: Sriya and Likhitha

Event: Sun 1 Nov 2026. Plan: `visual-bisect-build-plan.md`. Backend feature freeze: Fri night.
Setup (both): `python -m venv <SHORT PATH>` (Windows: the venv path must be short, or Pillow's DLL fails),
`pip install -e ".[dev]"`, `playwright install chromium`, copy `.env.example` to `.env` and fill in your own key.
`.env` is gitignored. Never commit keys. Model: `gemma-4-26b-a4b-it` (the 31B model hangs and returns 500s).

## State today (30 Oct, evening)
Working: CLI, real `git bisect run`, Gemma + pixel judges, cache/replay, repo generator, eval runner and
summarizer, `--preset`, `--model` (Gemini API or `ollama:<name>`), a first dashboard (`python -m vbisect.server`,
http://127.0.0.1:8431, single HTML page, includes `POST /api/runs`), and a real-repo case
(`eval/real_case.ps1`, homow/dashboard-skeleton, n = 1: Gemma found the culprit, the pixel judge was unsure).
**Not done: the dev-set eval has no complete results.** Three attempts were stopped (hangs, then Gemini API
failures). Nothing about Gemma's accuracy may go in the README until it runs.

### Eval handoff (whoever takes it: read this first)
- Use `gemma-4-26b-a4b-it`. Probe on 30 Oct: 26B worked on 3 of 4 calls (12-17 s, one 500); `gemma-4-31b-it`
  failed 4 of 4 with 500s; `gemini-3.5-flash` worked 4 of 4 (~6 s) but is not a Gemma model.
- When Gemma jobs skipped steps, every skip in the logs was an API error (500, 504, read timeout), never the
  model being unsure. Check `skip_reason` in `runs/eval/<label>/gemma/*/events.jsonl` before trusting a result.
- Retries are already tuned in `vbisect/judge_gemma.py` (45 s timeout, 5 attempts, images capped at 1024 px).
- **To do first in `eval/run_eval.py`:** the Gemma semaphore blocks a worker thread and wastes half the
  capacity. Run Gemma jobs in their own 1-worker pool and the pixel jobs in a separate pool (and write partial
  results after every job, so a killed batch keeps what it finished). Then run
  `powershell -File eval/run_dev.ps1 <venv-python> <label>` (log: `eval_<label>.log`).
- Do not run Gemma jobs while anything else uses the same API key.
- Rotate the two API keys that were pasted in chat before the repo goes public.

## The two shared contracts (do not change without telling the other person)
1. **`runs/<id>/events.jsonl`**: one JSON event per line. Types and fields: plan section 10.2
   (`run_started`, `step_started`, `build_progress`, `render_done`, `judge_call`, `step_done`, `run_done`,
   `run_failed`). Writer: `vbisect/events.py`. Sample runs to develop against: `runs/e2e-pixel`, `runs/e2e-gemma`.
2. **`eval/results.json`**: written by `eval/run_eval.py`, shape `{label, results: [{seed, judge, rep,
   culprit_type, difficulty, found, exact, steps, skips, api_calls, seconds, step_correct, step_judged, run}]}`.

---

## Demo plan and priority tiers (updated)
The demo story: a real project's UI changed, we have one old screenshot, we press Start and watch the
commit strip shrink live with Gemma's reasons, then the culprit appears with a before/after slider and the
diff. Backup: a recorded video and `--replay` (cached model answers, works offline).

- **Tier 1 (must be done by Sat afternoon):** a real public repo that works end to end, the dev/test eval
  numbers, Live Run + Culprit reveal screens, `--replay` and a backup video.
- **Tier 2 (only if Tier 1 is done):** New Run screen (drop a screenshot, draw a box, press Start),
  replay site on GitHub Pages.
- **Tier 3 (one "what's next" slide, not built):** a GitHub Action / bot that replies to a UI-regression
  issue with the culprit commit.
- We claim "web projects you can build and serve with a command", not "all repos". The README lists limits.

## Yasaswini: backend, model swap, presets, first real repo
Done so far: CLI, `git bisect run` pipeline, Gemma and pixel judges, cache/replay, repo generator, eval runner,
model swap (`--model`, Ollama supported), presets (`--preset vite|next|static`), `POST /api/runs`, the first
real-repo case (homow/dashboard-skeleton, n = 1), hang and timeout fixes.
1. **Still open:** a complete dev eval (see "Eval handoff" above) and `eval/results.dev.json`.
2. Hand the real case to Likhitha to verify by hand (a 4-commit range; widen it if time allows).
3. Support Sriya and Likhitha; bug fixes only after Saturday.

## Sriya: Dashboard (`vbisect/server.py`, `vbisect/export.py`, `web/`)
Owns everything the judges look at. Plan section 10 is the spec.

**Starting point already in the repo:** `vbisect/server.py` (FastAPI: run list, events, SSE stream, files, diff,
`POST /api/runs`) and `vbisect/static/index.html` (one page, no build step) show a run live from `events.jsonl`.
Build on it or replace the page with the React app below; keep the API routes. **Visual direction (decided
after reviewing awwwards.com and the Bluejack client dashboard):** light page, a plain-English one-line
result, very large numbers with small spaced-out labels, cream cards, italic serif for verdicts, one red
accent, a dark top bar. No gradients, no dark theme with status colours. Judge views: 1280x720.

1. **`server.py` (FastAPI)**: `GET /api/runs`, `/api/runs/{id}` (all events), `/api/runs/{id}/stream` (SSE tail of
   events.jsonl), `/api/runs/{id}/files/{path}`, `/api/eval`. Serve `web/dist` in production. Add `--ui` and
   `vbisect serve` to the CLI (`cli.py`: add only the new subcommand, don't touch the bisect flow).
2. **Frontend skeleton**: Vite + React + TS + Tailwind, Zustand store, `DataSource` interface with
   `LiveSource` (SSE) and `StaticSource` (files + timers). All derived state (remaining range, step count,
   culprit) as pure functions of the event list.
3. **Live Run screen (must-have)**: commit strip that visibly narrows, status line, judge panel
   (OLD | CANDIDATE | NEW, reason text, vote bars, verdict badge), step timeline. Light theme per the
   visual direction above, 1280x720.
4. **Culprit reveal (must-have)**: drag slider and side-by-side first; onion skin and heatmap only if time.
   Diff view with diff2html (`culprit.diff` is in the run folder).
5. **Replay screen**: scrubber, play/pause, 1x/2x/4x, same components as Live Run.
6. **Judge Arena** (after Likhitha's `results.json`): bar chart per judge, breakdown by culprit type, fooled gallery.
7. **`export.py` + GitHub Pages**: static replay site from run folders + `results.json`.
8. Presentation mode (`P` key).
9. **New Run screen (Tier 2, only after Live Run + Culprit reveal work)**: drop an old screenshot, fill repo path /
   refs / URL / focus, draw a box on the screenshot (sets `--region`), Start, then jump to Live Run.
   Uses `POST /api/runs` (Yasaswini).

Cut order if short on time (plan section 17): fooled gallery, onion skin/heatmap, New Run screen.
Must not slip: Live Run, Culprit reveal, terminal output still works if the UI breaks.

## Likhitha: Evidence, real case and docs (`eval/`, `README.md`, demo material)
Owns every number and every word judges read.

1. **Dev eval and prompt tuning (Fri AM)**: the dev eval has not completed yet; run it first, following
   "Eval handoff" at the top of this file. Then read `eval/results.dev.json`
   (`python eval/summarize.py eval/results.dev.json`). If Gemma misses on some culprit types, write
   `vbisect/prompts/judge_v2.txt` (bump `PROMPT_VERSION` in `judge_gemma.py`) and rerun on the **dev set only**.
2. **Test set (Fri PM, never tuned on)**: `python eval/make_repos.py --seeds 101 102 103 104 105 106 107 108 109 110 111 112 --commits 100`,
   then `python eval/run_eval.py --seeds 101 ... 112 --repeats 3 --workers 3 --label test --out eval/results.json`.
   Expect it to take a couple of hours; start it early. Commit `results.json` and the `*.truth.json` files.
3. **Real-world case (Sat, Tier 1; picks up from Yasaswini's first attempt)**: the first case exists
   (`eval/real_case.ps1`, homow/dashboard-skeleton, range `4ce2f40..8fa9e4a`; Gemma named `32632f7`, which edits
   `SideBarHeader.jsx`). Verify it by hand, keep its run folder (`runs/real/`) for replay, pre-warm the
   dependency cache, and try a wider range or a second repo (Chronicle or Zzzdo from the team's own repos) if
   time allows. Label it n = 1. The README already has a paragraph for it; keep it truthful.
4. **README** (outline: plan section 13): quickstart, how it works, results table from `summarize.py`,
   limitations, prior art. Only measured numbers, test set only (plan section 18 honesty rules).
5. **`SKILL.md`**: check the fields against the Agent Skill Open Standard.
6. **Demo (Sat)**: demo script (plan section 15), backup video, rehearse twice with a timer, run once with
   Wi-Fi off using `--replay`, fresh-clone test on another laptop, `v0.1.0` tag.
7. Stretch, only if everything above is done: text mode, `--region` crop for the Gemma judge.

---

## Timeline
| When | Yasaswini | Sriya | Likhitha |
|---|---|---|---|
| Fri | eval fix, model swap, presets, first real repo | server.py, frontend skeleton, Live Run | dev results, tuning, start the test-set run |
| Sat AM | `POST /api/runs`, support Sriya and Likhitha | Culprit reveal, Replay | test results, verify real-world case, README draft |
| Sat PM | bug fixes, backup video help | Judge Arena, export + Pages, presentation mode, New Run (Tier 2) | README numbers, SKILL.md, demo video, rehearsal |
| Sun | fix real bugs only | polish only | final numbers, submission text, `v0.1.0`, submit 15 min early |

## Rules
- Separate files, separate branches: Yasaswini owns `vbisect/` backend (`oracle.py`, `judge_gemma.py`, `cli.py`,
  `builder.py`); Sriya owns `web/`, `server.py`, `export.py`; Likhitha owns `eval/`, `README.md`,
  `prompts/`. Need a change in someone else's files (e.g. Sriya adding a `cli.py` subcommand)? Message the owner first.
- If the Gemma API is flaky on event day, use the cache: `vbisect ... --replay`.
- Check `git log` for secrets before making the repo public.
