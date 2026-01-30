from bs4 import BeautifulSoup

with open('prince_charles_page.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Look for elements with film_img class
film_containers = soup.find_all('div', class_='film_img')
print(f'Total film_img containers: {len(film_containers)}\n')

if film_containers:
    first = film_containers[0]
    print('First container structure:')
    print('=' * 50)

    # Get parent context
    parent = first.parent
    print(f'Parent tag: {parent.name}, classes: {parent.get("class")}')

    # Find film link
    film_link = first.find('a', href=lambda x: x and '/film/' in x)
    if film_link:
        print(f'\nFilm link found: {film_link.get("href")}')
        # Check what's inside the link
        img = film_link.find('img')
        if img:
            print(f'  - Has img with alt: {img.get("alt")}')

    # Look for title in parent
    if parent:
        # Check for any text content
        title_elem = parent.find('h3') or parent.find('h4') or parent.find('h2')
        if title_elem:
            print(f'\nTitle element: <{title_elem.name}> {title_elem.get("class")}')
            print(f'  Text: {title_elem.get_text(strip=True)}')

        # Look for links with film title
        all_links = parent.find_all('a', href=lambda x: x and '/film/' in x)
        print(f'\nAll film links in parent: {len(all_links)}')
        for link in all_links:
            text = link.get_text(strip=True)
            if text:
                print(f'  - {text[:60]}')
                print(f'    URL: {link.get("href")[:80]}')

        # Look for time elements
        time_spans = parent.find_all('span', class_='time')
        if time_spans:
            print(f'\nTime spans found: {len(time_spans)}')
            for time_span in time_spans:
                print(f'  - {time_span.get_text(strip=True)}')
                # Check parent of time span
                time_parent = time_span.parent
                if time_parent and time_parent.name == 'a':
                    print(f'    Link: {time_parent.get("href")[:80]}')

print('\n\n' + '='*50)
print('Looking for content divs')
print('='*50)

# Look for divs with class "content"
content_divs = soup.find_all('div', class_='content')
print(f'Total content divs: {len(content_divs)}\n')

if content_divs:
    first_content = content_divs[0]
    print('First content div:')
    # Look for film titles
    film_links = first_content.find_all('a', href=lambda x: x and '/film/' in x)
    for link in film_links[:3]:
        print(f'  - {link.get_text(strip=True)[:60]}')

    # Look for times
    times = first_content.find_all('span', class_='time')
    print(f'\nTimes in first content: {len(times)}')
    for time in times[:5]:
        print(f'  - {time.get_text(strip=True)}')
