"""Drive a real browser through the demo and assert what a visitor should see (L2).

Starts the command center with ``make demo``'s command (no API key, headless
Streamlit on port 8631), waits for ``/_stcore/health`` to answer ``ok``, then
with Playwright Chromium:

1. visits every top-level page in the sidebar and asserts its title renders
   with no Streamlit exception box;
2. on "Verified Rules" opens a rule family and asserts that a verified rule is
   shown with its quoted source text, and that the quote is one of the quotes
   recorded for verified rules in the committed run manifest;
3. saves three screenshots and one video under ``docs/demo/``.

Every browser request is checked against ``ALLOWED_HOSTS``. A request to any
other host is aborted and recorded, and the check fails if any was attempted.

Usage: ``python scripts/demo_check.py [--port 8631] [--out docs/demo]``.
Needs ``pip install -r requirements-demo.txt`` and
``python -m playwright install chromium``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT / "outputs" / "f1_runs" / "burnaby_r1" / "checkpoint_16_product_operations"
    / "command_center_app_manifest.json"
)
# The only hosts a visitor's browser may reach during the demo: the local app
# and the two Google Fonts hosts the dashboard stylesheet imports.
ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "fonts.googleapis.com", "fonts.gstatic.com"})
PAGES = [
    ("0 Command Center", "Bylaw Intelligence Command Center"),
    ("1 Sources", "Source Documents"),
    ("2 Verified Rules", "Verified Rules"),
    ("3 Review Workbench", "Review Workbench"),
    ("4 Repair Evidence", "Repair Evidence"),
    ("5 GIS + Compliance", "GIS + Compliance"),
    ("6 Quality Audit", "Quality Checks"),
]
SCREENSHOTS = {
    "0 Command Center": "01-command-center.png",
    "2 Verified Rules": "02-verified-rule-with-source-text.png",
    "3 Review Workbench": "03-review-workbench.png",
}
SECRET_ENV = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")


def demo_command(port: int) -> list[str]:
    return [
        sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
        "--server.port", str(port), "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]


def wait_for_health(port: int, timeout: float = 90.0) -> str:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/_stcore/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - loopback only
                body = response.read().decode().strip()
                if body == "ok":
                    return body
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{url} did not answer ok within {timeout:.0f}s")


def verified_quotes() -> set[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        str((rule.get("citation") or {}).get("quote") or "").strip()
        for rule in manifest.get("verified_rules") or []
        if (rule.get("citation") or {}).get("quote")
    }


def host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"data", "blob", "about"}:
        return True
    return (parsed.hostname or "") in ALLOWED_HOSTS


def run_browser(port: int, out: Path) -> dict:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 - optional dependency

    blocked: list[str] = []
    contacted: set[str] = set()
    visited: list[str] = []
    quote_seen = ""
    video_tmp = Path(tempfile.mkdtemp(prefix="demo-video-"))

    def guard(route) -> None:
        url = route.request.url
        if host_allowed(url):
            contacted.add(urlparse(url).hostname or urlparse(url).scheme)
            route.continue_()
        else:
            blocked.append(url)
            route.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(video_tmp),
            record_video_size={"width": 1280, "height": 800},
        )
        context.route("**/*", guard)
        page = context.new_page()
        page.goto(f"http://localhost:{port}/", wait_until="domcontentloaded")
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.wait_for(timeout=60_000)

        for nav_label, title in PAGES:
            sidebar.get_by_text(nav_label, exact=True).click()
            page.locator('[data-testid="stMain"]').get_by_text(title).first.wait_for(timeout=30_000)
            page.wait_for_timeout(1_500)  # let Streamlit finish the rerun
            exceptions = page.locator('[data-testid="stException"]').count()
            if exceptions:
                raise AssertionError(f"{nav_label}: {exceptions} Streamlit exception box(es) rendered")
            if nav_label == "2 Verified Rules":
                page.locator('[data-testid="stExpander"] summary').first.click()
                quote = page.locator(".rule-quote").first
                quote.wait_for(timeout=15_000)
                text = quote.inner_text().strip()
                inner = text.split("“", 1)[-1].rstrip("”").strip()
                if not inner or inner not in verified_quotes():
                    raise AssertionError(f"verified rule quote not found in committed manifest: {text!r}")
                quote_seen = text
                quote.scroll_into_view_if_needed()
            if nav_label in SCREENSHOTS:
                page.screenshot(path=str(out / SCREENSHOTS[nav_label]))
            visited.append(nav_label)

        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()

    if video_path:
        shutil.move(str(video_path), out / "demo-journey.webm")
    shutil.rmtree(video_tmp, ignore_errors=True)
    if blocked:
        raise AssertionError(f"requests to hosts outside the allowlist: {sorted(set(blocked))}")
    return {"visited": visited, "verified_quote": quote_seen, "hosts_contacted": sorted(contacted)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8631)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "demo")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
    server = subprocess.Popen(  # noqa: S603 - fixed local command
        demo_command(args.port), cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )
    try:
        print(f"health: {wait_for_health(args.port)}")
        result = run_browser(args.port, args.out)
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
    for nav in result["visited"]:
        print(f"PASS page rendered: {nav}")
    print(f"PASS verified rule shown with source text: {result['verified_quote']}")
    print(f"PASS only allowlisted hosts contacted: {', '.join(result['hosts_contacted'])}")
    for name in [*SCREENSHOTS.values(), "demo-journey.webm"]:
        path = args.out / name
        print(f"saved {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
