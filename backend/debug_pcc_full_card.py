from bs4 import BeautifulSoup

with open('prince_charles_page.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Look for rows that might contain both image and content
rows = soup.find_all('div', class_='row')
print(f'Total rows: {len(rows)}\n')

# Find a row with both film_img and time elements
for i, row in enumerate(rows):
    film_imgs = row.find_all('div', class_='film_img')
    time_spans = row.find_all('span', class_='time')

    if film_imgs and time_spans:
        print(f'\n{"="*60}')
        print(f'ROW {i} - Has {len(film_imgs)} film_img(s) and {len(time_spans)} time(s)')
        print("="*60)

        # Get film link from first film_img
        first_img = film_imgs[0]
        film_link = first_img.find('a', href=lambda x: x and '/film/' in x)
        if film_link:
            print(f'\nFilm URL: {film_link.get("href")}')

        # Look for title - check siblings of film_img
        parent_cols = row.find_all('div', class_=lambda x: x and 'col' in ' '.join(x) if x else False)
        print(f'\nColumns in row: {len(parent_cols)}')

        # Try to find title in the row
        all_film_links = row.find_all('a', href=lambda x: x and '/film/' in x)
        print(f'\nAll film links: {len(all_film_links)}')
        for link in all_film_links[:3]:
            text = link.get_text(strip=True)
            if text and text != 'filmimg':
                print(f'  Title link: {text}')
                print(f'    URL: {link.get("href")[:80]}')
                print(f'    Parent tag: {link.parent.name}, class: {link.parent.get("class")}')

        # Show times
        print(f'\nTimes:')
        for time_span in time_spans[:3]:
            print(f'  - {time_span.get_text(strip=True)}')
            # Check if time is in a link
            time_parent = time_span.parent
            if time_parent.name == 'a' and time_parent.get('href'):
                print(f'    Booking URL: {time_parent.get("href")[:100]}')

        # Only show first matching row in detail
        break

# Also look for film title patterns
print('\n\n' + '='*60)
print('Looking for h3/h4 elements near times')
print('='*60)

time_spans = soup.find_all('span', class_='time')
if time_spans:
    first_time = time_spans[0]
    # Walk up to find containing structure
    current = first_time
    for _ in range(5):  # Go up 5 levels max
        if current.parent:
            current = current.parent
            # Check for headings at this level
            headings = current.find_all(['h2', 'h3', 'h4'])
            if headings:
                print(f'\nFound headings at level {current.name}.{current.get("class")}')
                for h in headings[:2]:
                    print(f'  <{h.name}>: {h.get_text(strip=True)[:60]}')
