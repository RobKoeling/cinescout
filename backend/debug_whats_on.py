from bs4 import BeautifulSoup

with open('prince_charles_whats_on.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Check for calendarfilm-filmdata divs
film_data_divs = soup.find_all('div', class_='calendarfilm-filmdata')
print(f'calendarfilm-filmdata divs: {len(film_data_divs)}')

# Check for time spans
time_spans = soup.find_all('span', class_='time')
print(f'time spans: {len(time_spans)}')

# Look for film links
film_links = soup.find_all('a', href=lambda x: x and '/film/' in x)
print(f'film links: {len(film_links)}')

# Look for different date structure - maybe it's organized by date?
print('\nLooking for date headers...')
import re
date_headers = soup.find_all(['h2', 'h3', 'h4', 'div'], string=re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', re.I))
print(f'Found {len(date_headers)} date headers')
for header in date_headers[:5]:
    print(f'  {header.name}: {header.get_text(strip=True)[:60]}')

# Look for different classes
print('\nLooking for film container classes...')
all_divs_with_class = soup.find_all('div', class_=True)
class_counts = {}
for div in all_divs_with_class:
    for cls in div.get('class', []):
        if 'film' in cls.lower() or 'event' in cls.lower() or 'show' in cls.lower():
            class_counts[cls] = class_counts.get(cls, 0) + 1

for cls, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f'  .{cls}: {count}')
