import os
import requests
import re
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions
from urllib.parse import urlparse

# API Key and URLs
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
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

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def get_site_folder_name(url):
    parsed = urlparse(url)
    name = parsed.netloc.replace("www.", "")
    return name

def download_pdf(url, folder):
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    name = sanitize_filename(os.path.basename(urlparse(url).path))
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    
    path = os.path.join(folder, name)
    
    try:
        print(f"  Downloading: {url}")
        resp = requests.get(url, timeout=30, verify=False)
        if resp.status_code == 200:
            with open(path, 'wb') as f:
                f.write(resp.content)
            print(f"    Saved to {folder}/{name}")
        else:
            print(f"    Failed (Status {resp.status_code})")
    except Exception as e:
        print(f"    Error: {e}")

def scrape_with_firecrawl(base_url):
    # Khởi tạo ứng dụng với API Key từ môi trường
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    folder_name = get_site_folder_name(base_url)
    
    print(f"\n>>> Firecrawl searching for PDFs on: {base_url}")
    
    # We use search to find PDF files directly on the domain
    # Or crawl and extract. Firecrawl is great at finding structured data.
    # Note: Firecrawl's 'crawl' returns page content. To find PDFs, we might need a specific approach.
    # A simple but effective way with Firecrawl is to use a search query or crawl with a filter.
    
    try:
        # Crawl options to find files
        scrape_opts = ScrapeOptions(
            only_main_content=False, # We want everything to find links
            formats=["markdown"]
        )
        
        print(f"  Starting crawl (limit 100 for test)...")
        crawl_result = app.crawl(
            base_url,
            params={
                "limit": 100,
                "scrapeOptions": scrape_opts
            }
        )
        
        # Firecrawl returns a list of pages. We extract PDF links from their content/metadata.
        # This is a bit indirect. If Firecrawl is used, it's often better for content.
        # For direct PDF discovery, their 'map' or 'search' might be faster.
        
        # In this implementation, we'll assume we parse the result or use Firecrawl's 
        # ability to find specific patterns if supported.
        
        # For simplicity in this script, since we want PDFs:
        print(f"  Crawl status: {crawl_result.get('status')}")
        # Note: In a real scenario, you'd iterate crawl_result['data'] and find PDF links.
        
    except Exception as e:
        print(f"  Firecrawl error: {e}")

def main():
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("Firecrawl is best for JS-heavy sites or bypassing bot detection.")
    print("For simple PDF link extraction, the requests+bs4 method is usually faster.")
    print("Updating original script with PVI and suggesting to use it first.")

if __name__ == "__main__":
    main()
