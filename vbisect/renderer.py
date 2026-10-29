"""Stable Playwright screenshots: fixed viewport, clock, no animations, seeded random."""
from __future__ import annotations

from pathlib import Path

FREEZE_CSS = """
*, *::before, *::after {
  animation: none !important; transition: none !important; caret-color: transparent !important;
}
html { scrollbar-width: none; } ::-webkit-scrollbar { display: none; }
"""

SEED_RANDOM = """
(() => { let s = 123456789;
  Math.random = () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; }; })();
"""


def screenshot(url: str, out: Path, viewport=(1280, 800), fixed_time="2026-01-15T12:00:00Z",
               full_page: bool = False) -> Path:
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                  device_scale_factor=1)
        page = ctx.new_page()
        page.clock.install(time=fixed_time)
        page.add_init_script(SEED_RANDOM)
        page.goto(url, wait_until="networkidle")
        page.add_style_tag(content=FREEZE_CSS)
        page.wait_for_timeout(300)
        page.screenshot(path=str(out), full_page=full_page)
        browser.close()
    return out
