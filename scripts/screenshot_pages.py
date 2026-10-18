# /// script
# requires-python = ">=3.13"
# dependencies = ["playwright==1.61.0", "python-dotenv>=1.1.1,<2.0.0"]
# ///
"""Capture deterministic VidWiz UI screenshots with Playwright.

Examples (run from the repository root):
  uv run scripts/screenshot_pages.py --list
  uv run scripts/screenshot_pages.py --pages landing dashboard --sizes mobile desktop
  uv run scripts/screenshot_pages.py --all --sizes mobile desktop --browser-mode headless
  uv run scripts/screenshot_pages.py --all --sizes desktop tablet mobile --themes dark light --mode full
  uv run scripts/screenshot_pages.py --pages wiz-chat --sizes desktop tablet mobile --themes dark light
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, Response
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = Path(__file__).resolve().parent / ".env"

DEFAULT_UI_BASE_URL = "http://localhost:5173"
DEFAULT_API_BASE_URL = "http://localhost:5000/v2"
DEFAULT_OUTPUT_DIR = "scripts/outputs/ui-images"

load_dotenv(ENV_FILE, override=False)


@dataclass(frozen=True)
class ViewportPreset:
    alias: str
    width: int
    height: int
    scale: int = 1


@dataclass(frozen=True)
class PageCapture:
    alias: str
    screen: str
    path: str
    ready_text: str
    authenticated: bool = False
    dynamic_video: bool = False
    wiz_workspace: bool = False
    state: str | None = None
    action: Callable[[Page], None] | None = None
    sends_message: bool = False


@dataclass(frozen=True)
class RuntimeConfig:
    ui_base_url: str
    api_base_url: str
    output_dir: Path
    email: str | None
    password: str | None
    video_id: str | None
    navigation_timeout_ms: int
    scroll_overlap_px: int
    post_scroll_settle_ms: int
    max_screenshots_per_page: int


@dataclass(frozen=True)
class CliOptions:
    pages: list[PageCapture]
    sizes: list[ViewportPreset]
    themes: list[str]
    full_page: bool
    headless: bool


VIEWPORT_PRESETS = {
    "desktop": ViewportPreset("desktop", 1920, 1080),
    "tablet": ViewportPreset("tablet", 768, 1024, scale=2),
    "mobile": ViewportPreset("mobile", 390, 844, scale=2),
}

THEMES = ("dark", "light")

# Output folders follow this order so a reviewer can walk the product in sequence.
SCREEN_ORDER = (
    "landing",
    "login",
    "signup",
    "help",
    "privacy",
    "wiz",
    "dashboard",
    "video",
    "wiz-workspace",
    "profile",
)

WIZ_FALLBACK_PROMPT = "What is the main idea of this video, and what practical advice does it give?"
WIZ_ANSWER_TIMEOUT_MS = 180_000


def open_sort_menu(page: Page) -> None:
    page.get_by_role("button", name=re.compile(r"^Sort videos")).click()
    page.get_by_role("menu", name="Sort videos").wait_for(state="visible")


def open_user_menu(page: Page) -> None:
    page.get_by_role("button", name="User menu").click()
    page.locator("#user-menu").wait_for(state="visible")
    page.get_by_label("Loading credit balance").wait_for(state="hidden")


def fill_signup_mismatch(page: Page) -> None:
    page.get_by_placeholder("Enter your email").fill("designer@example.com")
    page.get_by_placeholder("Enter your name").fill("Alex Designer")
    page.get_by_placeholder("Create a password").fill("password123")
    page.get_by_placeholder("Repeat password").fill("password321")
    page.evaluate("() => document.activeElement?.blur()")


def edit_first_note(page: Page) -> None:
    page.get_by_title("Edit").first.click()
    page.locator("textarea").first.wait_for(state="visible")


PAGE_CAPTURES = {
    "landing": PageCapture("landing", "landing", "/", "Talk to the video."),
    "login": PageCapture("login", "login", "/login", "Welcome back"),
    "signup": PageCapture("signup", "signup", "/signup", "Create your account"),
    "signup-validation": PageCapture(
        "signup-validation",
        "signup",
        "/signup",
        "Create your account",
        state="validation",
        action=fill_signup_mismatch,
    ),
    "wiz": PageCapture("wiz", "wiz", "/wiz", "Meet Wiz"),
    "privacy": PageCapture("privacy", "privacy", "/privacy", "Your Privacy Matters"),
    "help": PageCapture("help", "help", "/help", "Set Up VidWiz"),
    "dashboard": PageCapture(
        "dashboard", "dashboard", "/dashboard", "Your library", authenticated=True
    ),
    "dashboard-sort-menu": PageCapture(
        "dashboard-sort-menu",
        "dashboard",
        "/dashboard",
        "Your library",
        authenticated=True,
        state="sort-menu",
        action=open_sort_menu,
    ),
    "dashboard-user-menu": PageCapture(
        "dashboard-user-menu",
        "dashboard",
        "/dashboard",
        "Your library",
        authenticated=True,
        state="user-menu",
        action=open_user_menu,
    ),
    "dashboard-search": PageCapture(
        "dashboard-search",
        "dashboard",
        "/dashboard?q=focus",
        "Your library",
        authenticated=True,
        state="search",
    ),
    "profile": PageCapture(
        "profile", "profile", "/profile", "User Details", authenticated=True
    ),
    "video": PageCapture(
        "video",
        "video",
        "/dashboard/{video_id}",
        "Your Notes",
        authenticated=True,
        dynamic_video=True,
    ),
    "video-note-edit": PageCapture(
        "video-note-edit",
        "video",
        "/dashboard/{video_id}",
        "Your Notes",
        authenticated=True,
        dynamic_video=True,
        state="note-edit",
        action=edit_first_note,
    ),
    "wiz-workspace": PageCapture(
        "wiz-workspace",
        "wiz-workspace",
        "/wiz/{video_id}",
        "Ready to chat!",
        authenticated=True,
        dynamic_video=True,
        wiz_workspace=True,
    ),
    # Sends one real Wiz message, so --all leaves it out.
    "wiz-chat": PageCapture(
        "wiz-chat",
        "wiz-workspace",
        "/wiz/{video_id}",
        "Ready to chat!",
        authenticated=True,
        dynamic_video=True,
        wiz_workspace=True,
        state="chat",
        sends_message=True,
    ),
}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        result = int(value)
    except ValueError as error:
        raise RuntimeError(f"Invalid integer value for {name}: {value!r}") from error
    if result < 0:
        raise RuntimeError(f"{name} must not be negative.")
    return result


def build_runtime_config() -> RuntimeConfig:
    output_value = os.environ.get(
        "VIDWIZ_UI_IMAGE_OUTPUT_DIR", DEFAULT_OUTPUT_DIR
    ).strip()
    output_dir = Path(output_value)
    if not output_dir.is_absolute():
        output_dir = ROOT_DIR / output_dir

    return RuntimeConfig(
        ui_base_url=os.environ.get("VIDWIZ_UI_BASE_URL", DEFAULT_UI_BASE_URL).rstrip(
            "/"
        ),
        api_base_url=os.environ.get("VIDWIZ_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip(
            "/"
        ),
        output_dir=output_dir,
        email=clean_optional_env("VIDWIZ_AUTOMATION_EMAIL"),
        password=clean_optional_env("VIDWIZ_AUTOMATION_PASSWORD"),
        video_id=clean_optional_env("VIDWIZ_AUTOMATION_VIDEO_ID"),
        navigation_timeout_ms=env_int(
            "VIDWIZ_AUTOMATION_NAVIGATION_TIMEOUT_MS", 30_000
        ),
        scroll_overlap_px=env_int("VIDWIZ_AUTOMATION_SCROLL_OVERLAP_PX", 140),
        post_scroll_settle_ms=env_int("VIDWIZ_AUTOMATION_POST_SCROLL_SETTLE_MS", 400),
        max_screenshots_per_page=env_int(
            "VIDWIZ_AUTOMATION_MAX_SCREENSHOTS_PER_PAGE", 20
        ),
    )


def clean_optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture VidWiz pages as overlapping desktop or mobile screenshots."
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--pages", nargs="+", metavar="PAGE", help="Page aliases to capture."
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="Capture every page alias except wiz-chat, which sends a message.",
    )
    parser.add_argument(
        "--sizes", nargs="+", metavar="SIZE", help="Viewport aliases to capture."
    )
    parser.add_argument(
        "--themes",
        nargs="+",
        choices=THEMES,
        default=["dark"],
        help="Color themes to capture (default: dark).",
    )
    parser.add_argument(
        "--mode",
        choices=("slices", "full"),
        default="slices",
        help="Overlapping viewport slices or one full-page image (default: slices).",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available pages and sizes."
    )
    parser.add_argument(
        "--browser-mode",
        choices=("headless", "headful"),
        default="headless",
        help="Run Chromium hidden or visible (default: headless).",
    )
    return parser


def resolve_options(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> CliOptions:
    if not args.all and not args.pages:
        parser.error("one of --pages or --all is required unless --list is used.")
    if not args.sizes:
        parser.error("--sizes is required unless --list is used.")

    page_aliases = (
        [alias for alias, page in PAGE_CAPTURES.items() if not page.sends_message]
        if args.all
        else list(args.pages)
    )
    size_aliases = list(args.sizes)
    unknown_pages = sorted(set(page_aliases) - PAGE_CAPTURES.keys())
    unknown_sizes = sorted(set(size_aliases) - VIEWPORT_PRESETS.keys())
    if unknown_pages:
        parser.error(
            f"unknown page alias(es): {', '.join(unknown_pages)}. Use --list for options."
        )
    if unknown_sizes:
        parser.error(
            f"unknown size alias(es): {', '.join(unknown_sizes)}. Use --list for options."
        )

    return CliOptions(
        pages=[PAGE_CAPTURES[alias] for alias in page_aliases],
        sizes=[VIEWPORT_PRESETS[alias] for alias in size_aliases],
        themes=list(dict.fromkeys(args.themes)),
        full_page=args.mode == "full",
        headless=args.browser_mode == "headless",
    )


def validate_config(config: RuntimeConfig, pages: Sequence[PageCapture]) -> None:
    if any(page.authenticated for page in pages):
        missing = []
        if not config.email:
            missing.append("VIDWIZ_AUTOMATION_EMAIL")
        if not config.password:
            missing.append("VIDWIZ_AUTOMATION_PASSWORD")
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

    if any(page.dynamic_video for page in pages) and not config.video_id:
        raise RuntimeError(
            "Missing required environment variable: VIDWIZ_AUTOMATION_VIDEO_ID"
        )
    if config.max_screenshots_per_page < 1:
        raise RuntimeError(
            "VIDWIZ_AUTOMATION_MAX_SCREENSHOTS_PER_PAGE must be at least 1."
        )


def print_available_options() -> None:
    print("Available pages:")
    for capture in PAGE_CAPTURES.values():
        path = capture.path.replace("{video_id}", "{VIDWIZ_AUTOMATION_VIDEO_ID}")
        labels = []
        if capture.authenticated:
            labels.append("authenticated")
        if capture.dynamic_video:
            labels.append("configured video")
        if capture.sends_message:
            labels.append("sends one Wiz message")
        suffix = f" ({', '.join(labels)})" if labels else ""
        print(f"  - {capture.alias}: {path}{suffix}")

    print("\nAvailable sizes:")
    for preset in VIEWPORT_PRESETS.values():
        print(f"  - {preset.alias}: {preset.width}x{preset.height} @{preset.scale}x")
    print("\nAvailable themes:")
    for theme in THEMES:
        print(f"  - {theme}")
    print("\nAvailable browser modes:\n  - headless\n  - headful")


def request_json(
    url: str, payload: dict[str, str], timeout_seconds: float
) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Automation login failed with HTTP {error.code}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not reach the VidWiz API at {url}: {error.reason}"
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Automation login returned invalid JSON.") from error


def login(config: RuntimeConfig) -> str:
    if not config.email or not config.password:
        raise RuntimeError(
            "Automation credentials are required for authenticated captures."
        )
    result = request_json(
        f"{config.api_base_url}/auth/login",
        {"email": config.email, "password": config.password},
        config.navigation_timeout_ms / 1000,
    )
    token = result.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Automation login response did not contain a token.")
    return token


def build_context(
    browser: Browser,
    preset: ViewportPreset,
    theme: str,
    token: str | None,
    config: RuntimeConfig,
) -> BrowserContext:
    context = browser.new_context(
        viewport={"width": preset.width, "height": preset.height},
        device_scale_factor=preset.scale,
        reduced_motion="reduce",
        color_scheme=theme,
    )
    context.set_default_timeout(config.navigation_timeout_ms)
    context.set_default_navigation_timeout(config.navigation_timeout_ms)
    context.add_init_script(build_init_script(token, theme))
    return context


def build_init_script(token: str | None, theme: str) -> str:
    token_json = json.dumps(token)
    theme_json = json.dumps(theme)
    return f"""
    (() => {{
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


def screen_dir(capture: PageCapture, config: RuntimeConfig) -> Path:
    index = SCREEN_ORDER.index(capture.screen) + 1
    path = config.output_dir / f"{index:02d}-{capture.screen}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_base_name(capture: PageCapture, preset: ViewportPreset, theme: str) -> str:
    suffix = f"-{capture.state}" if capture.state else ""
    return f"{preset.alias}-{theme}{suffix}"


def capture_for_size(
    browser: Browser,
    preset: ViewportPreset,
    theme: str,
    pages: Sequence[PageCapture],
    token: str | None,
    config: RuntimeConfig,
    full_page: bool,
) -> None:
    anonymous_pages = [capture for capture in pages if not capture.authenticated]
    authenticated_pages = [capture for capture in pages if capture.authenticated]

    for captures, context_token in (
        (anonymous_pages, None),
        (authenticated_pages, token),
    ):
        if not captures:
            continue
        context = build_context(browser, preset, theme, context_token, config)
        try:
            page = context.new_page()
            for capture in captures:
                capture_page(page, capture, preset, theme, config, full_page)
        finally:
            context.close()


def capture_page(
    page: Page,
    capture: PageCapture,
    preset: ViewportPreset,
    theme: str,
    config: RuntimeConfig,
    full_page: bool,
) -> None:
    path = capture.path.format(video_id=config.video_id)
    url = f"{config.ui_base_url}{path}"
    output_dir = screen_dir(capture, config)
    base_name = output_base_name(capture, preset, theme)
    requests: list[tuple[str, str]] = []
    responses: list[tuple[str, str, int]] = []

    def record_request(request) -> None:
        requests.append((request.method, request.url))

    def record_response(response: Response) -> None:
        responses.append((response.request.method, response.url, response.status))

    page.on("request", record_request)
    page.on("response", record_response)
    try:
        print(f"Capturing {url} [{preset.alias}, {theme}] -> {output_dir.name}/{base_name}")
        response = page.goto(url, wait_until="domcontentloaded")
        if response and response.status >= 400:
            raise RuntimeError(f"Navigation to {url} returned HTTP {response.status}.")

        wait_for_ready_state(page, capture, responses, config)
        assert_expected_route(page, capture, urlparse(path).path)
        wait_for_visual_stability(page, config)
        if full_page:
            preload_lazy_content(page, config)
        reset_scroll(page, config)
        if capture.action:
            capture.action(page)
            wait_for_visual_stability(page, config)
        capture_current_view(page, output_dir, base_name, config, full_page)

        if count_message_posts(requests):
            raise RuntimeError(
                "The screenshot workflow unexpectedly submitted a Wiz message."
            )
    finally:
        page.remove_listener("request", record_request)
        page.remove_listener("response", record_response)


def count_message_posts(requests: Sequence[tuple[str, str]]) -> int:
    return sum(
        1
        for method, request_url in requests
        if method == "POST"
        and "/conversations/" in request_url
        and request_url.endswith("/messages")
    )


def capture_current_view(
    page: Page,
    output_dir: Path,
    base_name: str,
    config: RuntimeConfig,
    full_page: bool,
    scale: str = "device",
) -> None:
    clear_existing_outputs(base_name, output_dir)
    if full_page:
        page.screenshot(
            path=str(output_dir / f"{base_name}-full.png"), full_page=True, scale=scale
        )
    else:
        capture_scrolled_sequence(page, output_dir, base_name, config, scale)


def capture_wiz_chat(
    browser: Browser,
    capture: PageCapture,
    sizes: Sequence[ViewportPreset],
    themes: Sequence[str],
    token: str | None,
    config: RuntimeConfig,
    full_page: bool,
) -> None:
    """Send one Wiz message, then capture the answer at every size and theme.

    Each Wiz visit starts a new conversation, so the workflow resizes and
    re-themes the same page instead of reloading it.
    """
    path = capture.path.format(video_id=config.video_id)
    url = f"{config.ui_base_url}{path}"
    output_dir = screen_dir(capture, config)
    context_scale = max(preset.scale for preset in sizes)
    first = sizes[0]
    context = build_context(
        browser,
        ViewportPreset(first.alias, first.width, first.height, context_scale),
        themes[0],
        token,
        config,
    )
    requests: list[tuple[str, str]] = []
    responses: list[tuple[str, str, int]] = []
    try:
        page = context.new_page()
        page.on("request", lambda request: requests.append((request.method, request.url)))
        page.on(
            "response",
            lambda response: responses.append(
                (response.request.method, response.url, response.status)
            ),
        )
        print(f"Opening {url} to send one Wiz message")
        page.goto(url, wait_until="domcontentloaded")
        wait_for_ready_state(page, capture, responses, config)
        assert_expected_route(page, capture, path)
        wait_for_visual_stability(page, config)

        send_wiz_prompt(page)
        status = page.get_by_role("status").filter(has_text=re.compile("Answering"))
        try:
            status.first.wait_for(state="visible", timeout=WIZ_ANSWER_TIMEOUT_MS)
            page.wait_for_timeout(1_500)
            streaming_name = f"{first.alias}-{themes[0]}-chat-streaming"
            clear_existing_outputs(streaming_name, output_dir)
            page.screenshot(
                path=str(output_dir / f"{streaming_name}-01.png"),
                scale=screenshot_scale(first, context_scale),
            )
        except PlaywrightTimeoutError:
            print("Wiz answered before a streaming frame could be captured.")

        page.get_by_role("button", name=re.compile("Copy answer")).first.wait_for(
            state="visible", timeout=WIZ_ANSWER_TIMEOUT_MS
        )
        page.get_by_role("status").filter(
            has_text=re.compile("Answering|Thinking")
        ).first.wait_for(state="hidden", timeout=WIZ_ANSWER_TIMEOUT_MS)
        if page.get_by_role("alert").count():
            raise RuntimeError("Wiz returned an error instead of an answer.")
        if count_message_posts(requests) != 1:
            raise RuntimeError("The Wiz chat capture must send exactly one message.")

        for preset in sizes:
            page.set_viewport_size({"width": preset.width, "height": preset.height})
            for theme in themes:
                apply_theme(page, theme)
                wait_for_visual_stability(page, config)
                reset_scroll(page, config)
                base_name = output_base_name(capture, preset, theme)
                print(f"Capturing Wiz chat [{preset.alias}, {theme}] -> {output_dir.name}/{base_name}")
                capture_current_view(
                    page,
                    output_dir,
                    base_name,
                    config,
                    full_page,
                    screenshot_scale(preset, context_scale),
                )
    finally:
        context.close()


def send_wiz_prompt(page: Page) -> None:
    starter = page.locator("h3:has-text('Ready to chat!') ~ div button")
    if starter.count():
        print(f"Sending starter question: {starter.first.inner_text()}")
        starter.first.click()
    else:
        print(f"Sending prompt: {WIZ_FALLBACK_PROMPT}")
        page.get_by_label("Message Wiz").fill(WIZ_FALLBACK_PROMPT)
    page.get_by_role("button", name="Send message").click()


def apply_theme(page: Page, theme: str) -> None:
    is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    if is_dark != (theme == "dark"):
        page.get_by_role("button", name="Toggle theme").click()


def screenshot_scale(preset: ViewportPreset, context_scale: int) -> str:
    return "device" if preset.scale == context_scale else "css"


def wait_for_ready_state(
    page: Page,
    capture: PageCapture,
    responses: list[tuple[str, str, int]],
    config: RuntimeConfig,
) -> None:
    try:
        page.get_by_text(capture.ready_text, exact=False).first.wait_for(
            state="visible"
        )
        if capture.wiz_workspace:
            page.get_by_placeholder("Ask about this video...").wait_for(state="visible")
            wait_for_conversation_creation(
                page, responses, config.navigation_timeout_ms
            )
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            f"Timed out waiting for {capture.alias!r} to become ready at {page.url}."
        ) from error


def wait_for_conversation_creation(
    page: Page,
    responses: list[tuple[str, str, int]],
    timeout_ms: int,
) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        conversation_responses = [
            status
            for method, url, status in responses
            if method == "POST"
            and urlparse(url).path.rstrip("/").endswith("/v2/conversations")
        ]
        if conversation_responses:
            status = conversation_responses[-1]
            if 200 <= status < 300:
                return
            raise RuntimeError(f"Wiz conversation creation failed with HTTP {status}.")
        page.wait_for_timeout(100)
    raise RuntimeError("Timed out waiting for the Wiz conversation to be created.")


def assert_expected_route(page: Page, capture: PageCapture, expected_path: str) -> None:
    actual_path = urlparse(page.url).path.rstrip("/") or "/"
    normalized_expected = expected_path.rstrip("/") or "/"
    if capture.authenticated and actual_path == "/login":
        raise RuntimeError(f"Navigation to {normalized_expected} redirected to login.")
    if actual_path != normalized_expected:
        raise RuntimeError(
            f"Navigation to {normalized_expected} ended at unexpected route {actual_path}."
        )


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
    pattern = re.compile(rf"{re.escape(base_name)}-(\d{{2}}|full)\.png")
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
        page.wait_for_timeout(config.post_scroll_settle_ms)

    raise RuntimeError(f"Exceeded screenshot guard for {base_name}.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list:
        print_available_options()
        return 0

    try:
        options = resolve_options(parser, args)
        config = build_runtime_config()
        validate_config(config, options.pages)
        config.output_dir.mkdir(parents=True, exist_ok=True)
        token = (
            login(config) if any(page.authenticated for page in options.pages) else None
        )
        static_pages = [page for page in options.pages if not page.sends_message]
        chat_pages = [page for page in options.pages if page.sends_message]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=options.headless)
            try:
                for preset in options.sizes:
                    for theme in options.themes:
                        capture_for_size(
                            browser,
                            preset,
                            theme,
                            static_pages,
                            token,
                            config,
                            options.full_page,
                        )
                for capture in chat_pages:
                    capture_wiz_chat(
                        browser,
                        capture,
                        options.sizes,
                        options.themes,
                        token,
                        config,
                        options.full_page,
                    )
            finally:
                browser.close()
    except (RuntimeError, PlaywrightError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
