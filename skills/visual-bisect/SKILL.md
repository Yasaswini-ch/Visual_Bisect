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
3. Open `runs/<id>/` to check the before/after renders and the judge's reasons in `events.jsonl`.
4. Show the user the commit, its diff and the judge's reasons.

## Limits
- Web apps only; pages behind login are not supported.
- Commits that fail to build are skipped.
- If the result is a range instead of one commit, report the range.
