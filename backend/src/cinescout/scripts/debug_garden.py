"""Debug script to inspect The Garden Cinema HTML structure."""

import asyncio

import httpx
from bs4 import BeautifulSoup


async def fetch_garden_html():
    """Fetch and analyze The Garden Cinema HTML."""
    url = "https://www.thegardencinema.co.uk"

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        print(f"Fetching: {url}")
        response = await client.get(url)
        response.raise_for_status()

        html = response.text

        # Save to file
        with open("garden_page.html", "w", encoding="utf-8") as f:
            f.write(html)

        print(f"✓ HTML saved to garden_page.html ({len(html)} bytes)")

        # Parse and analyze
        soup = BeautifulSoup(html, "html.parser")

        print("\n" + "="*50)
        print("ANALYZING STRUCTURE")
        print("="*50)

        # Look for film-related elements
        print("\n1. Links containing 'film':")
        film_links = soup.find_all("a", href=lambda x: x and "/film/" in x)
        for link in film_links[:5]:
            print(f"  - {link.get('href')}: {link.get_text(strip=True)[:60]}")

        print(f"\n  Total film links: {len(film_links)}")

        # Look for booking links
        print("\n2. Booking links (bookings.thegardencinema.co.uk):")
        booking_links = soup.find_all("a", href=lambda x: x and "bookings.thegardencinema.co.uk" in x)
        for link in booking_links[:5]:
            print(f"  - {link.get_text(strip=True)}")
            print(f"    URL: {link.get('href')[:100]}")

        print(f"\n  Total booking links: {len(booking_links)}")

        # Look for time patterns
        print("\n3. Elements containing time patterns (HH:MM):")
        import re
        time_pattern = re.compile(r'\b\d{1,2}:\d{2}\b')
        time_elements = soup.find_all(string=time_pattern)
        for elem in time_elements[:10]:
            print(f"  - {elem.strip()}")
            print(f"    Parent: {elem.parent.name if elem.parent else 'None'}")

        # Look for common container classes
        print("\n4. Common div classes:")
        all_divs = soup.find_all("div", class_=True)
        class_counts = {}
        for div in all_divs:
            classes = div.get("class", [])
            for cls in classes:
                class_counts[cls] = class_counts.get(cls, 0) + 1

        for cls, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            if count > 2:
                print(f"  - .{cls}: {count}")


if __name__ == "__main__":
    asyncio.run(fetch_garden_html())
