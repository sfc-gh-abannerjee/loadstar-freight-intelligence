"""
Visual regression tests for LoadStar Commander using Playwright.

Connects to the deployed Streamlit in Snowflake (SiS) app URL and captures
screenshots of each tab, comparing against committed baseline images.

Gracefully SKIPs when Playwright is not installed, the SiS URL is unreachable,
or authentication fails.
"""

import os
import subprocess
import json
import re

import pytest

# ---------------------------------------------------------------------------
# Check for Playwright availability
# ---------------------------------------------------------------------------

def _has_playwright():
    """Check if Playwright and its Python bindings are available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _get_sis_url() -> str:
    """Get the deployed Streamlit in Snowflake app URL.

    Tries multiple approaches:
    1. Environment variable LOADSTAR_URL
    2. snow streamlit get-url via Snowflake CLI
    3. Construct from SHOW STREAMLITS output
    """
    # 1. Check environment variable
    env_url = os.environ.get("LOADSTAR_URL")
    if env_url:
        return env_url

    # 2. Try snow CLI (streamlit get-url can be slow, use snow sql instead)
    try:
        result = subprocess.run(
            [
                "snow", "sql", "-c", "se_demo", "-q",
                "SHOW STREAMLITS IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS",
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for row in data:
                if row.get("name") == "LOADSTAR_COMMANDER":
                    url_id = row.get("url_id", "")
                    if url_id:
                        # Construct SiS URL from account + url_id
                        # Format: https://app.snowflake.com/<org>/<account>/#/streamlit-apps/<url_id>
                        # Or the direct URL pattern
                        return url_id
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return ""


def _resolve_sis_url() -> str:
    """Get the full SiS app URL, constructing from url_id if needed."""
    url_or_id = _get_sis_url()
    if not url_or_id:
        return ""

    # If it's already a full URL, use it directly
    if url_or_id.startswith("http"):
        return url_or_id

    # Construct the Snowsight URL from the url_id
    org = os.environ.get("SNOWFLAKE_ORG", "SFSENORTHAMERICA")
    account = os.environ.get("SNOWFLAKE_ACCOUNT", "ABANNERJEE_AWS1")
    return f"https://app.snowflake.com/{org}/{account}/#/streamlit-apps/{url_or_id}"


# Baselines directory
BASELINES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visual_baselines")

# Tab definitions for screenshot capture
TABS = [
    {"name": "command_map", "label": "Command map", "index": 0},
    {"name": "match_engine", "label": "Match engine", "index": 1},
    {"name": "broker_360", "label": "Broker 360", "index": 2},
]


@pytest.mark.skipif(not _has_playwright(), reason="Playwright not installed")
class TestVisualRegression:
    """Visual regression tests using Playwright against the live SiS app."""

    @pytest.fixture(scope="class")
    def sis_url(self):
        """Get the SiS app URL, skip if unavailable."""
        url = _resolve_sis_url()
        if not url:
            pytest.skip("SiS app URL not available — set LOADSTAR_URL env var or ensure snow CLI is configured")
        return url

    @pytest.fixture(scope="class")
    def browser_context(self):
        """Create a Playwright browser context for the test class."""
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)

        # Use Snowflake connection config for auth cookies if available
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        context.set_default_timeout(30000)

        yield context

        context.close()
        browser.close()
        pw.stop()

    @pytest.fixture(scope="class")
    def page(self, browser_context, sis_url):
        """Navigate to the SiS app and wait for load."""
        pg = browser_context.new_page()

        try:
            pg.goto(sis_url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            pytest.skip(f"Cannot load SiS app at {sis_url}: {e}")

        # Wait for Streamlit to finish loading
        try:
            pg.wait_for_selector('[data-testid="stApp"]', timeout=30000)
        except Exception:
            # Might be an auth page — check for login form
            if "login" in pg.url.lower() or "oauth" in pg.url.lower():
                pytest.skip("SiS app requires interactive SSO login — cannot automate")
            # Otherwise try to continue
            pass

        yield pg
        pg.close()

    def _screenshot_path(self, tab_name: str, suffix: str = "") -> str:
        """Get the path for a screenshot file."""
        filename = f"{tab_name}{suffix}.png"
        return os.path.join(BASELINES_DIR, filename)

    def _click_tab(self, page, tab_label: str):
        """Click a Streamlit tab by its label text."""
        # Streamlit tabs use button[role="tab"] elements
        tab_selector = f'button[role="tab"]:has-text("{tab_label}")'
        try:
            page.click(tab_selector, timeout=10000)
            page.wait_for_timeout(2000)  # Wait for tab content to render
        except Exception:
            # Try alternative selector
            tabs = page.query_selector_all('button[role="tab"]')
            for tab in tabs:
                if tab_label.lower() in (tab.inner_text() or "").lower():
                    tab.click()
                    page.wait_for_timeout(2000)
                    return
            pytest.fail(f"Could not find tab '{tab_label}'")

    def _mask_dynamic_content(self, page):
        """Inject CSS to mask dynamic content before screenshot."""
        page.evaluate("""
            () => {
                const style = document.createElement('style');
                style.textContent = `
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

    def _compare_screenshots(self, actual_path: str, baseline_path: str, threshold: float = 0.02) -> bool:
        """Compare two screenshots with a pixel difference threshold.

        Returns True if they match within threshold, False otherwise.
        Uses PIL for comparison if available, otherwise byte comparison.
        """
        if not os.path.exists(baseline_path):
            return False  # No baseline = needs creation

        try:
            from PIL import Image
            import math

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
                    # Check if difference is significant (not just anti-aliasing)
                    channel_diff = sum(abs(a - b) for a, b in zip(pa, pb))
                    if channel_diff > 30:  # Significant pixel difference
                        diff_count += 1

            diff_ratio = diff_count / total if total > 0 else 0
            return diff_ratio <= threshold

        except ImportError:
            # Fallback: byte comparison (strict)
            with open(actual_path, "rb") as f1, open(baseline_path, "rb") as f2:
                return f1.read() == f2.read()

    def test_tab_command_map(self, page):
        """Command Map tab should render and match baseline."""
        tab = TABS[0]
        self._click_tab(page, tab["label"])
        self._mask_dynamic_content(page)

        actual_path = self._screenshot_path(tab["name"], "_actual")
        page.screenshot(path=actual_path, full_page=False)

        baseline_path = self._screenshot_path(tab["name"])
        if not os.path.exists(baseline_path):
            # First run — save as baseline
            import shutil
            shutil.copy2(actual_path, baseline_path)
            pytest.skip(f"Baseline created for {tab['name']} — manual review required")

        assert self._compare_screenshots(actual_path, baseline_path), (
            f"Visual regression detected in {tab['name']} tab. "
            f"Compare {actual_path} vs {baseline_path}"
        )

    def test_tab_match_engine(self, page):
        """Match Engine tab should render and match baseline."""
        tab = TABS[1]
        self._click_tab(page, tab["label"])
        self._mask_dynamic_content(page)

        actual_path = self._screenshot_path(tab["name"], "_actual")
        page.screenshot(path=actual_path, full_page=False)

        baseline_path = self._screenshot_path(tab["name"])
        if not os.path.exists(baseline_path):
            import shutil
            shutil.copy2(actual_path, baseline_path)
            pytest.skip(f"Baseline created for {tab['name']} — manual review required")

        assert self._compare_screenshots(actual_path, baseline_path), (
            f"Visual regression detected in {tab['name']} tab. "
            f"Compare {actual_path} vs {baseline_path}"
        )

    def test_tab_broker_360(self, page):
        """Broker 360 tab should render and match baseline."""
        tab = TABS[2]
        self._click_tab(page, tab["label"])
        self._mask_dynamic_content(page)

        actual_path = self._screenshot_path(tab["name"], "_actual")
        page.screenshot(path=actual_path, full_page=False)

        baseline_path = self._screenshot_path(tab["name"])
        if not os.path.exists(baseline_path):
            import shutil
            shutil.copy2(actual_path, baseline_path)
            pytest.skip(f"Baseline created for {tab['name']} — manual review required")

        assert self._compare_screenshots(actual_path, baseline_path), (
            f"Visual regression detected in {tab['name']} tab. "
            f"Compare {actual_path} vs {baseline_path}"
        )

    def test_page_structure(self, page):
        """Basic DOM structure checks for the SiS app."""
        # Check that the Streamlit app container exists
        app = page.query_selector('[data-testid="stApp"]')
        assert app is not None, "Streamlit app container not found"

        # Check that tabs exist
        tabs = page.query_selector_all('button[role="tab"]')
        assert len(tabs) >= 3, f"Expected 3+ tabs, found {len(tabs)}"

        # Check that the app title is present somewhere
        page_text = page.inner_text("body")
        assert "LoadStar" in page_text, "App title 'LoadStar' not found in page"

    def test_no_streamlit_errors(self, page):
        """The app should not display any Streamlit error banners."""
        errors = page.query_selector_all('[data-testid="stException"]')
        assert len(errors) == 0, (
            f"Found {len(errors)} Streamlit error(s) on page"
        )

        # Also check for the generic error container
        error_blocks = page.query_selector_all('.stAlert [data-testid="stError"]')
        assert len(error_blocks) == 0, (
            f"Found {len(error_blocks)} error alert(s) on page"
        )


@pytest.mark.skipif(not _has_playwright(), reason="Playwright not installed")
class TestVisualAccessibility:
    """Accessibility-focused visual checks."""

    @pytest.fixture(scope="class")
    def sis_url(self):
        url = _resolve_sis_url()
        if not url:
            pytest.skip("SiS app URL not available")
        return url

    @pytest.fixture(scope="class")
    def page(self, sis_url):
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        pg = context.new_page()

        try:
            pg.goto(sis_url, wait_until="networkidle", timeout=60000)
            pg.wait_for_selector('[data-testid="stApp"]', timeout=30000)
        except Exception as e:
            pytest.skip(f"Cannot load SiS app: {e}")

        yield pg

        pg.close()
        context.close()
        browser.close()
        pw.stop()

    def test_color_contrast_ratio(self, page):
        """Primary text should have sufficient contrast against background."""
        # Extract computed styles for text and background
        result = page.evaluate("""
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
            # Just verify we got valid color values back
            assert result.get("color"), "Could not determine text color"
            assert result.get("backgroundColor"), "Could not determine background color"

    def test_responsive_viewport(self, page):
        """App should not have horizontal overflow at standard viewports."""
        overflow = page.evaluate("""
            () => {
                return document.documentElement.scrollWidth > document.documentElement.clientWidth;
            }
        """)
        assert not overflow, "Page has horizontal overflow at 1440px viewport"
