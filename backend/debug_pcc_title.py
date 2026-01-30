from bs4 import BeautifulSoup
import re

with open('prince_charles_whats_on.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Get first jacro-event
event = soup.find('div', class_='jacro-event')

print('Looking for film title...\n')

# Check all links
all_links = event.find_all('a')
print(f'Total links in event: {len(all_links)}\n')

for i, link in enumerate(all_links[:10]):
    href = link.get('href', '')
    text = link.get_text(strip=True)
    classes = link.get('class', [])
    if text:
        print(f'{i+1}. [{", ".join(classes)}] "{text}"')
        print(f'   href: {href[:80]}')

# Check for liveeventtitle
print('\n\nChecking liveeventtitle...')
live_event_title = event.find('a', class_='liveeventtitle')
if live_event_title:
    print(f'liveeventtitle text: "{live_event_title.get_text(strip=True)}"')
    print(f'liveeventtitle href: {live_event_title.get("href")}')

# Check img alt text
print('\n\nChecking img elements...')
imgs = event.find_all('img')
for img in imgs[:3]:
    alt = img.get('alt', '')
    if alt:
        print(f'img alt: "{alt}"')
