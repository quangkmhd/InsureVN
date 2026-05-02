import os
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions

# Sử dụng API key từ biến môi trường
app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))

scrape_opts = ScrapeOptions(
    only_main_content=True,
    max_age=172800000,
    formats=["markdown"]
)

crawl_result = app.crawl(
    "pacificcross.com.vn/",
    sitemap="include",
    crawl_entire_domain=True,
    limit=10000,
    scrape_options=scrape_opts
)

print(crawl_result)
