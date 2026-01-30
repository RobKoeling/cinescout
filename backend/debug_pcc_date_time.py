from bs4 import BeautifulSoup
import re

with open('prince_charles_whats_on.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Get first jacro-event
event = soup.find('div', class_='jacro-event')

print('First event structure:')
print('=' * 60)

# Get film title
film_link = event.find('a', href=re.compile(r'/film/\d+/'))
if film_link:
    print(f'Film: {film_link.get_text(strip=True)}')

# Find date divs
date_divs = event.find_all('div', string=re.compile(
    r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+',
    re.IGNORECASE
))

print(f'\nDate divs found: {len(date_divs)}')

for i, date_div in enumerate(date_divs[:2]):
    print(f'\n--- Date {i+1} ---')
    print(f'Date text: {date_div.get_text(strip=True)}')
    print(f'Date div parent: {date_div.parent.name}, class: {date_div.parent.get("class")}')

    # Find times in parent
    date_parent = date_div.parent
    time_spans = date_parent.find_all('span', class_='time')
    print(f'Time spans in parent: {len(time_spans)}')
    for time_span in time_spans:
        print(f'  - {time_span.get_text(strip=True)}')

    # Try going up another level
    grandparent = date_parent.parent if date_parent else None
    if grandparent:
        print(f'\nGrandparent: {grandparent.name}, class: {grandparent.get("class", [])}')
        time_spans_gp = grandparent.find_all('span', class_='time')
        print(f'Time spans in grandparent: {len(time_spans_gp)}')

print('\n\n' + '='*60)
print('Looking at overall jacrofilm-list-content structure')
print('='*60)

# Find jacrofilm-list-content within first event
content_div = event.find('div', class_='jacrofilm-list-content')
if content_div:
    print('Found jacrofilm-list-content')

    # Look for all children
    for child in content_div.children:
        if hasattr(child, 'name') and child.name:
            print(f'  Child: {child.name}, class: {child.get("class", [])}')
            # Check if it has date or time info
            has_date = child.find('div', string=re.compile(r'(Monday|Tuesday|Wednesday)', re.I))
            has_time = child.find('span', class_='time')
            if has_date:
                print(f'    -> Has date')
            if has_time:
                print(f'    -> Has time')
