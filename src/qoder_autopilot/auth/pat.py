"""
Qoder Autopilot — PAT (Personal Access Token) Creation
========================================================
Creates a Personal Access Token on Qoder's integrations page
via browser automation, after the user is logged in.

Flow:
    1. Navigate to qoder.com/account/integrations
    2. Click "+ New Token" button
    3. Fill Name field with "a"
    4. Set expiration date to 31/7/2026
    5. Click Create button
    6. Read and return the PAT value
"""

import asyncio
import re

from ..infra import config
from ..utils.logger import log, log_err, log_ok, log_warn


async def create_pat(page) -> str | None:
    """Create a Personal Access Token via the Qoder integrations page.

    Must be called while the user is logged in (browser has active session
    on qoder.com).

    Args:
        page: Playwright/Camoufox page object (must be logged in).

    Returns:
        The PAT token string on success, None on failure.
    """
    log("   🔑 Step: Creating PAT (Personal Access Token)...")

    # ═══ 1. Navigate to integrations page ═══
    try:
        await page.goto(
            config.QODER_INTEGRATIONS_URL,
            wait_until="networkidle",
            timeout=30000,
        )
        await asyncio.sleep(1.5)
        log(f"   📍 Navigated to {config.QODER_INTEGRATIONS_URL}")
    except Exception as e:
        log_err(f"Failed to navigate to integrations page: {e}")
        await _debug_screenshot(page, "pat_nav_fail.png")
        return None

    # ═══ 2. Click "+ New Token" button ═══
    try:
        new_token_btn = page.locator(
            'xpath=/html/body/div[1]/div/div/div/main/div[2]/div[3]/div[1]/button'
        )
        await new_token_btn.wait_for(state="visible", timeout=15000)
        await new_token_btn.click()
        log("   ✅ Clicked '+ New Token' button")
        await asyncio.sleep(1)
    except Exception as e:
        log_err(f"Failed to click '+ New Token' button: {e}")
        # Fallback: try text-based selector
        try:
            fallback_btn = page.locator('button:has-text("New Token")').first
            await fallback_btn.wait_for(state="visible", timeout=5000)
            await fallback_btn.click()
            log("   ✅ Clicked '+ New Token' via fallback")
            await asyncio.sleep(1)
        except Exception as e2:
            log_err(f"Fallback also failed: {e2}")
            await _debug_screenshot(page, "pat_btn_fail.png")
            return None

    # ═══ 3. Wait for modal and fill Name field ═══
    try:
        name_input = page.locator(
            'xpath=/html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div[1]/input'
        )
        await name_input.wait_for(state="visible", timeout=10000)
        await name_input.fill("a")
        log('   ✅ Filled name: "a"')
        await asyncio.sleep(0.5)
    except Exception as e:
        log_err(f"Failed to fill name input: {e}")
        await _debug_screenshot(page, "pat_name_fail.png")
        return None

    # ═══ 4. Set expiration date ═══
    try:
        date_picker = page.locator(
            'xpath=/html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div[2]/div'
        )
        await date_picker.wait_for(state="visible", timeout=5000)
        await date_picker.click()
        await asyncio.sleep(0.3)

        # Try to clear and fill the date input
        # First check if it's an input or a date picker component
        date_input = date_picker.locator("input").first
        if await date_input.count() > 0:
            await date_input.fill("")
            await date_input.fill("31/7/2026")
        else:
            # Try typing directly into the picker div
            await date_picker.fill("31/7/2026")
            await page.keyboard.press("Tab")

        log("   ✅ Set expiration date: 31/7/2026")
        await asyncio.sleep(0.5)
    except Exception as e:
        log_err(f"Failed to set expiration date: {e}")
        # Non-fatal — try to continue
        log_warn("Date picker failed, continuing anyway...")

    # ═══ 5. Click Create button ═══
    try:
        create_btn = page.locator(
            'xpath=/html/body/div[2]/div/div[2]/div/div[1]/div/div[3]/div/div/button[2]'
        )
        await create_btn.wait_for(state="visible", timeout=5000)
        await create_btn.click()
        log("   ✅ Clicked Create button")
        await asyncio.sleep(2)
    except Exception as e:
        log_err(f"Failed to click Create button: {e}")
        # Fallback: try finding a button with "Create" text in the modal
        try:
            fallback_create = page.locator(
                'xpath=/html/body/div[2]/div/div[2]/div/div[1]/div[3]/div/div/button[2]'
            )
            await fallback_create.wait_for(state="visible", timeout=3000)
            await fallback_create.click()
            log("   ✅ Clicked Create via fallback")
            await asyncio.sleep(2)
        except Exception:
            await _debug_screenshot(page, "pat_create_fail.png")
            return None

    # ═══ 6. Read the PAT value ═══
    try:
        pat_display = page.locator(
            'xpath=/html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div[2]/div'
        )
        await pat_display.wait_for(state="visible", timeout=10000)
        pat_text = await pat_display.text_content()

        if pat_text:
            pat_text = pat_text.strip()
            # The PAT might be a full token string (e.g., "qoder_pat_...")
            log_ok(f"🎉 PAT created: {pat_text[:20]}...")
            await _debug_screenshot(page, "pat_success.png")
            return pat_text
        else:
            log_err("PAT display element is empty")
            await _debug_screenshot(page, "pat_empty.png")
            return None
    except Exception as e:
        log_err(f"Failed to read PAT value: {e}")
        # Try to extract PAT from the page text
        try:
            page_text = await page.evaluate(
                "() => document.body?.innerText || ''"
            )
            # Look for PAT-like strings
            pat_match = re.search(
                r'(qoder_pat_[a-zA-Z0-9_]+|[a-zA-Z0-9_-]{20,})',
                page_text,
            )
            if pat_match:
                pat = pat_match.group(1)
                log_ok(f"🎉 PAT extracted from page: {pat[:20]}...")
                await _debug_screenshot(page, "pat_success.png")
                return pat
        except Exception:
            pass
        await _debug_screenshot(page, "pat_read_fail.png")
        return None


async def _debug_screenshot(page, filename: str) -> None:
    """Take a debug screenshot if the screenshots directory is available."""
    try:
        config.SCREENSHOTS_DIR.mkdir(exist_ok=True)
        await page.screenshot(path=str(config.SCREENSHOTS_DIR / filename))
        log(f"   📸 Screenshot saved: {filename}")
    except Exception:
        pass
