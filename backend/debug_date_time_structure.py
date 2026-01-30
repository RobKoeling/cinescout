"""Debug script to understand exact date-time grouping in PCC HTML."""

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

# Find all performance-list-items-outer divs
outer_divs = event.find_all('div', class_='performance-list-items-outer')
print(f'\nFound {len(outer_divs)} performance-list-items-outer divs\n')

for i, outer_div in enumerate(outer_divs[:3]):  # First 3 dates
    print(f'\n{"="*60}')
    print(f'OUTER DIV {i+1}')
    print("="*60)

    # Find the ul.performance-list-items inside
    perf_list = outer_div.find('ul', class_='performance-list-items')
    if not perf_list:
        print('No performance-list-items found')
        continue

    # Find date div within this specific ul
    date_divs = perf_list.find_all('div', string=re.compile(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+',
        re.IGNORECASE
    ))

    print(f'\nDate divs in this ul: {len(date_divs)}')
    for date_div in date_divs:
        print(f'  - {date_div.get_text(strip=True)}')

    # Find time spans within this specific ul
    time_spans = perf_list.find_all('span', class_='time')
    print(f'\nTime spans in this ul: {len(time_spans)}')
    for time_span in time_spans:
        print(f'  - {time_span.get_text(strip=True)}')
        if time_span.parent.name == 'a':
            print(f'    Booking: {time_span.parent.get("href", "")[:80]}')

    # Show the structure of list items
    print(f'\nList items (li) in this ul:')
    list_items = perf_list.find_all('li', recursive=False)
    print(f'  Count: {len(list_items)}')

    for j, li in enumerate(list_items[:5]):  # First 5 li elements
        # Check what's in each li
        has_date = li.find('div', string=re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', re.I))
        has_time = li.find('span', class_='time')

        content_summary = []
        if has_date:
            content_summary.append(f'DATE: {has_date.get_text(strip=True)[:30]}')
        if has_time:
            content_summary.append(f'TIME: {has_time.get_text(strip=True)}')

        if content_summary:
            print(f'    li[{j}]: {" | ".join(content_summary)}')

print('\n\n' + '='*60)
print('HYPOTHESIS CHECK')
print('='*60)
print('\nIs each performance-list-items-outer = one date with its times?')
print('Or does one outer contain multiple dates?')
