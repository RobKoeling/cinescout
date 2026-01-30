from bs4 import BeautifulSoup
import re

with open('prince_charles_whats_on.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Look at jacro-event containers
jacro_events = soup.find_all('div', class_='jacro-event')
print(f'Total jacro-event containers: {len(jacro_events)}\n')

if jacro_events:
    first = jacro_events[0]
    print('First jacro-event structure:')
    print('=' * 60)

    # Look for film title
    film_links = first.find_all('a', href=re.compile(r'/film/'))
    print(f'\nFilm links: {len(film_links)}')
    for link in film_links[:2]:
        text = link.get_text(strip=True)
        if text and 'Other dates' not in text:
            print(f'  Title: {text}')
            print(f'  URL: {link.get("href")}')

    # Look for date
    date_divs = first.find_all('div', string=re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'))
    if date_divs:
        print(f'\nDate divs: {len(date_divs)}')
        for date_div in date_divs[:2]:
            print(f'  {date_div.get_text(strip=True)}')

    # Look for times
    time_spans = first.find_all('span', class_='time')
    print(f'\nTime spans: {len(time_spans)}')
    for time_span in time_spans[:5]:
        print(f'  - {time_span.get_text(strip=True)}')
        if time_span.parent and time_span.parent.name == 'a':
            print(f'    URL: {time_span.parent.get("href", "")[:80]}')

    # Show the overall structure
    print('\n\nOverall structure:')
    print(f'Parent: {first.parent.name if first.parent else None}')
    print(f'Classes on jacro-event: {first.get("class")}')

    # Look for jacrofilm-list-content inside
    content_divs = first.find_all('div', class_='jacrofilm-list-content')
    print(f'\njacrofilm-list-content divs inside: {len(content_divs)}')
