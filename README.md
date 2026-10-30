# Visual Bisect

**Find the commit that changed what you see, from one old screenshot.**
`git bisect` does the search. Gemma 4 decides "good or bad" at each step by looking at the rendered page.

> Status: work in progress for a hackathon. Results and the dashboard are being added; sections marked
> *pending* are not done yet and contain no numbers on purpose.

## The problem
A part of the UI changed or broke and nobody noticed for weeks. There is no error to trace, and a code diff
shows what changed, not which change caused the visible effect. `git bisect` can do the binary search, but at
every step a person has to build the app, open the page and judge "does this look right?". Pixel diffs fail
because dates, data and unrelated parts of the page change between commits.

## What it does
Give it an old screenshot, a page URL and a short description of what changed ("the left sidebar").
It runs a real `git bisect run`. At each commit it builds the app, renders the page with Playwright
(fixed viewport, clock and animations) and asks Gemma 4 whether the focus area looks like the OLD or the NEW
version. It returns the culprit commit and its diff.

## Quickstart
```bash
python -m venv <short path>      # on Windows keep the path short, or Pillow's DLL may fail to load
<venv>/Scripts/activate           # Linux/macOS: source <venv>/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env              # add GEMINI_API_KEY and GEMMA_MODEL (e.g. gemma-4-26b-a4b-it)
```

Try it on a generated repo with a known culprit:
```bash
python eval/make_repos.py --out eval/cases --seeds 1 --commits 30 --type color
vbisect --repo eval/cases/seed1 --good $(git -C eval/cases/seed1 rev-list --max-parents=0 HEAD) \
        --bad HEAD --good-render --focus "the left sidebar" --judge gemma --out runs/demo
```
The answer for that repo is in `eval/cases/seed1.truth.json`. Output goes to `runs/demo/`
(`events.jsonl`, renders, `culprit.diff`).

Use your own screenshot instead of `--good-render`: `--screenshot old.png`.

### Presets
`--preset vite` (default), `next` or `static` (plain HTML, nothing to build). Any of
`--install-cmd`, `--build-cmd`, `--serve-cmd` overrides the preset; use `{port}` in the serve command.

## How it works
```
vbisect CLI -> git worktree -> git bisect run python -m vbisect.oracle
   for each commit git picks:  build + serve -> Playwright screenshot -> judge
   exit code: 0 = old, 1 = new, 125 = skip (build failed, or the judge was unsure)
   events are appended to runs/<id>/events.jsonl  (live view and replay read this)
```
**The judge compares three images:** OLD reference, NEW reference and the candidate, and answers "is the
focus area closer to OLD or NEW?". That is easier and more reliable than "is this the same?".
It asks twice with the image order swapped to cancel position bias, takes a third vote on disagreement, and
**skips when unsure**, because one wrong answer sends a binary search to the wrong half.

Responses are cached by input hash. `--replay` uses only cached answers, so a run can be reproduced offline.

## Results
*Pending.* The evaluation compares the Gemma judge with full-page and cropped pixel-diff baselines on
generated repos with a known culprit (separate dev and test sets; only test-set numbers will be reported),
plus one real-world case labelled n = 1. Run `python eval/summarize.py eval/results.json` once it exists.

**Real-world case (n = 1, not a measured accuracy).** On [homow/dashboard-skeleton](https://github.com/homow/dashboard-skeleton),
range `4ce2f40..8fa9e4a` (4 commits), the sidebar logo, text size and icons change subtly
([before](docs/real-case/old.png), [after](docs/real-case/new.png)). The full-page pixel judge answered
"unsure" at every step; the Gemma judge found `32632f7` ("update and config", which edits `SideBarHeader.jsx`)
in 2 steps. Reproduce with `powershell -File eval/real_case.ps1 <venv-python> gemma`.

## Limitations
- Web apps that build and serve locally with a command. No login-gated pages, mobile or desktop apps, or
  projects that need a database or secrets.
- Commits that fail to build are skipped; if too many are skipped the result is a range, not one commit.
- Subtle changes need a clear focus description. The model is an API call, so latency varies and the
  API sometimes returns transient errors (the code retries and times out long calls).
- Generated test repos are synthetic; claims about real projects need real projects.

## Prior art
`git bisect` (search, but needs a scriptable judge), visual regression tools such as Percy and Chromatic
(need baselines set up before the bug), pixel diffs (fooled by unrelated changes). Visual Bisect works
backwards from any old screenshot with no setup.

## Use as an agent skill
See [`skills/visual-bisect/SKILL.md`](skills/visual-bisect/SKILL.md).

## Contributing
Ideas: more presets, other judges and local models, a GitHub Action, text/CLI-output mode. See
[`WORK_SPLIT.md`](WORK_SPLIT.md) for the current plan.

## License
MIT. See [`LICENSE`](LICENSE).
