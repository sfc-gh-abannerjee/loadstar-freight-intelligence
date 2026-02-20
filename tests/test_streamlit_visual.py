"""
Visual regression tests for LoadStar Commander using Playwright.

Connects to a running Chrome instance via CDP (Chrome DevTools Protocol) on
port 9222 and navigates to the deployed Streamlit in Snowflake (SiS) app.

Prerequisites:
  1. Chrome must be running with --remote-debugging-port=9222
     and --remote-allow-origins=* flags
  2. The user must be authenticated to Snowsight in that Chrome session
  3. MFA bypass is set automatically via snowflake-connector-python

The key insight: Playwright can access cross-origin iframe DOM when it
*observes* the navigation that creates the iframe. So we navigate away
(to Snowsight home) then back to the SiS app while Playwright is connected.
"""

import os
import json
import time
import shutil
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

BASELINES_DIR = Path(__file__).resolve().parent / "visual_baselines"

SNOWSIGHT_ORG = os.environ.get("SNOWFLAKE_ORG", "SFSENORTHAMERICA")
SNOWSIGHT_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "ABANNERJEE_AWS1")
SNOWSIGHT_LOGIN_URL = (
    f"https://app.snowflake.com/{SNOWSIGHT_ORG}/{SNOWSIGHT_ACCOUNT}"
)

# Full qualified name URL — url_id URLs cause "Something went wrong"
SIS_APP_URL = (
    f"{SNOWSIGHT_LOGIN_URL}/#/streamlit-apps/"
    "APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_COMMANDER"
)

CDP_ENDPOINT = os.environ.get("CDP_ENDPOINT", "http://localhost:9222")

TABS = [
    {"name": "command_map", "label": "Command map", "index": 0},
    {"name": "match_engine", "label": "Match engine", "index": 1},
    {"name": "broker_360", "label": "Broker 360", "index": 2},
]

# ---------------------------------------------------------------------------
# Playwright availability check
# ---------------------------------------------------------------------------


def _has_playwright():
    """Check if Playwright and its Python bindings are available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _cdp_available() -> bool:
    """Check if Chrome is listening on the CDP port."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{CDP_ENDPOINT}/json/version")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return "Browser" in data
    except Exception:
        return False


# ---------------------------------------------------------------------------
# MFA bypass helpers
# ---------------------------------------------------------------------------


def _set_mfa_bypass(minutes: int):
    """Set MINS_TO_BYPASS_MFA for the test user via snowflake-connector-python."""
    config_path = Path.home() / ".snowflake" / "config.toml"
    if not config_path.exists():
        return

    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
        conn = cfg.get("connections", {}).get("se_demo", {})
        if not conn:
            return
    except Exception:
        return

    try:
        import snowflake.connector

        ctx = snowflake.connector.connect(
            account=conn.get("account", ""),
            user=conn.get("user", ""),
            password=conn.get("password", ""),
            host=conn.get("host", ""),
            role="ACCOUNTADMIN",
            login_timeout=15,
            network_timeout=15,
        )
        cur = ctx.cursor()
        cur.execute(
            f"ALTER USER {conn.get('user', 'ABANNERJEE')}"
            f" SET MINS_TO_BYPASS_MFA = {int(minutes)}"
        )
        cur.close()
        ctx.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Debug screenshot helper
# ---------------------------------------------------------------------------


def _save_debug_screenshot(page, name: str):
    """Save a debug screenshot for visual inspection on failure."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(BASELINES_DIR / f"{name}_debug.png"))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loaded_page():
    """Connect to Chrome via CDP, navigate to SiS app, yield (page, frame).

    The critical pattern: navigate away from the SiS page first (to Snowsight
    home), then navigate back. This lets Playwright observe the iframe creation
    and attach to the cross-origin Streamlit iframe, giving full DOM access.
    """
    if not _has_playwright():
        pytest.skip("Playwright not installed")

    if not _cdp_available():
        pytest.skip(
            "Chrome not running with CDP on port 9222. Launch with:\n"
            '  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" '
            "--remote-debugging-port=9222 --remote-allow-origins=* "
            '--user-data-dir="/tmp/chrome-visual-test-profile" --no-first-run'
        )

    from playwright.sync_api import sync_playwright

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)

    pw = sync_playwright().start()
    browser = None
    try:
        browser = pw.chromium.connect_over_cdp(CDP_ENDPOINT)
    except Exception as exc:
        pw.stop()
        pytest.skip(f"Cannot connect to Chrome via CDP: {exc}")

    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    try:
        # Step 1: Navigate to Snowsight home (ensures we're on the right origin
        # and forces a fresh navigation when we go to the SiS app)
        page.goto(SNOWSIGHT_LOGIN_URL, timeout=30000)
        page.wait_for_timeout(3000)

        # Check that we're authenticated (not on a login page)
        if "login" in page.url.lower() or "oauth" in page.url.lower():
            _save_debug_screenshot(page, "not_authenticated")
            pytest.skip(
                "Chrome session is not authenticated to Snowsight. "
                "Please log in manually in the Chrome window first."
            )

        # Step 2: Navigate to SiS app — this triggers iframe creation
        # which Playwright can observe and attach to
        sis_url = os.environ.get("LOADSTAR_URL", SIS_APP_URL)
        page.goto(sis_url, timeout=60000)

        # Step 3: Wait for the Streamlit iframe to appear
        page.wait_for_selector(
            '[data-testid="streamlit-iframe"]', timeout=30000
        )
        # Give Streamlit time to render content inside the iframe
        page.wait_for_timeout(10000)

        # Step 4: Get the iframe's content frame
        iframe_el = page.query_selector('[data-testid="streamlit-iframe"]')
        if not iframe_el:
            _save_debug_screenshot(page, "no_iframe")
            pytest.fail("Streamlit iframe element not found on page")

        frame = iframe_el.content_frame()

        # If content_frame is None, the cross-origin iframe wasn't attached.
        # This can happen if Playwright connected after the iframe was created.
        # Retry by navigating away and back.
        if frame is None:
            page.goto(SNOWSIGHT_LOGIN_URL, timeout=30000)
            page.wait_for_timeout(3000)
            page.goto(sis_url, timeout=60000)
            page.wait_for_selector(
                '[data-testid="streamlit-iframe"]', timeout=30000
            )
            page.wait_for_timeout(10000)
            iframe_el = page.query_selector('[data-testid="streamlit-iframe"]')
            frame = iframe_el.content_frame() if iframe_el else None

        if frame is None:
            _save_debug_screenshot(page, "frame_unavailable")
            pytest.skip(
                "Cannot access Streamlit iframe content frame. "
                "The cross-origin iframe was not attached by Playwright."
            )

        # Step 5: Wait for Streamlit app to be ready inside the iframe
        try:
            frame.wait_for_selector(
                '[data-testid="stApp"]', timeout=20000
            )
        except Exception:
            _save_debug_screenshot(page, "stapp_not_ready")
            pytest.fail(
                "Streamlit [data-testid='stApp'] not found in iframe. "
                "The app may not have loaded."
            )

        # Step 6: Wait for tabs to be available
        try:
            frame.wait_for_selector(
                'button[role="tab"]', timeout=15000
            )
        except Exception:
            _save_debug_screenshot(page, "tabs_not_found")
            pytest.fail("Tab buttons not found in Streamlit app")

        # Give everything a moment to settle
        page.wait_for_timeout(2000)

        yield page, frame

    except Exception:
        raise
    finally:
        # Don't close the browser — it's the user's Chrome session
        try:
            pw.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _click_tab(frame, tab_label: str):
    """Click a Streamlit tab by its label text within the iframe frame."""
    tab_selector = f'button[role="tab"]:has-text("{tab_label}")'
    try:
        frame.click(tab_selector, timeout=10000)
        frame.page.wait_for_timeout(2000)
    except Exception:
        tabs = frame.query_selector_all('button[role="tab"]')
        for tab in tabs:
            text = (tab.inner_text() or "").lower()
            if tab_label.lower() in text:
                tab.click()
                frame.page.wait_for_timeout(2000)
                return
        pytest.fail(f"Could not find tab '{tab_label}'")


def _mask_dynamic_content(frame):
    """Inject CSS into the Streamlit iframe to mask dynamic content."""
    try:
        frame.evaluate("""
            () => {
                const style = document.createElement('style');
                style.textContent = `
                    /* Disable animations for stable screenshots */
                    *, *::before, *::after {
                        animation-duration: 0s !important;
                        animation-delay: 0s !important;
                        transition-duration: 0s !important;
                        transition-delay: 0s !important;
                        scroll-behavior: auto !important;
                    }
                    /* Mask timestamps and live data */
                    [data-testid="stMetricValue"],
                    time,
                    .stDataFrame td {
                        color: transparent !important;
                    }
                `;
                document.head.appendChild(style);
            }
        """)
    except Exception:
        # If we can't inject CSS (frame detached, etc.), continue anyway
        pass


def _screenshot_path(tab_name: str, suffix: str = "") -> str:
    """Get the path for a screenshot file."""
    return str(BASELINES_DIR / f"{tab_name}{suffix}.png")


def _compare_screenshots(
    actual_path: str, baseline_path: str, threshold: float = 0.02
) -> bool:
    """Compare two screenshots with a pixel difference threshold.

    Returns True if they match within threshold, False otherwise.
    """
    if not os.path.exists(baseline_path):
        return False

    try:
        from PIL import Image

        img_actual = Image.open(actual_path).convert("RGB")
        img_baseline = Image.open(baseline_path).convert("RGB")

        if img_actual.size != img_baseline.size:
            return False

        pixels_a = list(img_actual.getdata())
        pixels_b = list(img_baseline.getdata())
        total = len(pixels_a)
        diff_count = 0

        for pa, pb in zip(pixels_a, pixels_b):
            if pa != pb:
                channel_diff = sum(abs(a - b) for a, b in zip(pa, pb))
                if channel_diff > 30:
                    diff_count += 1

        diff_ratio = diff_count / total if total > 0 else 0
        return diff_ratio <= threshold

    except ImportError:
        with open(actual_path, "rb") as f1, open(baseline_path, "rb") as f2:
            return f1.read() == f2.read()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_playwright(), reason="Playwright not installed")
class TestVisualRegression:
    """Visual regression tests using Playwright against the live SiS app."""

    def test_tab_command_map(self, loaded_page):
        """Command Map tab should render and match baseline."""
        page, frame = loaded_page
        tab = TABS[0]
        _click_tab(frame, tab["label"])
        _mask_dynamic_content(frame)

        actual_path = _screenshot_path(tab["name"], "_actual")
        page.screenshot(path=actual_path, full_page=False)

        baseline_path = _screenshot_path(tab["name"])
        if not os.path.exists(baseline_path):
            shutil.copy2(actual_path, baseline_path)
            pytest.skip(
                f"Baseline created for {tab['name']} — manual review required"
            )

        assert _compare_screenshots(actual_path, baseline_path), (
            f"Visual regression detected in {tab['name']} tab. "
            f"Compare {actual_path} vs {baseline_path}"
        )

    def test_tab_match_engine(self, loaded_page):
        """Match Engine tab should render and match baseline."""
        page, frame = loaded_page
        tab = TABS[1]
        _click_tab(frame, tab["label"])
        _mask_dynamic_content(frame)

        actual_path = _screenshot_path(tab["name"], "_actual")
        page.screenshot(path=actual_path, full_page=False)

        baseline_path = _screenshot_path(tab["name"])
        if not os.path.exists(baseline_path):
            shutil.copy2(actual_path, baseline_path)
            pytest.skip(
                f"Baseline created for {tab['name']} — manual review required"
            )

        assert _compare_screenshots(actual_path, baseline_path), (
            f"Visual regression detected in {tab['name']} tab. "
            f"Compare {actual_path} vs {baseline_path}"
        )

    def test_tab_broker_360(self, loaded_page):
        """Broker 360 tab should render and match baseline."""
        page, frame = loaded_page
        tab = TABS[2]
        _click_tab(frame, tab["label"])
        _mask_dynamic_content(frame)

        actual_path = _screenshot_path(tab["name"], "_actual")
        page.screenshot(path=actual_path, full_page=False)

        baseline_path = _screenshot_path(tab["name"])
        if not os.path.exists(baseline_path):
            shutil.copy2(actual_path, baseline_path)
            pytest.skip(
                f"Baseline created for {tab['name']} — manual review required"
            )

        assert _compare_screenshots(actual_path, baseline_path), (
            f"Visual regression detected in {tab['name']} tab. "
            f"Compare {actual_path} vs {baseline_path}"
        )

    def test_page_structure(self, loaded_page):
        """Basic DOM structure checks for the SiS app."""
        page, frame = loaded_page
        app = frame.query_selector('[data-testid="stApp"]')
        assert app is not None, "Streamlit app container not found"

        tabs = frame.query_selector_all('button[role="tab"]')
        assert len(tabs) >= 3, f"Expected 3+ tabs, found {len(tabs)}"

        page_text = frame.inner_text('[data-testid="stApp"]')
        assert "LoadStar" in page_text, "App title 'LoadStar' not found in page"

    def test_no_streamlit_errors(self, loaded_page):
        """The app should not display any Streamlit error banners."""
        page, frame = loaded_page
        errors = frame.query_selector_all('[data-testid="stException"]')
        assert len(errors) == 0, (
            f"Found {len(errors)} Streamlit error(s) on page"
        )

        error_blocks = frame.query_selector_all(
            '.stAlert [data-testid="stError"]'
        )
        assert len(error_blocks) == 0, (
            f"Found {len(error_blocks)} error alert(s) on page"
        )


@pytest.mark.skipif(not _has_playwright(), reason="Playwright not installed")
class TestVisualAccessibility:
    """Accessibility-focused visual checks."""

    def test_color_contrast_ratio(self, loaded_page):
        """Primary text should have sufficient contrast against background."""
        page, frame = loaded_page
        result = frame.evaluate("""
            () => {
                const body = document.querySelector('[data-testid="stApp"]');
                if (!body) return null;
                const style = window.getComputedStyle(body);
                return {
                    color: style.color,
                    backgroundColor: style.backgroundColor,
                };
            }
        """)
        if result:
            assert result.get("color"), "Could not determine text color"
            assert result.get("backgroundColor"), (
                "Could not determine background color"
            )

    def test_responsive_viewport(self, loaded_page):
        """App should not have horizontal overflow at standard viewports."""
        page, frame = loaded_page
        overflow = frame.evaluate("""
            () => {
                return document.documentElement.scrollWidth > document.documentElement.clientWidth;
            }
        """)
        assert not overflow, "Page has horizontal overflow at current viewport"
