import os
from firecrawl import FirecrawlApp
# Lưu ý: Class chính xác trong thư viện firecrawl-py thường là FirecrawlApp
# Nếu bạn cài đặt bằng 'pip install firecrawl-py'

def crawl_pacific_cross():
    # Khởi tạo ứng dụng với API Key từ môi trường
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

    # Cấu hình các tùy chọn cào (Scrape Options)
    scrape_opts = {
        "onlyMainContent": True,
        "formats": ["markdown"]
    }

    print("Đang bắt đầu quá trình crawl toàn bộ domain pacificcross.com.vn...")
    
    # Thực hiện crawl
    # Lưu ý: Các tham số có thể thay đổi tùy theo version của SDK
    crawl_result = app.crawl_url(
        "https://pacificcross.com.vn/",
        params={
            "limit": 10000,
            "scrapeOptions": scrape_opts
        }
    )

    print("Quá trình crawl hoàn tất!")
    print(crawl_result)

if __name__ == "__main__":
    crawl_pacific_cross()
