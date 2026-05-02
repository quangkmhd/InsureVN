import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin

url = "https://pacificcross.com.vn/vi/forms-and-policies/"
output_dir = "pacific_cross_pdfs"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print(f"Scraping links from {url}...")
try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    pdf_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.lower().endswith('.pdf'):
            full_url = urljoin(url, href)
            pdf_links.append(full_url)

    # De-duplicate
    pdf_links = list(set(pdf_links))
    print(f"Found {len(pdf_links)} PDF links.")

    for i, link in enumerate(pdf_links):
        filename = os.path.join(output_dir, os.path.basename(link))
        print(f"Downloading [{i+1}/{len(pdf_links)}]: {link}")
        try:
            pdf_response = requests.get(link, timeout=60)
            pdf_response.raise_for_status()
            with open(filename, 'wb') as f:
                f.write(pdf_response.content)
            print(f"  Saved to {filename}")
        except Exception as e:
            print(f"  Error downloading {link}: {e}")

    print("Done!")

except Exception as e:
    print(f"An error occurred: {e}")
