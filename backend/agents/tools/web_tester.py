"""
Shadow DOM Web Tester
──────────────────────
A complex tool utilizing Playwright to autonomously navigate websites,
interact with Shadow DOM elements, and capture state for Vision Pipeline analysis.
"""

import time
import logging
from typing import Dict, Any, Optional

try:
    from playwright.sync_api import sync_playwright, Browser, Page
except ImportError:
    sync_playwright = None

logger = logging.getLogger(__name__)

class ShadowDOMTester:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright_context = None

    def start(self, headless: bool = True):
        """Initialize the Playwright core."""
        if sync_playwright is None:
            logger.error("Playwright not installed! Run `pip install playwright && playwright install`")
            return False
            
        self._playwright_context = sync_playwright().start()
        self.browser = self._playwright_context.chromium.launch(headless=headless)
        self.page = self.browser.new_page()
        logger.info("🕸️ Shadow DOM Web Tester fully initialized.")
        return True

    def stop(self):
        """Shutdown the browser and free memory."""
        if self.browser:
            self.browser.close()
        if self._playwright_context:
            self._playwright_context.stop()
        logger.info("🕸️ Web Tester shutdown.")

    def navigate(self, url: str) -> bool:
        """Navigate to a URL and wait for the network to settle."""
        if not self.page:
            return False
        try:
            logger.info(f"Navigating to {url}...")
            self.page.goto(url, wait_until="networkidle")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate: {e}")
            return False

    def click_element(self, selector: str) -> bool:
        """Click an element, even if it's hidden inside a Shadow DOM."""
        if not self.page:
            return False
        try:
            # Playwright bypasses shadow DOM boundaries natively with normal CSS selectors!
            self.page.click(selector, force=True, timeout=2000)
            time.sleep(0.5) # Wait for UI reaction
            return True
        except Exception as e:
            logger.error(f"Could not click '{selector}': {e}")
            return False
            
    def type_text(self, selector: str, text: str) -> bool:
        """Type into an input field within the shadow DOM."""
        if not self.page:
            return False
        try:
            self.page.fill(selector, text, timeout=2000)
            return True
        except Exception as e:
            logger.error(f"Could not type in '{selector}': {e}")
            return False

    def get_dom_snapshot(self) -> Dict[str, Any]:
        """Extract a structured string of all accessible text and buttons."""
        if not self.page:
            return {}
            
        # Execute JS to pull relevant interactive elements
        snapshot = self.page.evaluate('''() => {
            const elements = document.querySelectorAll('button, a, input, [role="button"]');
            const data = [];
            elements.forEach(el => {
                const rect = el.getBoundingClientRect();
                data.push({
                    tag: el.tagName,
                    text: el.innerText || el.value || el.name || 'UNKNOWN',
                    x: rect.x,
                    y: rect.y,
                    visible: rect.width > 0 && rect.height > 0
                });
            });
            return data;
        }''')
        return {"elements": snapshot}

    def capture_screenshot(self, filename: str = "shadow_state.png") -> str:
        """Take a full-page screenshot for Vision Pipeline ingestion."""
        if not self.page:
            return ""
        try:
            path = f"data/uploads/{filename}"
            self.page.screenshot(path=path, full_page=True)
            logger.info(f"📸 Shadow DOM state captured: {path}")
            return path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""
