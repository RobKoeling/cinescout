"""Debug where date divs are located."""

from bs4 import BeautifulSoup
import re

with open('prince_charles_whats_on.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Get first jacro-event
event = soup.find('div', class_='jacro-event')

# Get film title
title_link = event.find('a', class_='liveeventtitle')
print(f'Film: {title_link.get_text(strip=True)}')
print('=' * 60)

# Find all date divs
date_divs = event.find_all('div', string=re.compile(
    r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+',
    re.IGNORECASE
))

print(f'\nFound {len(date_divs)} date divs\n')

for i, date_div in enumerate(date_divs[:3]):
    print(f'\n{"="*60}')
    print(f'DATE DIV {i+1}: {date_div.get_text(strip=True)}')
    print("="*60)

    print(f'Tag: {date_div.name}')
    print(f'Classes: {date_div.get("class")}')

    # Walk up the tree
    print(f'\nParent hierarchy:')
    current = date_div
    for level in range(5):
        if current.parent:
            current = current.parent
            classes = current.get('class', [])
            print(f'  Level {level+1}: <{current.name}> class={classes}')

    # Look for siblings
    print(f'\nSiblings of date div:')
    if date_div.parent:
        siblings = [s for s in date_div.parent.children if hasattr(s, 'name') and s.name]
        print(f'  Parent has {len(siblings)} child elements')
        for j, sib in enumerate(siblings[:10]):
            # Check if it's the date div or something else
            if sib == date_div:
                print(f'    [{j}] THIS DATE DIV')
            else:
                # Check if it has times
                time_span = sib.find('span', class_='time') if hasattr(sib, 'find') else None
                if time_span:
                    print(f'    [{j}] <{sib.name}> - Contains TIME: {time_span.get_text(strip=True)}')
                else:
                    text = sib.get_text(strip=True)[:50] if hasattr(sib, 'get_text') else ''
                    if text:
                        print(f'    [{j}] <{sib.name}> - {text}')

print('\n\n' + '='*60)
print('CHECKING: Are dates and times siblings in the same parent?')
print('='*60)

# Check if first date and first time share a parent
first_date = date_divs[0]
first_time = event.find('span', class_='time')

if first_date.parent == first_time.parent:
    print('YES - dates and times are siblings')
else:
    print('NO - dates and times have different parents')
    print(f'Date parent: {first_date.parent.name}.{first_date.parent.get("class")}')
    print(f'Time parent: {first_time.parent.name}.{first_time.parent.get("class")}')
