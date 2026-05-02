import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
import time
from collections import deque
import re

# List of target websites
TARGET_URLS = [
    "https://baoviet-online.vn/",
    "https://www.baominh.com.vn/",
    "https://bic.vn/",
    "https://myvbi.vn/",
    "https://www.libertyinsurance.com.vn/",
    "https://generali.vn/",
    "https://www.pti.com.vn/",
    "https://www.aia.com.vn/vi.html",
    "https://www.pvicare.net/"
]

# Configuration
MAX_PAGES_PER_SITE = 2000  # Limit per site to avoid infinite loops or excessive load
CRAWL_DELAY = 0.5         # Seconds between requests to be polite
TIMEOUT = 30              # Request timeout

import urllib.parse
import unicodedata

def remove_vietnamese_accents(s):
    """Remove Vietnamese accents from a string."""
    s = s.replace('đ', 'd').replace('Đ', 'D')
    nfkd_form = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def sanitize_filename(name):
    """Sanitize filename: decode URL, remove accents, and clean special chars."""
    # Decode URL-encoded characters like %20
    name = urllib.parse.unquote(name)
    # Remove accents
    name = remove_vietnamese_accents(name)
    # Basic cleaning of special characters
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # Replace multiple underscores or spaces with a single one
    name = re.sub(r'\s+', "_", name)
    return name.strip()

def get_site_folder_name(url):
    """Extract a clean folder name from the URL."""
    parsed = urlparse(url)
    name = parsed.netloc.replace("www.", "")
    if not name: # For cases like local files or weird URLs
        name = sanitize_filename(url.replace("https://", "").replace("http://", "").strip("/"))
    return name

def scrape_site(base_url):
    """Scrape a single site for all PDFs."""
    site_domain = urlparse(base_url).netloc
    folder_name = get_site_folder_name(base_url)
    
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        
    visited_pages = set()
    queue = deque([base_url])
    pdf_urls = set()
    
    print(f"\n>>> Starting scrape for: {base_url}")
    print(f">>> Saving to folder: {folder_name}")
    
    count = 0
    while queue and count < MAX_PAGES_PER_SITE:
        url = queue.popleft()
        if url in visited_pages:
            continue
        
        visited_pages.add(url)
        count += 1
        
        print(f"[{folder_name}] ({count}/{MAX_PAGES_PER_SITE}) Crawling: {url}")
        
        try:
            # Using custom headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False) # verify=False for some older VN sites with SSL issues
            
            # Check if it's actually an HTML page
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                full_url = urljoin(url, href)
                parsed_url = urlparse(full_url)
                
                # Check if it's a PDF
                if full_url.lower().split('?')[0].endswith('.pdf'):
                    if full_url not in pdf_urls:
                        pdf_urls.add(full_url)
                        print(f"  [PDF] Found: {full_url}")
                        
                        # Download PDF
                        pdf_name = sanitize_filename(os.path.basename(parsed_url.path))
                        if not pdf_name.lower().endswith('.pdf'):
                            pdf_name += '.pdf'
                        
                        file_path = os.path.join(folder_name, pdf_name)
                        
                        try:
                            pdf_resp = requests.get(full_url, headers=headers, timeout=TIMEOUT, verify=False)
                            if pdf_resp.status_code == 200:
                                with open(file_path, 'wb') as f:
                                    f.write(pdf_resp.content)
                                print(f"    Saved: {pdf_name}")
                            else:
                                print(f"    Failed to download (Status {pdf_resp.status_code})")
                        except Exception as e:
                            print(f"    Download error: {e}")
                
                # Check if it's an internal link to crawl further
                elif parsed_url.netloc == site_domain:
                    # Strip fragments and queries to avoid redundant crawls
                    clean_url = full_url.split('#')[0].split('?')[0]
                    # Ensure it's still under the base URL path logic if needed, 
                    # but for these sites, staying within domain is usually enough.
                    if clean_url not in visited_pages and clean_url.startswith(('http://', 'https://')):
                        queue.append(clean_url)
                        
        except Exception as e:
            print(f"  Error crawling {url}: {e}")
        
        time.sleep(CRAWL_DELAY)

    print(f"\n>>> Finished {base_url}. Found {len(pdf_urls)} PDFs.")

def main():
    # Disable warnings for insecure requests (verify=False)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    for url in TARGET_URLS:
        try:
            scrape_site(url)
        except Exception as e:
            print(f"Critical error on site {url}: {e}")

if __name__ == "__main__":
    main()
