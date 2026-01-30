"""Debug script to inspect BFI website HTML structure."""

import asyncio
from datetime import date

from playwright.async_api import async_playwright


async def fetch_bfi_html():
    """Fetch and save BFI HTML for inspection."""
    url = "https://whatson.bfi.org.uk/Online/default.asp?BOparam::WScontent::loadArticle::permalink=whats-on&BOparam::WScontent::loadArticle::context_id=&date=2026-01-31"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Show browser for debugging
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            print(f"Navigating to: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Wait for Cloudflare challenge
            print("Waiting for Cloudflare challenge...")
            try:
                await page.wait_for_selector('body:not(:has-text("Just a moment"))', timeout=20000)
                print("✓ Challenge passed!")
            except:
                print("⚠ Challenge may still be present")

            await page.wait_for_timeout(5000)

            html = await page.content()

            # Save to file
            with open("bfi_page.html", "w", encoding="utf-8") as f:
                f.write(html)

            print(f"✓ HTML saved to bfi_page.html ({len(html)} bytes)")
            print("\nFirst 2000 characters:")
            print(html[:2000])

            # Try to find common elements
            print("\n" + "="*50)
            print("Looking for common selectors...")

            selectors_to_try = [
                ("div.event", "Event divs"),
                ("div.screening", "Screening divs"),
                ("article", "Articles"),
                ("div.film-item", "Film items"),
                ("li.showing", "Showing list items"),
                ("h2, h3, h4", "Headings"),
                ("a[href*='book']", "Booking links"),
            ]

            for selector, desc in selectors_to_try:
                count = await page.locator(selector).count()
                print(f"  {desc} ({selector}): {count} found")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(fetch_bfi_html())
