import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
import time
from collections import deque

BASE_URL = "https://pacificcross.com.vn/vi/"
DOMAIN = urlparse(BASE_URL).netloc
OUTPUT_DIR = "pacific_cross_all_pdfs"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

visited_pages = set()
queue = deque([BASE_URL])
pdf_urls = set()

print(f"Starting deep crawl of {BASE_URL}...")

# Limit total pages to avoid excessive crawling if it's a huge site
# Adjust as needed, but for a corporate site, usually a few hundred pages max.
MAX_PAGES = 500 

count = 0
while queue and count < MAX_PAGES:
    url = queue.popleft()
    if url in visited_pages:
        continue
    
    visited_pages.add(url)
    count += 1
    
    print(f"[{count}] Crawling: {url}")
    try:
        response = requests.get(url, timeout=20)
        # Check if it's actually an HTML page
        if 'text/html' not in response.headers.get('Content-Type', ''):
            continue
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)
            
            # Check if it's a PDF
            if full_url.lower().endswith('.pdf'):
                if full_url not in pdf_urls:
                    pdf_urls.add(full_url)
                    print(f"  Found PDF: {full_url}")
                    # Download immediately or later? Let's download immediately to be sure.
                    filename = os.path.join(OUTPUT_DIR, os.path.basename(parsed_url.path))
                    # Basic filename sanitization
                    if not filename.endswith('.pdf'):
                        filename += '.pdf'
                    
                    try:
                        pdf_resp = requests.get(full_url, timeout=30)
                        with open(filename, 'wb') as f:
                            f.write(pdf_resp.content)
                        print(f"    Saved to {filename}")
                    except Exception as e:
                        print(f"    Error downloading PDF {full_url}: {e}")
            
            # Check if it's an internal link to crawl further
            elif parsed_url.netloc == DOMAIN and full_url.startswith(BASE_URL):
                # Strip fragments to avoid redundant crawls
                clean_url = full_url.split('#')[0]
                if clean_url not in visited_pages:
                    queue.append(clean_url)
                    
    except Exception as e:
        print(f"  Error crawling {url}: {e}")
    
    # Small delay to be polite
    time.sleep(0.1)

print(f"\nCrawling finished. Visited {count} pages.")
print(f"Found and downloaded {len(pdf_urls)} unique PDFs.")
