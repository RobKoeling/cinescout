from bs4 import BeautifulSoup
import re

with open('prince_charles_page.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Look for calendarfilm-filmdata divs (these contain film titles)
film_data_divs = soup.find_all('div', class_='calendarfilm-filmdata')
print(f'Total calendarfilm-filmdata divs: {len(film_data_divs)}\n')

if film_data_divs:
    for i, film_div in enumerate(film_data_divs[:3]):  # First 3 films
        print(f'\n{"="*60}')
        print(f'FILM {i+1}')
        print("="*60)

        # Get film title
        film_link = film_div.find('a', href=lambda x: x and '/film/' in x)
        if film_link:
            title = film_link.get_text(strip=True)
            url = film_link.get('href')
            print(f'Title: {title}')
            print(f'URL: {url}')

        # Look for parent container that groups this film with its times
        parent = film_div.parent
        print(f'\nParent: <{parent.name}> class={parent.get("class")}')

        # Go up one more level
        grandparent = parent.parent if parent else None
        if grandparent:
            print(f'Grandparent: <{grandparent.name}> class={grandparent.get("class")}')

            # Look for times within the grandparent
            time_spans = grandparent.find_all('span', class_='time')
            print(f'\nTimes in grandparent: {len(time_spans)}')
            for time_span in time_spans[:5]:
                time_text = time_span.get_text(strip=True)
                print(f'  - {time_text}')

                # Check if wrapped in link
                if time_span.parent.name == 'a':
                    booking_url = time_span.parent.get('href')
                    if booking_url:
                        print(f'    Booking: {booking_url}')

        # Look for perf data (performance/showing data) nearby
        perf_divs = parent.find_all('div', class_='calendarfilm-perfdata') if parent else []
        if perf_divs:
            print(f'\nPerformance data divs: {len(perf_divs)}')
            for perf_div in perf_divs[:2]:
                # Look for dates
                date_text = perf_div.get_text(strip=True)
                if date_text:
                    print(f'  Content: {date_text[:100]}')

# Let's also look for date headers
print('\n\n' + '='*60)
print('DATE STRUCTURE')
print('='*60)

# Look for date-related elements
date_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))', re.I))
print(f'Found {len(date_headers)} date headers')
for header in date_headers[:3]:
    print(f'  <{header.name}>: {header.get_text(strip=True)}')
