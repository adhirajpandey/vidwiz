# /// script
# requires-python = ">=3.13"
# dependencies = ["playwright==1.61.0", "python-dotenv>=1.1.1,<2.0.0"]
# ///
"""Capture VidWiz v3 pages using a dedicated test account.

Copy scripts/.env.example to scripts/.env and configure the API, credentials,
video, and a search word present in that account's library. Install Chromium:
  uv run --with playwright==1.61.0 playwright install chromium

Run from the repository root:
  uv run scripts/screenshot_pages.py --list
  uv run scripts/screenshot_pages.py --all --sizes desktop mobile --themes dark light
  uv run scripts/screenshot_pages.py --pages video-overview library home --sizes desktop
  uv run scripts/screenshot_pages.py --pages ask-answer --sizes desktop mobile --themes dark light

Dark is the default theme. Output stays under scripts/outputs/ui-images.
The default mode captures overlapping viewport slices; --mode full captures the
whole document. Scrollable panels are also captured in slices mode. The command
palette captures one viewport, since scrolling only changes its background.
--all excludes ask-answer (one real question per run) and video-ask (the Ask tab).
The video-ask state never clicks Unlock or sends a question.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

from dotenv import load_dotenv
from playwright.sync_api import Browser, Page, Request, Route, sync_playwright
from playwright.sync_api import Error as PlaywrightError

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).with_name(".env"), override=False)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViewportPreset:
    width: int
    height: int
    scale: int = 1


@dataclass(frozen=True)
class PageCapture:
    path: str
    ready: str
    authenticated: bool = True
    opt_in: bool = False


@dataclass(frozen=True)
class RuntimeConfig:
    ui_base_url: str
    api_base_url: str
    output_dir: Path
    video_id: str
    search_query: str
    navigation_timeout_ms: int
    scroll_overlap_px: int
    post_scroll_settle_ms: int
    max_screenshots_per_page: int


VIEWPORT_PRESETS = {
    "desktop": ViewportPreset(1920, 1080),
    "tablet": ViewportPreset(768, 1024, 2),
    "mobile": ViewportPreset(390, 844, 2),
}
PAGE_CAPTURES = {
    "landing": PageCapture("/", 'h1:has-text("You just heard")', False),
    "login": PageCapture("/login", 'h1:has-text("Welcome back")', False),
    "signup": PageCapture("/signup", 'h1:has-text("Create your account")', False),
    "privacy": PageCapture("/privacy", 'h1:has-text("Your Privacy Matters")', False),
    "home": PageCapture("/", "h1"),
    "library": PageCapture("/library", 'h1:has-text("Library")'),
    "search": PageCapture("/search?q={search_query}", 'h1:has-text("Results for")'),
    "ask": PageCapture("/ask", 'h1:has-text("Ask your library")'),
    "ask-answer": PageCapture("/ask", 'h1:has-text("Ask your library")', opt_in=True),
    "video-moments": PageCapture(
        "/v/{video_id}?tab=moments", '[role="tabpanel"][data-state="active"]'
    ),
    "video-transcript": PageCapture(
        "/v/{video_id}?tab=transcript", 'input[aria-label="Find in transcript"]'
    ),
    "video-overview": PageCapture("/v/{video_id}?tab=overview", "#key-points"),
    "video-ask": PageCapture(
        "/v/{video_id}?tab=ask", '[role="tabpanel"][data-state="active"]', opt_in=True
    ),
    "settings": PageCapture("/settings", 'h1:has-text("Settings")'),
    "command-palette": PageCapture("/", "h1"),
}


def env_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value < 0:
        raise ValueError(f"{name} must not be negative.")
    return value


def build_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        ui_base_url=os.environ.get(
            "VIDWIZ_UI_BASE_URL", "http://localhost:5174"
        ).rstrip("/"),
        api_base_url=os.environ.get(
            "VIDWIZ_API_BASE_URL", "http://localhost:5000/v2"
        ).rstrip("/"),
        output_dir=ROOT_DIR
        / os.environ.get("VIDWIZ_UI_IMAGE_OUTPUT_DIR", "scripts/outputs/ui-images"),
        video_id=os.environ.get("VIDWIZ_AUTOMATION_VIDEO_ID", "").strip(),
        search_query=os.environ.get("VIDWIZ_AUTOMATION_SEARCH_QUERY", "").strip(),
        navigation_timeout_ms=env_int(
            "VIDWIZ_AUTOMATION_NAVIGATION_TIMEOUT_MS", 30_000
        ),
        scroll_overlap_px=env_int("VIDWIZ_AUTOMATION_SCROLL_OVERLAP_PX", 140),
        post_scroll_settle_ms=env_int("VIDWIZ_AUTOMATION_POST_SCROLL_SETTLE_MS", 400),
        max_screenshots_per_page=env_int(
            "VIDWIZ_AUTOMATION_MAX_SCREENSHOTS_PER_PAGE", 30
        ),
    )


def login(config: RuntimeConfig) -> str:
    credentials = {}
    for field in ("email", "password"):
        key = f"VIDWIZ_AUTOMATION_{field.upper()}"
        credentials[field] = os.environ.get(key, "")
        if not credentials[field]:
            raise ValueError(f"Missing required environment variable: {key}")
    request = urllib.request.Request(
        f"{config.api_base_url}/auth/login",
        data=json.dumps(credentials).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "VidWiz-Screenshots/3",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=config.navigation_timeout_ms / 1000
        ) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # Never log the login body: it can contain credentials or a token.
        raise RuntimeError(f"Automation login failed with HTTP {error.code}.") from None
    token = result.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Automation login did not return a token.")
    return token


def build_init_script(token: str | None, theme: str) -> str:
    token_json = json.dumps(token)
    theme_json = json.dumps(theme)
    return f"""
    (() => {{
      if (window !== window.top) return;
      const token = {token_json};
      const theme = {theme_json};
      localStorage.setItem('theme', theme);
      sessionStorage.removeItem('guestSessionId');
      if (token) localStorage.setItem('token', token);
      else localStorage.removeItem('token');
      const installStyles = () => {{
        document.documentElement.classList.toggle('dark', theme === 'dark');
        const style = document.createElement('style');
        style.dataset.vidwizScreenshots = 'true';
        style.textContent = `
          *, *::before, *::after {{
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition-duration: 0s !important;
            scroll-behavior: auto !important;
            caret-color: transparent !important;
          }}
        `;
        document.head.appendChild(style);
      }};
      if (document.head) installStyles();
      else document.addEventListener('DOMContentLoaded', installStyles, {{ once: true }});
    }})();
    """


def wait_for_visual_stability(page: Page, config: RuntimeConfig) -> None:
    page.evaluate("() => document.fonts?.ready || Promise.resolve()")
    page.evaluate(
        """
        (timeoutMs) => Promise.race([
          Promise.all(Array.from(document.images).map((image) => {
            if (image.complete) return Promise.resolve();
            return new Promise((resolve) => {
              image.addEventListener('load', resolve, { once: true });
              image.addEventListener('error', resolve, { once: true });
            });
          })),
          new Promise((resolve) => setTimeout(resolve, timeoutMs)),
        ])
        """,
        min(config.navigation_timeout_ms, 5_000),
    )
    page.wait_for_timeout(config.post_scroll_settle_ms)


def reset_scroll(page: Page, config: RuntimeConfig) -> None:
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(config.post_scroll_settle_ms)


def preload_lazy_content(page: Page, config: RuntimeConfig) -> None:
    """Scroll through the page so lazy images load before a full-page capture."""
    page.evaluate(
        """
        async () => {
          const step = Math.max(200, window.innerHeight - 100);
          for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
            window.scrollTo(0, y);
            await new Promise((resolve) => setTimeout(resolve, 150));
          }
        }
        """
    )
    wait_for_visual_stability(page, config)


def clear_existing_outputs(base_name: str, output_dir: Path) -> None:
    pattern = re.compile(rf"{re.escape(base_name)}-(?:panel-\d+-)?(\d{{2}}|full)\.png")
    for path in output_dir.glob(f"{base_name}-*.png"):
        if pattern.fullmatch(path.name):
            path.unlink()


def capture_scrolled_sequence(
    page: Page, output_dir: Path, base_name: str, config: RuntimeConfig, scale: str
) -> None:
    previous_scroll_y = -1
    for index in range(1, config.max_screenshots_per_page + 1):
        output_path = output_dir / f"{base_name}-{index:02d}.png"
        page.screenshot(path=str(output_path), full_page=False, scale=scale)
        metrics = page.evaluate(
            """
            () => ({
              scrollY: Math.round(window.scrollY),
              viewportHeight: Math.round(window.innerHeight),
              scrollHeight: Math.round(document.documentElement.scrollHeight),
            })
            """
        )
        scroll_y = metrics["scrollY"]
        viewport_height = metrics["viewportHeight"]
        max_scroll_y = max(0, metrics["scrollHeight"] - viewport_height)
        if scroll_y >= max_scroll_y:
            return

        scroll_step = max(1, viewport_height - config.scroll_overlap_px)
        next_scroll_y = min(max_scroll_y, scroll_y + scroll_step)
        if next_scroll_y <= scroll_y or next_scroll_y == previous_scroll_y:
            return

        previous_scroll_y = scroll_y
        page.evaluate("(nextY) => window.scrollTo(0, nextY)", next_scroll_y)
        wait_for_visual_stability(page, config)

    raise RuntimeError(f"Exceeded screenshot guard for {base_name}.")


def wait_for_visual_ready(page: Page, config: RuntimeConfig) -> None:
    page.get_by_role("status", name="Loading", exact=True).first.wait_for(
        state="hidden"
    )
    wait_for_visual_stability(page, config)


def capture_view(
    page: Page, alias: str, size: str, theme: str, config: RuntimeConfig, full: bool
) -> None:
    output_dir = config.output_dir / alias
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{size}-{theme}"
    clear_existing_outputs(base_name, output_dir)
    reset_scroll(page, config)
    logger.info("Capturing %s [%s, %s]", alias, size, theme)
    logger.debug(
        "Document metrics: %s",
        page.evaluate("""() => ({
            viewport: [innerWidth, innerHeight],
            document: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
            theme: localStorage.getItem('theme'),
            unloadedImages: [...document.images].filter(image => !image.naturalWidth).length,
        })"""),
    )
    if alias == "command-palette":
        page.screenshot(path=str(output_dir / f"{base_name}-01.png"))
    elif full:
        preload_lazy_content(page, config)
        reset_scroll(page, config)
        page.screenshot(path=str(output_dir / f"{base_name}-full.png"), full_page=True)
    else:
        capture_scrolled_sequence(page, output_dir, base_name, config, "device")
        # Transcript and chat viewports scroll independently of the document.
        panels = page.locator(".overflow-y-auto")
        for index, panel in enumerate(panels.all(), 1):
            if not panel.is_visible() or not panel.evaluate(
                "el => el.scrollHeight > el.clientHeight + 1"
            ):
                continue
            panel.evaluate("(el) => { el.scrollTop = 0; }")
            panel.scroll_into_view_if_needed()
            panel_name = f"{base_name}-panel-{index}"
            clear_existing_outputs(panel_name, output_dir)
            for part in range(1, config.max_screenshots_per_page + 1):
                page.wait_for_timeout(config.post_scroll_settle_ms)
                page.screenshot(path=str(output_dir / f"{panel_name}-{part:02d}.png"))
                done = panel.evaluate(
                    """(el, overlap) => {
                    const before = el.scrollTop;
                    el.scrollTop += Math.max(1, el.clientHeight - overlap);
                    return el.scrollTop === before;
                }""",
                    config.scroll_overlap_px,
                )
                if done:
                    break
            else:
                raise RuntimeError(f"Exceeded panel screenshot guard for {alias}.")
            panel.evaluate("(el) => { el.scrollTop = 0; }")


def run_capture(
    browser: Browser,
    alias: str,
    sizes: list[str],
    themes: list[str],
    token: str | None,
    config: RuntimeConfig,
    full: bool,
) -> None:
    capture = PAGE_CAPTURES[alias]
    # Answer once, then resume the saved conversation for every other variant.
    conversation_path = None
    for size in sizes:
        preset = VIEWPORT_PRESETS[size]
        for theme in themes:
            context = browser.new_context(
                viewport={"width": preset.width, "height": preset.height},
                device_scale_factor=preset.scale,
                reduced_motion="reduce",
                color_scheme=theme,
            )
            context.set_default_timeout(config.navigation_timeout_ms)
            context.set_default_navigation_timeout(config.navigation_timeout_ms)
            context.add_init_script(
                build_init_script(token if capture.authenticated else None, theme)
            )
            page = context.new_page()
            posts = []
            failures = []
            pending = set()

            def api_request(request: Request) -> None:
                if request.url.startswith(config.api_base_url + "/"):
                    pending.add(request)
                    logger.debug(
                        "API %s %s", request.method, urlparse(request.url).path
                    )

            def finished(request: Request) -> None:
                pending.discard(request)

            def request_failed(request: Request) -> None:
                pending.discard(request)
                if request.url.startswith(config.api_base_url + "/"):
                    # The chat transport aborts its Fetch stream after the final event.
                    # Answer readiness and API responses determine success.
                    logger.debug(
                        "Request ended: %s (%s)",
                        urlparse(request.url).path,
                        request.failure,
                    )

            def response_received(response) -> None:
                if (
                    response.url.startswith(config.api_base_url + "/")
                    and response.status >= 400
                ):
                    failures.append(f"{response.status} {urlparse(response.url).path}")

            def guard_message(route: Route) -> None:
                request = route.request
                if request.method == "POST" and re.search(
                    r"/conversations/[^/]+/messages$", urlparse(request.url).path
                ):
                    posts.append(request.url)
                    if alias != "ask-answer" or conversation_path or len(posts) > 1:
                        failures.append("Blocked an unexpected Ask message")
                        route.abort()
                        return
                route.continue_()

            page.on("request", api_request)
            page.on("requestfinished", finished)
            page.on("requestfailed", request_failed)
            page.on("response", response_received)
            page.on("pageerror", lambda error: logger.debug("Browser error: %s", error))
            page.route("**/conversations/*/messages", guard_message)
            try:
                path = conversation_path or capture.path.format(
                    video_id=config.video_id,
                    search_query=quote(config.search_query, safe=""),
                )
                response = page.goto(
                    config.ui_base_url + path, wait_until="domcontentloaded"
                )
                if response and response.status >= 400:
                    raise RuntimeError(f"Navigation returned HTTP {response.status}.")
                page.locator(capture.ready).first.wait_for(state="visible")
                deadline = time.monotonic() + config.navigation_timeout_ms / 1000
                while pending and time.monotonic() < deadline:
                    page.wait_for_timeout(100)
                if pending:
                    raise RuntimeError(f"API requests did not finish for {alias}.")
                if urlparse(page.url).path != urlparse(path).path:
                    raise RuntimeError(f"{alias} redirected to an unexpected route.")
                wait_for_visual_ready(page, config)
                if alias == "search":
                    page.locator('main li a[href^="/v/"]').first.wait_for()
                if alias.startswith("video-"):
                    page.locator('iframe[src*="youtube.com/embed/"]').wait_for()
                    page.wait_for_timeout(1_000)
                if alias == "command-palette":
                    page.keyboard.press("Control+k")
                    page.get_by_role("dialog", name="Command palette").wait_for()
                if alias == "ask-answer":
                    if not conversation_path:
                        prompt = os.environ.get(
                            "VIDWIZ_AUTOMATION_ASK_PROMPT",
                            "What practical advice do my saved videos give about learning a new skill? Give a concise answer with citations.",
                        )
                        page.get_by_label("Message Wiz").fill(prompt)
                        page.get_by_role(
                            "button", name="Send message", exact=True
                        ).click()
                    page.get_by_role("button", name="Copy answer", exact=True).wait_for(
                        timeout=180_000
                    )
                    page.get_by_role("status").filter(
                        has_text=re.compile("Answering|Thinking")
                    ).first.wait_for(state="hidden", timeout=180_000)
                    page.locator(".wiz-watch").first.wait_for(timeout=180_000)
                    if page.get_by_role("alert").count():
                        raise RuntimeError(
                            "Ask returned an error instead of a cited answer."
                        )
                    if not conversation_path:
                        if len(posts) != 1 or "c=" not in page.url:
                            raise RuntimeError(
                                "Expected exactly one saved Ask question."
                            )
                        conversation_path = page.url.removeprefix(config.ui_base_url)
                        logger.info(
                            "Reusing answered conversation: %s", conversation_path
                        )
                    wait_for_visual_stability(page, config)
                if failures:
                    raise RuntimeError("; ".join(failures))
                capture_view(page, alias, size, theme, config, full)
            except (RuntimeError, PlaywrightError):
                config.output_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(config.output_dir / f"error-{alias}-{size}-{theme}.png")
                )
                raise
            finally:
                context.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--pages", nargs="+", choices=PAGE_CAPTURES)
    selection.add_argument(
        "--all", action="store_true", help="Exclude opt-in Ask states."
    )
    parser.add_argument("--sizes", nargs="+", choices=VIEWPORT_PRESETS)
    parser.add_argument(
        "--themes", nargs="+", choices=("dark", "light"), default=["dark"]
    )
    parser.add_argument("--mode", choices=("slices", "full"), default="slices")
    parser.add_argument(
        "--browser-mode", choices=("headless", "headful"), default="headless"
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    if args.list:
        for alias, capture in PAGE_CAPTURES.items():
            print(f"{alias}: {capture.path}" + (" (opt-in)" if capture.opt_in else ""))
        for alias, size in VIEWPORT_PRESETS.items():
            print(f"{alias}: {size.width}x{size.height} @{size.scale}x")
        return 0
    if not args.sizes or not (args.all or args.pages):
        parser.error("Choose --all or --pages, and --sizes. Use --list for options.")
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    aliases = (
        [alias for alias, capture in PAGE_CAPTURES.items() if not capture.opt_in]
        if args.all
        else list(dict.fromkeys(args.pages))
    )
    try:
        config = build_runtime_config()
        if any("{video_id}" in PAGE_CAPTURES[alias].path for alias in aliases):
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", config.video_id):
                raise ValueError(
                    "Set VIDWIZ_AUTOMATION_VIDEO_ID to a video with moments, a ready transcript, and an overview."
                )
        if "search" in aliases and len(config.search_query) < 2:
            raise ValueError(
                "Set VIDWIZ_AUTOMATION_SEARCH_QUERY to a word in the test library (at least two characters)."
            )
        if not config.navigation_timeout_ms or not config.max_screenshots_per_page:
            raise ValueError(
                "Navigation timeout and maximum screenshots must be positive."
            )
        token = (
            login(config)
            if any(PAGE_CAPTURES[alias].authenticated for alias in aliases)
            else None
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=args.browser_mode == "headless"
            )
            try:
                for alias in aliases:
                    run_capture(
                        browser,
                        alias,
                        list(dict.fromkeys(args.sizes)),
                        list(dict.fromkeys(args.themes)),
                        token,
                        config,
                        args.mode == "full",
                    )
            finally:
                browser.close()
    except (ValueError, RuntimeError, urllib.error.URLError, PlaywrightError) as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
