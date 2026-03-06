# Test individual components
from src.data_collection import OpenInsiderScraper
scraper = OpenInsiderScraper()
data = scraper.scrape_prebuilt_screen()
print(f"Found {len(data)} trades")