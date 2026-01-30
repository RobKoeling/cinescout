from bs4 import BeautifulSoup

with open('garden_page.html') as f:
    soup = BeautifulSoup(f, 'html.parser')

# Check first film container structure
containers = soup.find_all('div', class_='films-list__by-date__film')
print(f'Total containers: {len(containers)}\n')

if containers:
    first = containers[0]
    print('First container structure:')
    print('=' * 50)
    
    # Check for title link
    title_link = first.find('a', href=lambda x: x and '/film/' in x)
    if title_link:
        print(f'Title link found: {title_link.get("href")}')
        print(f'Title text: {title_link.get_text(strip=True)}')
    else:
        print('NO TITLE LINK FOUND')
    
    # Check for screening times container
    screening_times = first.find('div', class_='films-list__by-date__film__screeningtimes')
    if screening_times:
        print(f'\nScreening times container found')
        panels = screening_times.find_all('div', class_='screening-panel')
        print(f'Screening panels: {len(panels)}')
        
        if panels:
            first_panel = panels[0]
            print(f'\nFirst panel:')
            date_title = first_panel.find('div', class_='screening-panel__date-title')
            if date_title:
                print(f'  Date: {date_title.get_text(strip=True)}')
            else:
                print('  NO DATE TITLE')
            
            time_links = first_panel.find_all('a', href=lambda x: x and 'bookings.thegardencinema.co.uk' in x)
            print(f'  Time links: {len(time_links)}')
            for link in time_links[:3]:
                print(f'    - {link.get_text(strip=True)}: {link.get("href")[:80]}')
    else:
        print('NO SCREENING TIMES CONTAINER')
