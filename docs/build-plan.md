# Visual Bisect: Full Build Plan

> **Find the commit that changed what you see, from one old screenshot.**
> `git bisect` does the search. Gemma 4 decides "good or bad" at each step by looking at the rendered page.

**Event:** Hacktoberfest offline hackathon, Sun 1 Nov 2026
**Tracks:** Best Open-Source AI Project + Best Use of Gemma 4
**Plan written:** Wed 28 Oct 2026 (about 4 days to the event)

---

## Table of contents

1. [The project](#1-the-project)
2. [Scope](#2-scope)
3. [Tech stack and setup](#3-tech-stack-and-setup)
4. [Architecture](#4-architecture)
5. [Module specs](#5-module-specs)
6. [The Gemma judge in detail](#6-the-gemma-judge-in-detail)
7. [Stable renders](#7-stable-renders)
8. [Builds, caching and skips](#8-builds-caching-and-skips)
9. [Evaluation](#9-evaluation)
10. [The live dashboard](#10-the-live-dashboard)
11. [Stretch: text mode](#11-stretch-text-mode)
12. [SKILL.md](#12-skillmd)
13. [README outline](#13-readme-outline)
14. [Day-by-day timeline](#14-day-by-day-timeline)
15. [Demo script](#15-demo-script)
16. [Judge Q&A prep](#16-judge-qa-prep)
17. [Risks and fallbacks](#17-risks-and-fallbacks)
18. [Honesty rules](#18-honesty-rules)
19. [Submission checklist](#19-submission-checklist)

---

## 1. The project

### Problem
A part of the UI changed or broke, and nobody noticed for weeks. Now there are 100+ commits between "it looked right" and "it's broken," and there is no error to trace.

- **A diff doesn't help.** It shows what code changed, not which change caused the visible effect. The culprit is often a commit that looks unrelated, such as a dependency bump, a shared CSS edit or a refactor.
- **`git bisect` only half-helps.** It does the binary search, but at every step someone must answer "good or bad?" For crashes or failing tests you can script that answer. For "does the sidebar look like it did in March?" you can't, so a human has to check out, build, open the browser and judge, about 7–8 times per search.
- **Pixel diffs fail** because dates, data and unrelated parts of the page change between commits.
- **Visual regression tools** (Percy, Chromatic and similar) need baselines set up *before* the bug. They can't work backwards from an old screenshot.

### Solution
Visual Bisect automates the missing judge:

1. You give it an old screenshot, a page URL and a short description of what changed ("the left sidebar").
2. It runs real `git bisect run`. At each step it builds the commit, renders the page with Playwright and asks Gemma 4 whether the focus area matches the OLD or NEW version.
3. It returns the culprit commit and its diff, and a live dashboard shows every step as it happens.

**Pitch line:** "`git bisect` knows *how* to search. We taught it to *see*."

### How it maps to the judging criteria

| Criterion | How we win it |
|---|---|
| Usefulness | Saves 30–60 minutes of manual bisecting per visual regression; works on any web app with zero setup |
| Open-source AI usage | Gemma 4 is the core decision-maker, not decoration; open-weight model, MIT/Apache repo, SKILL.md |
| Execution | Real `git bisect` underneath, cached and reproducible runs, measured accuracy on 20 test repos plus 1 real case |
| Demo quality | A live dashboard: the commit range visibly shrinks step by step, Gemma's reasons stream in, then a before/after reveal of the culprit; pixel-diff baseline shown failing |
| Documentation | 30-second quickstart, how-it-works diagram, results table, limitations, prior art, reproduce command |

### Track requirements

- [ ] Public GitHub repo with an open-source license (MIT or Apache-2.0)
- [ ] Gemma 4 via the Gemini API is an important part of the project
- [ ] SKILL.md that follows the Agent Skill Open Standard
- [ ] Original implementation (we build the oracle, judge, renderer and eval, and call `git bisect` underneath)

---

## 2. Scope

### Must have (MVP)
- CLI: `vbisect` with old screenshot + URL + focus description, returns the culprit commit
- Gemma judge with the 3-image comparison, order swap and skip-when-unsure logic
- Pixel-diff baseline judges (full page and cropped) for comparison
- Response cache and `--replay` mode
- Live dashboard: Live Run, Culprit reveal, Judge Arena and Replay screens ([section 10](#10-the-live-dashboard))
- Eval: synthetic repos with known culprits, plus 1 real open-source case
- README, LICENSE, SKILL.md

### Stretch (only after the MVP works end to end)
1. **Static replay site on GitHub Pages** (strongly recommended: gives judges a link they can explore themselves)
2. New Run screen in the dashboard (start runs from the browser, draw the focus box)
3. Text mode: bisect changes in CLI or JSON output
4. GitHub Action wrapper
5. `--region x,y,w,h` crop flag for the Gemma judge

### Out of scope
- Mobile apps, desktop apps
- Apps that need login, secrets or a database to render
- Slow monorepos (build time over about 60 seconds per commit)
- Anything that isn't a web page reachable on localhost

---

## 3. Tech stack and setup

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Fast to write, good Playwright and Gemini SDKs |
| Model | Gemma 4 via the Gemini API (`google-genai` SDK) | Required for the Gemma track; multimodal |
| Browser | Playwright for Python (Chromium, headless) | Reliable screenshots, clock control |
| Git | `git` CLI via `subprocess` | Real `git bisect run` and `git worktree` |
| Images | Pillow, scikit-image (SSIM) | Cropping, pixel baseline |
| Test apps | Vite (vanilla TS) | Builds in about 1–3 seconds |
| Dashboard backend | FastAPI + Server-Sent Events (SSE) | Streams each bisect step to the browser live; simpler than WebSockets |
| Dashboard frontend | Vite + React + TypeScript + Tailwind | Fast to build, fast to iterate |
| Animation | Framer Motion | Shrinking commit range, culprit reveal |
| Charts | Recharts | Judge Arena results |
| Image compare | react-compare-slider | Drag-to-compare before/after |
| Diff view | diff2html | Syntax-highlighted culprit diff |
| State | Zustand | Small store shared by live and replay modes |

### Setup commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install google-genai playwright pillow scikit-image rich fastapi "uvicorn[standard]"
playwright install chromium
cp .env.example .env    # add GEMINI_API_KEY and GEMMA_MODEL

# dashboard
npm create vite@latest web -- --template react-ts
cd web
npm install framer-motion recharts react-compare-slider diff2html zustand
npm install -D tailwindcss @tailwindcss/vite
```

`.env.example`
```
GEMINI_API_KEY=
GEMMA_MODEL=          # copy the exact Gemma 4 model name from the event's Gemma docs
```

Node.js 20+ is also needed to build the test apps and the dashboard.

---

## 4. Architecture

### Flow
```
 vbisect CLI
     │  writes run.json (config), creates a git worktree
     ▼
 git bisect start --term-old=old --term-new=new <bad> <good>
 git bisect run python -m vbisect.oracle --config run.json
     │
     │  for each commit git picks:
     ▼
 oracle.py
   1. builder:   install deps (cached) → build → serve on localhost
   2. renderer:  Playwright screenshot of --url (stable settings)
   3. judge:     Gemma compares candidate vs OLD ref vs NEW ref in the focus area
   4. exit code: 0 = old, 1 = new, 125 = skip (build failed or judge unsure)
     │
     ▼
 git bisect reports the first "new" commit
     │
     ▼
 Throughout: oracle appends events to runs/<id>/events.jsonl
     │
     ▼
 server.py tails events.jsonl → SSE → live dashboard in the browser
 (the same events file replays the run later, or in a static site)
```

### Repo layout
```
visual-bisect/
├── vbisect/
│   ├── __init__.py
│   ├── cli.py            # entry point, arguments, starts the bisect
│   ├── config.py         # RunConfig dataclass, read/write run.json
│   ├── oracle.py         # called by git bisect for each commit
│   ├── git_ops.py        # worktree, bisect start/run/reset, commit info
│   ├── builder.py        # install, build, serve, dependency cache
│   ├── renderer.py       # Playwright screenshots with stable settings
│   ├── judge_gemma.py    # Gemma judge
│   ├── judge_pixel.py    # SSIM baseline judges
│   ├── cache.py          # response cache keyed by input hashes
│   ├── events.py         # appends typed events to events.jsonl
│   ├── server.py         # FastAPI: API + SSE stream + file serving
│   └── export.py         # builds the static replay site
├── web/                  # dashboard (Vite + React + TS)
│   └── src/
│       ├── api/          # live.ts (SSE), static.ts (replay from files), types.ts
│       ├── state/        # runStore.ts (Zustand)
│       ├── screens/      # LiveRun, Culprit, JudgeArena, Replay, NewRun
│       └── components/   # CommitStrip, JudgePanel, VoteBars, CompareView, DiffView, StepTimeline
├── eval/
│   ├── base_app/         # the Vite app template used by make_repos.py
│   ├── make_repos.py     # generates test repos with known culprits
│   ├── run_eval.py       # runs all cases with each judge
│   ├── summarize.py      # results.json → results table (markdown)
│   └── cases/            # generated repos + truth.json (gitignored except truth files)
├── skills/visual-bisect/SKILL.md
├── tests/                # unit tests with fake judge and fake builder
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## 5. Module specs

### 5.1 `cli.py`
```
vbisect --repo PATH --good REF --bad REF
        --screenshot OLD.png --url /path --focus "text"
        [--build-cmd "npm run build"] [--serve-cmd "npx vite preview --port {port}"]
        [--install-cmd "npm ci"] [--judge gemma|pixel-full|pixel-crop]
        [--region x,y,w,h] [--replay] [--out runs/<id>]
```
- Validates inputs (repo exists, refs resolve, screenshot is a PNG).
- Creates a run folder `runs/<timestamp>/` containing `run.json`, screenshots, `events.jsonl` and the culprit diff.
- Writes the ordered commit list (`git rev-list --reverse --ancestry-path good..bad`) into the `run_started` event so the dashboard can draw the commit strip. Keep demo and eval repos linear; for merge-heavy history, commits off the list are shown in a separate "other" row.
- **Renders the NEW reference first** by building `--bad` (normally HEAD). The OLD reference is the user's screenshot. If the user has no screenshot, `--good-render` builds and renders the good commit instead.
- Calls `git_ops.run_bisect(config)`. With `--ui`, it first starts `server.py` and opens the dashboard at the new run, so you watch it live.
- Other commands: `vbisect serve` (dashboard for all past runs) and `vbisect export` (static replay site).
- Prints the culprit: short SHA, author, date, message, files changed.

**Done when:** one command finds the culprit on a hand-made repo with no human input.

### 5.2 `config.py`
A `RunConfig` dataclass with everything the oracle needs (paths, commands, URL, focus, judge type, model name, run dir, viewport, fixed time). Written to `run.json` so `oracle.py` (a separate process started by git) can read it.

### 5.3 `git_ops.py`
- `make_worktree(repo, ref) -> path`: `git worktree add <tmp> <ref>` so the user's checkout is never touched.
- `run_bisect(cfg)`: inside the worktree run
  - `git bisect start --term-old=old --term-new=new <bad> <good>`
  - `git bisect run python -m vbisect.oracle --config <run.json>`
  - parse the "first new commit" line from the output
  - `git bisect reset`
- `commit_info(sha)`: author, date, subject, `--stat`, diff (truncated for the dashboard, with the full diff saved to the run folder).
- `cleanup()`: `git worktree remove`.

`git bisect run` exit codes: **0 = old (good)**, **1 = new (bad)**, **125 = skip**. Any code above 127 aborts the bisect, so the oracle must catch all exceptions and map them to 125.

### 5.4 `oracle.py`
```python
def main():
    cfg = load_config()
    sha = current_sha()
    try:
        url = builder.build_and_serve(cfg, sha)        # raises BuildFailed
        cand = renderer.screenshot(cfg, url, sha)
        verdict = judge(cfg, old_ref, new_ref, cand)   # "old" | "new" | "unsure"
    except BuildFailed:
        verdict = "skip-build"
    except Exception as e:
        verdict = "skip-error"
    finally:
        builder.stop_server()
    events.append(cfg, "step_done", sha=sha, verdict=verdict, **details)
    sys.exit({"old": 0, "new": 1}.get(verdict, 125))
```

### 5.5 `builder.py`
- Hash the lockfile (`package-lock.json`, `pnpm-lock.yaml` or `yarn.lock`). Keep a cache folder `~/.cache/vbisect/deps/<hash>/node_modules` and symlink or copy it into the worktree. Only run `--install-cmd` on a cache miss.
- Run `--build-cmd` with a timeout (default 120 s). Non-zero exit → `BuildFailed`.
- Start `--serve-cmd` on a free port, poll the URL until it responds (timeout 30 s).
- `stop_server()` kills the whole process group.

### 5.6 `renderer.py`
See [section 7](#7-stable-renders). Returns the PNG path.

### 5.7 `judge_gemma.py`
See [section 6](#6-the-gemma-judge-in-detail).

### 5.8 `judge_pixel.py`
Two baselines, both deliberately fair:
- **pixel-full:** SSIM of the candidate vs OLD and vs NEW over the whole page. Closer wins. If the two scores are within 0.005, return "unsure".
- **pixel-crop:** same, but only inside `--region`. This is the strongest fair baseline because it gets a hand-drawn box, which Gemma does not need.

### 5.9 `cache.py`
- Key = SHA-256 of (model name, prompt version, image bytes in order, focus text).
- Value = the raw model response and the parsed JSON.
- `--replay` reads only from the cache and fails loudly on a miss. This makes every published number exactly reproducible and enables an offline demo.

### 5.10 `events.py`
Appends one JSON line per event to `runs/<id>/events.jsonl`, each with a timestamp and a type. The event types are listed in [section 10.2](#102-event-types). Flush after every write so the server sees events immediately. This file is the single source of truth for the live view, replay and the static site.

### 5.11 `server.py` and `export.py`
See [section 10](#10-the-live-dashboard).

### 5.12 `tests/`
- Fake builder (returns a fixed image per commit) and fake judge (reads the truth file) so the bisect logic can be tested without network or Node.
- Test: exit-code mapping, skip handling, cache hit/miss, replay failure on a miss, judge JSON parsing with malformed output.

---

## 6. The Gemma judge in detail

### Why three images
Comparing a candidate to one reference asks "is this the same?", which fails because many unrelated things differ. Comparing it to **both** references asks "is this closer to OLD or NEW in this area?", which is a much easier and more reliable question.

- **Image A, OLD reference:** the user's screenshot (or a render of the good commit).
- **Image B, NEW reference:** a render of the bad commit (usually HEAD).
- **Image C, candidate:** a render of the commit being tested.

### Prompt (v1)
```
You are checking ONE area of a web page across versions of an app.

FOCUS AREA: {focus}

Image A shows the page BEFORE the change (OLD).
Image B shows the page AFTER the change (NEW).
Image C is the CANDIDATE version.

Compare ONLY the focus area.
Ignore every difference outside the focus area, and ignore dates, times,
numbers, counts, sample data and text content unless the focus area
description is about them.

Does the focus area in Image C look like OLD (Image A) or NEW (Image B)?

Reply with JSON only, no other text:
{"verdict": "old" | "new" | "unsure",
 "confidence": <number from 0 to 1>,
 "reason": "<one sentence naming the exact visual detail you used>"}
```
Keep the prompt in `vbisect/prompts/judge_v1.txt` and include the version in the cache key, so prompt changes never mix with old cached answers.

### Calling the API
```python
from google import genai
from google.genai import types

client = genai.Client()  # reads GEMINI_API_KEY
resp = client.models.generate_content(
    model=cfg.model,
    contents=[
        prompt_text,
        "Image A (OLD):", types.Part.from_bytes(data=old_png, mime_type="image/png"),
        "Image B (NEW):", types.Part.from_bytes(data=new_png, mime_type="image/png"),
        "Image C (CANDIDATE):", types.Part.from_bytes(data=cand_png, mime_type="image/png"),
    ],
    config=types.GenerateContentConfig(temperature=0),
)
```
Confirm tonight that the chosen Gemma 4 model accepts three images in one request. If it only accepts one, stitch the three images side by side into one PNG with labels drawn on top (Pillow) and adjust the prompt to "left / middle / right."

### Decision logic
1. **Call 1:** A = OLD, B = NEW (normal order).
2. **Call 2:** swap the positions (A = NEW, B = OLD) and map the answer back. This cancels position bias.
3. If both agree and both have confidence ≥ 0.6 → that verdict.
4. If they disagree → **Call 3** in the normal order. Majority of 3 wins, if it has confidence ≥ 0.6.
5. Otherwise → `"unsure"` → exit 125 (skip).

Why skip instead of guessing: one wrong answer sends a binary search to the wrong half and ruins the result. A skip only costs one extra build.

### Robustness
- Parse JSON with a fallback regex. If parsing fails, retry once with "Reply with JSON only."
- Retry API errors 3 times with exponential backoff (1 s, 2 s, 4 s).
- Downscale screenshots so the longest side is at most 1600 px to keep requests small.
- With `--region`, also send a crop of the focus area for each image (6 images, or a stitched version).

### Cost and speed estimate
About 7 steps × 2–3 calls = 14–21 calls per search. Check the Gemma rate limits on the event's API tier tonight and note them in the README.

---

## 7. Stable renders

Without these, the clock and animations create fake differences.

- Fixed viewport, for example 1280 × 800, device scale factor 1.
- Fixed time: Playwright's clock API, set to the same fixed date for every render.
- Disable animations and transitions with injected CSS:
  ```css
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
  }
  ```
- Wait for `networkidle`, then a short fixed delay (300 ms) for fonts.
- Hide scrollbars.
- Seed or freeze randomness if the app uses `Math.random` (inject a deterministic replacement via an init script).
- Full-page screenshot off by default (viewport only), on with a flag.

---

## 8. Builds, caching and skips

- **Dependency cache:** keyed by lockfile hash. Most nearby commits share a lockfile, so most steps skip the install.
- **Build timeout:** 120 s default, configurable.
- **Failed build →** exit 125. `git bisect` then tries a nearby commit.
- **Too many skips:** if more than 5 skips happen in one run, stop and report "could not narrow down further," listing the remaining candidate range. `git bisect` already reports a range when skips block a single answer; show that range in the dashboard.
- **Server cleanup:** always kill the server in a `finally` block, so ports are not leaked between steps.

---

## 9. Evaluation

This produces the headline number: **Gemma judge vs pixel-diff judge accuracy on repos with a known answer.**

### 9.1 Synthetic repos (`eval/make_repos.py`)

**Base app (`eval/base_app/`):** a small Vite vanilla-TS page with:
- Header with an "Updated: {date}" line
- Left sidebar (5–7 nav items with icons)
- Main area with 3–6 cards showing numbers
- Footer

**Each generated repo:**
- 100 commits by default (configurable).
- One **culprit commit** at a random position between commit 10 and 90.
- Every other commit is a **noise commit**.
- `truth.json` stores the culprit SHA, its index, the focus description, the culprit type and the seed.

**Noise mutations** (designed to fool pixel diffs):
- Change the displayed date
- Change card numbers
- Edit card text or the header subtitle
- Add, remove or reorder cards
- Change the footer color or main-area spacing
- Code-only changes with no visual effect (comments, refactors)
- **Hard noise:** change the sidebar's badge number when the focus is the sidebar *color* (tests whether Gemma follows the focus description)

**Culprit mutations** (always inside the focus area):
- Sidebar background color
- Sidebar width
- An icon removed
- Nav items reordered
- Font weight or size changed
- Padding changed (subtle: 4 px; obvious: 16 px)
- Item text truncated

**Hard culprits:**
- The change is in a shared `styles.css` and also affects another area
- The commit message is misleading ("chore: tidy imports")
- The change is subtle (4 px padding)

### 9.2 Dev / test split
- **Dev set:** 8 repos (seeds 1–8). Use these to tune the prompt.
- **Test set:** 12 repos (seeds 101–112), generated once and **never used for tuning**.
- Report only test-set numbers in the README. This answers "did you tune to your own test?"

### 9.3 Metrics (`eval/run_eval.py`)
For each judge (`gemma`, `pixel-full`, `pixel-crop`) and each test repo:

| Metric | Definition |
|---|---|
| Exact accuracy | Found commit == culprit |
| Steps | Number of oracle calls |
| Skips | Number of 125 exits |
| Per-step accuracy | Judge verdict vs truth for that commit (we know if it's before or after the culprit) |
| Wall time | Total seconds per search |
| API calls | Gemma calls per search |

Run the Gemma judge 3 times per repo (with cache off for runs 2 and 3) and report the mean and min–max range.

### 9.4 Results table template (`eval/summarize.py` writes this)
```
| Judge       | Exact culprit found | Per-step accuracy | Avg steps | Avg skips | Avg time |
|-------------|---------------------|-------------------|-----------|-----------|----------|
| Gemma 4     |  x/12 (range a–b)   |        x%         |    x.x    |    x.x    |   xx s   |
| Pixel-crop  |  x/12               |        x%         |    x.x    |    x.x    |   xx s   |
| Pixel-full  |  x/12               |        x%         |    x.x    |    x.x    |   xx s   |
```
Also break down Gemma's accuracy by culprit type (obvious / subtle / shared CSS / misleading message).

### 9.5 Real-world case
Pick one public repo that:
- builds with `npm ci && npm run build` in under about 60 seconds,
- has a visible UI change somewhere in its history (look at the CHANGELOG, release notes or a README screenshot that was replaced).

Steps:
1. Render the page at a commit before the change to get the OLD screenshot (or use the old README screenshot).
2. Run `vbisect` from that commit to a commit after the change.
3. Check the found commit by hand against the diff.
4. Present it as a **single case study**, clearly labeled n = 1, with its replay linked.

Pre-warm the dependency cache before the event so this runs fast.

---

## 10. The live dashboard

The CLI does the work; the dashboard makes it visible. It updates **live while the search runs**, and it can **replay** any past run. This is the main thing judges will see, so it gets real design effort.

### 10.1 How data flows
- `oracle.py` runs in a separate process that git starts for each commit, so it can't talk to the browser directly. Instead it appends events to `runs/<id>/events.jsonl`.
- `server.py` (FastAPI) tails that file and pushes each new line to the browser with **Server-Sent Events (SSE)**. SSE is one-way (server → browser), which is all we need, and it's simpler than WebSockets.
- Screenshots and the diff are served from the run folder.
- **Replay uses the same events file**: the frontend reads it and plays it back at a chosen speed instead of waiting for live events. Same components, different data source.
- The frontend works out the remaining commit range itself from the verdicts (everything at or before an OLD commit is ruled out, everything at or after a NEW commit is ruled out), so the oracle doesn't need to know git's internal range.

### 10.2 Event types
| Type | Fields |
|---|---|
| `run_started` | `run_id`, `commits` (ordered list of `sha`, `subject`, `date`, `author`), `good`, `bad`, `focus`, `url`, `old_ref_img`, `new_ref_img`, `judge` |
| `step_started` | `sha`, `step_no`, `est_total` |
| `build_progress` | `sha`, `phase` (`install` / `install-cached` / `build` / `serve`), `seconds` |
| `render_done` | `sha`, `img` |
| `judge_call` | `sha`, `call_no`, `order` (`normal` / `swapped`), `verdict`, `confidence`, `reason`, `seconds` |
| `step_done` | `sha`, `verdict` (`old` / `new` / `skip`), `skip_reason` |
| `run_done` | `culprit_sha` (or `range` if skips blocked a single answer), `steps`, `skips`, `api_calls`, `seconds`, `diff_file` |
| `run_failed` | `error` |

Every event also has `ts` (timestamp) and `type`.

### 10.3 API (`server.py`)
| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/runs` | List runs (id, date, focus, status, culprit) |
| `GET` | `/api/runs/{id}` | All events so far (used on page load and for replay) |
| `GET` | `/api/runs/{id}/stream` | SSE stream of new events |
| `GET` | `/api/runs/{id}/files/{path}` | Screenshots, diff |
| `GET` | `/api/eval` | `eval/results.json` for the Judge Arena |
| `POST` | `/api/runs` | Start a run (only for the stretch New Run screen; the CLI can start runs too) |

In development, the Vite dev server proxies `/api` to FastAPI. In production, FastAPI serves the built `web/dist` folder.

### 10.4 Screens

**1. Live Run (the demo screen)**
- **Commit strip** across the top: every commit between good and bad as a small tile. Ruled-out commits fade and shrink; the remaining range glows and **visibly narrows after each step** (Framer Motion layout animation). The commit being tested pulses.
- **Counters**: "Step 4 of ~7", "9 commits left", elapsed time.
- **Status line** for the current commit: installing (cached) → building → rendering → judging, each with its time.
- **Judge panel**: OLD | CANDIDATE | NEW side by side, with the focus description above them.
  - Gemma's reason appears word by word as each call finishes.
  - The two votes (normal and swapped order) show as **confidence bars**; a third bar appears if a tie-breaker call was needed.
  - The verdict badge flips to OLD (green-teal), NEW (red-orange) or SKIP (grey).
- **Step timeline** down the side: every finished step with thumbnail, verdict and one-line reason. Click any step to inspect it.

**2. Culprit reveal**
- When the search ends, the strip collapses onto one commit and a card slides in: short SHA, message, author, date, files changed.
- **Compare view** of "commit just before the culprit" vs "the culprit", with four modes:
  - drag slider (react-compare-slider)
  - side by side
  - onion skin (opacity slider blending the two)
  - difference heatmap (computed in the browser on a canvas, changed pixels highlighted)
- **Diff view** with syntax highlighting (diff2html).
- If skips blocked a single answer, show the remaining range as a short list instead, honestly labeled.

**3. Judge Arena (evaluation results)**
- Bar chart: exact culprit found out of 12 for Gemma vs pixel-crop vs pixel-full, with min–max whiskers for Gemma's 3 runs (Recharts).
- Breakdown by culprit type (obvious, subtle, shared CSS, misleading message).
- Per-step accuracy and average steps and skips per judge.
- **Fooled gallery**: steps where the pixel judge was wrong and Gemma was right, each showing the three images and both verdicts. Also include steps where Gemma was wrong, for honesty.
- Click any test case to open its replay.

**4. Replay**
- Any past run, played from its events file.
- Scrubber, play/pause, speed 1× / 2× / 4×, jump to step.
- Uses the exact same Live Run and Culprit components.

**5. New Run (stretch)**
- Drop the old screenshot, fill in repo path, refs, URL and focus.
- **Draw a box on the screenshot** to set `--region`.
- Start → jumps straight to Live Run.

### 10.5 Static replay site
`vbisect export --runs runs/demo runs/real-case --eval eval/results.json --out site/`
- Builds the frontend with a `StaticSource` that reads bundled `events.jsonl` files and images, so no backend is needed.
- Deploy `site/` to GitHub Pages. Judges get a link where they can replay the searches and explore the Judge Arena themselves, even after the event.

Implementation: the frontend talks to a small `DataSource` interface with two implementations, `LiveSource` (SSE + API) and `StaticSource` (fetch files + timed playback). Every screen uses only the interface.

### 10.6 Frontend structure
```
web/src/
├── api/
│   ├── types.ts        # event types mirroring section 10.2
│   ├── source.ts       # DataSource interface
│   ├── live.ts         # LiveSource: fetch + EventSource (SSE)
│   └── static.ts       # StaticSource: fetch files, replay with timers
├── state/runStore.ts   # Zustand: events → derived state (range, steps, culprit)
├── screens/
│   ├── RunList.tsx  LiveRun.tsx  Culprit.tsx  JudgeArena.tsx  Replay.tsx  NewRun.tsx
└── components/
    ├── CommitStrip.tsx  JudgePanel.tsx  VoteBars.tsx  StatusLine.tsx
    ├── StepTimeline.tsx  CompareView.tsx  DiffView.tsx  Heatmap.tsx
```
Keep all derived logic (remaining range, step count, culprit) in the store as pure functions of the event list, so live and replay always agree and it's easy to unit-test.

### 10.7 Design notes
- **Dark theme by default** (looks better on projectors), large type, one accent color for OLD (green-teal) and one for NEW (red-orange), grey for SKIP.
- **Presentation mode** (press `P`): hides developer details, enlarges the commit strip and judge panel.
- Must look right at **1280×720**, the most common projector resolution.
- Keep animations under about 400 ms so the demo feels snappy.
- If events arrive faster than animations finish, queue them; never drop or block.
- If the SSE connection drops, reconnect and reload all events from `/api/runs/{id}`, so a refresh never loses the run.

---

## 11. Stretch: text mode

Same bisect loop and the same decision logic, different input.

```
vbisect --mode text --cmd "node cli.js --summary" \
        --old-output march.txt --focus "the totals line"
```
- The oracle runs `--cmd` instead of building and rendering.
- The judge receives OLD output, NEW output and the candidate output as text, with the same prompt adapted to text and the same "ignore dates and paths" rule.
- Add 4–6 synthetic text cases to the eval if time allows.

Use this as a 20-second bonus in the demo, not the main story.

---

## 12. SKILL.md

`skills/visual-bisect/SKILL.md` (check the exact required fields against the Agent Skill Open Standard before submitting):

```markdown
---
name: visual-bisect
description: Find the git commit that changed how part of a web page looks, starting from one old screenshot. Use when a UI regression has no error message and the commit that caused it is unknown.
---

# Visual Bisect

## When to use
- A part of a web app's UI changed or broke, with no error or failing test.
- You have (or can render) a screenshot of how it looked before.
- The project builds and serves locally.

## Inputs to collect
1. Repo path, a known-good ref and a known-bad ref (usually HEAD)
2. An old screenshot, or a ref to render one from
3. The page URL path
4. A one-line description of the area that changed
5. Install, build and serve commands if they differ from the defaults

## Steps
1. Run:
   vbisect --repo <path> --good <ref> --bad <ref> --screenshot <png> --url <path> --focus "<area>"
2. Read the culprit commit from the output.
3. Run `vbisect serve` and open the run in the dashboard to check the before/after renders.
4. Show the user the commit, its diff and the judge's reasons.

## Limits
- Web apps only; pages behind login are not supported.
- Commits that fail to build are skipped.
- If the result is a range instead of one commit, report the range.
```

---

## 13. README outline

1. **Title + one-line pitch + demo GIF of the dashboard** (the range shrinking and the culprit reveal, about 10 seconds) + **link to the live replay site**
2. **The problem** (3 sentences: diffs don't say which commit, bisect needs a judge, pixel diffs fail)
3. **Quickstart** (copy-paste, working in under 1 minute on the bundled demo repo)
4. **How it works** (the flow diagram from section 4 + the 3-image judge explained in 4 lines)
5. **Results** (the table from 9.4, culprit-type breakdown, the real-world case study, and the exact reproduce command)
6. **Limitations** (web only, build must work, subtle changes need a clear focus description, synthetic eval + 1 real case)
7. **Prior art** (git bisect, visual regression tools, pixel diffs, and exactly what this adds)
8. **Use as an agent skill** (link to SKILL.md)
9. **Contributing** (good first issues: text mode, more judges, GitHub Action, other frameworks)
10. **License**
11. **Note:** "Pre-event work started with organizer approval." (only if confirmed)

---

## 14. Day-by-day timeline

### Wed 28 Oct (tonight, about 3–4 hours): prove the risky part
- [ ] Message Farhaan or Sri Ram: the idea changed from Skill Compiler to Visual Bisect. Confirm pre-event work is still okay.
- [ ] Get the exact Gemma 4 model name from the event's Gemma docs. Put it in `.env`.
- [ ] Test one API call with three images. If multi-image isn't supported, test the stitched single-image version.
- [ ] **Judge spike:** make 5 hand-made screenshot sets (OLD, NEW, candidate) with the base app:
  - 2 obvious (sidebar color), 1 subtle (4 px padding), 1 where only the date differs (should match OLD), 1 with hard noise
- [ ] Run the prompt from section 6 on all 5, with the order swap.
- [ ] Create the repo: LICENSE, `.gitignore` (include `.env`, `runs/`, `eval/cases/*/` except truth files), folder skeleton, `.env.example`.

**Decision gate:** if Gemma gets fewer than 4 of 5 right after two prompt tweaks, stop and decide whether to continue, crop to `--region` by default, or switch back to Skill Compiler. Don't build further until this passes.

### Thu 29 Oct: one full search working end to end
- [ ] `config.py`, `git_ops.py` (worktree, bisect start/run/reset)
- [ ] `builder.py` (install with cache, build, serve, stop)
- [ ] `renderer.py` (stable settings from section 7)
- [ ] `judge_gemma.py` (3-image prompt, swap, decision logic, JSON parsing, retries)
- [ ] `cache.py` + `--replay`
- [ ] `oracle.py` (exit codes, catch everything)
- [ ] `events.py` writing all event types from section 10.2 (the dashboard depends on these, so get them right now)
- [ ] `cli.py`
- [ ] Hand-build one test repo (about 30 commits) with a known culprit
- [ ] Unit tests with the fake judge and fake builder

**Done when:** `vbisect` finds the right commit on that repo with no human input, and `--replay` reproduces it offline.

### Fri 30 Oct: evaluation and evidence
- [ ] `eval/base_app/` and `make_repos.py` (noise + culprit mutations, `truth.json`)
- [ ] Generate dev set (8) and test set (12)
- [ ] `judge_pixel.py` (pixel-full, pixel-crop)
- [ ] `run_eval.py` and `summarize.py`
- [ ] Tune the prompt **on the dev set only**. Save each prompt as a new version file.
- [ ] Run the final prompt on the test set: 3 Gemma runs + both pixel baselines
- [ ] `server.py`: API + SSE stream (section 10.3)
- [ ] Dashboard skeleton (Vite, Tailwind, Zustand store, live + static data sources)
- [ ] **Live Run screen**: commit strip, judge panel, counters

**Done when:** the results table has real numbers from the test set, and you can watch a real run live in the browser. **Backend feature freeze tonight; Saturday is dashboard and docs only.**

### Sat 31 Oct: real case, docs, rehearsal
- [ ] **Culprit reveal screen**: slider, side by side, onion skin, diff view
- [ ] **Judge Arena screen**: charts, culprit-type breakdown, fooled gallery
- [ ] **Replay screen**: scrubber, play/pause, speed
- [ ] Presentation mode; test at 1280×720
- [ ] `vbisect export` → deploy the static replay site to GitHub Pages
- [ ] Real-world case (section 9.5); cache it for replay
- [ ] Text mode, **only if everything above is done**
- [ ] README (section 13) with real numbers and the demo GIF
- [ ] SKILL.md (section 12), checked against the standard
- [ ] Record a backup demo video (2–3 minutes)
- [ ] Rehearse the demo twice with a timer
- [ ] Run the demo once with Wi-Fi off using `--replay`
- [ ] Fresh clone on another laptop; follow the README exactly and fix anything that breaks
- [ ] Sleep

### Sun 1 Nov: event day
Check the final schedule on the event page. The earlier plan was: Sprint 1 11:45–1:30, Sprint 2 2:15–3:45, submission at 3:45.

- [ ] **Morning (before check-in, 20 min):** pull `main`, run the test suite, run one replay, charge laptops, open the dashboard in presentation mode
- [ ] **Sprint 1:** polish the dashboard (presentation mode, animation timing) and the demo flow; fix only real bugs
- [ ] **Lunch:** one more full rehearsal
- [ ] **Sprint 2:** final README numbers and screenshots, submission text, tag a release (`v0.1.0`)
- [ ] **Submit at least 15 minutes before the deadline**

---

## 15. Demo script

**Setup before going on stage:** dependency cache warm, the demo repo ready, the dashboard open in presentation mode, the real-case replay and the Judge Arena in other tabs, `--replay` ready in case the network fails.

| Time | What to say | What's on screen |
|---|---|---|
| 0:00–0:30 | "This sidebar looked right in March. Now it's broken. 140 commits since then. No error to trace." | Old screenshot next to current page |
| 0:30–0:50 | "A diff doesn't say which commit caused it. `git bisect` can search, but a human has to judge good or bad at every step." | One slide with the two problems |
| 0:50–1:50 | "Watch." Run `vbisect --ui`. Narrate 2–3 of Gemma's reasons as they appear, and point at how many commits are left. | Live Run: the range shrinking, judge panel, then the culprit reveal with the drag slider |
| 1:50–2:20 | "Across 12 test repos, Gemma found the exact commit in X; a pixel diff found Y. Here's a step where pixel diff was fooled by a date change." | Judge Arena chart, one frame from the fooled gallery |
| 2:20–2:40 | "Also works on a real project," (and if built) "and on CLI output, not just UI." | Real-case replay at 4× speed |
| 2:40–3:00 | "Open source, an agent skill, and you can replay all of this yourself at this link. `git bisect` knows how to search. We taught it to see." | Replay site link, repo page, SKILL.md |

**Roles:** one speaker, one operator at the laptop, one person ready to answer number questions.

---

## 16. Judge Q&A prep

**"We already have `git bisect`."**
We use it. `git bisect` does the search, but at every step it needs someone to say good or bad. For visual changes you can't script that, so today a human does it 7–8 times. We automated the judge.

**"Can't you just look at the diff on GitHub?"**
For one commit, yes. Across 100+ commits a diff shows thousands of changed lines and never says which one changed what you see. The culprit is often a dependency bump or a shared CSS edit that looks unrelated.

**"Why not a pixel diff?"**
Dates, data and other parts of the page change in every commit. Our results table shows the pixel baseline failing, even with a hand-drawn crop box.

**"Why not Percy or Chromatic?"**
They need baselines set up before the bug. This works backwards from any old screenshot with zero setup.

**"What if Gemma is wrong?"**
It judges twice with the image order swapped, takes a third vote on disagreement and skips when unsure. Skips cost one extra build; wrong answers would ruin the search, so we avoid guessing.

**"What if old commits don't build?"**
They're skipped with bisect's own skip code, and the dashboard shows the remaining range if one commit can't be pinned down.

**"Isn't your eval synthetic?"**
Mostly, because it needs known answers. We kept a separate test set we never tuned on, ran it 3 times and added one real-world case labeled as n = 1.

**"How long does it take?"**
About 7 steps for 100 commits. On the demo app that's about 1–2 minutes; on bigger apps it depends on build time, and dependency caching helps.

**"Does it only work for UI?"**
The idea works for any change you can't script a test for. We built UI first and (if done) CLI output as a second mode.

---

## 17. Risks and fallbacks

| Risk | Likelihood | Fallback |
|---|---|---|
| Gemma misjudges subtle changes | Medium | Clear `--focus` text, `--region` crop, skip when unsure; report accuracy by culprit type honestly |
| Model rejects multiple images per request | Medium | Stitch into one labeled image |
| Old commits don't build | Medium | Skip; choose demo apps with stable builds |
| Builds too slow live | Low–medium | Pre-warmed cache; show the real case via `--replay` |
| API rate limits on event day | Medium | Cache + `--replay`; separate API keys per person |
| Venue Wi-Fi fails | Medium | Offline replay + backup video |
| Judge spike fails tonight | Low–medium | Decision gate in section 14; Skill Compiler remains the fallback |
| Dashboard takes longer than planned | Medium–high | Live Run and Culprit reveal are must-haves. Judge Arena can fall back to one bar chart. Onion skin and heatmap are optional. The terminal output still works if the UI breaks on stage |
| Running out of time | Medium | Cut in this order: text mode → New Run screen → GitHub Action → onion skin/heatmap → fooled gallery → real-world case polish. Never cut the eval, the Live Run screen or the README |

---

## 18. Honesty rules

1. Only report numbers that were actually measured. Every number in the README must come from `results.json` and be reproducible with `--replay`.
2. Label synthetic results and the real case separately. Never mix them into one number.
3. Report test-set numbers only, not dev-set numbers.
4. Show failures too: the culprit-type breakdown should include where Gemma is weakest.
5. If pre-event work is mentioned, it must match what organizers approved.

---

## 19. Submission checklist

- [ ] Public GitHub repo, open-source LICENSE
- [ ] README with quickstart, results table, limitations, prior art
- [ ] Demo GIF of the dashboard in the README; backup video uploaded
- [ ] Static replay site live on GitHub Pages and linked in the README and submission
- [ ] SKILL.md following the Agent Skill Open Standard
- [ ] Gemma 4 usage stated clearly (model name, what it decides)
- [ ] `results.json` and the reproduce command committed
- [ ] Release tag `v0.1.0`
- [ ] Submission form filled: description, both tracks, repo link, video link, team members
- [ ] `.env` and API keys **not** committed (check `git log` before making the repo public)
