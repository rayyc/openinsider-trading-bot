#src/data_collection.py
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import structlog
from src.config import config

# Configure logger
logger = structlog.get_logger()
logger = logging.getLogger(__name__)

class OpenInsiderScraper:
    def __init__(self):
        # Create a session with retries and headers
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,                # retry up to 5 times
            backoff_factor=1,       # wait 1s, 2s, 4s, etc. between retries
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def scrape_prebuilt_screen(self, screen_type="cluster"):
        """Scrape OpenInsider pre-built screens with header-based column mapping"""
        screens = {
            "cluster": "?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1",
            "ceocfo": "?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=25&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&isceo=1&iscfo=1&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"
        }

        url = config.OPENINSIDER_URL + screens.get(screen_type, screens["cluster"])

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'class': 'tinytable'})

            if not table:
                logger.error("Could not find data table")
                return pd.DataFrame()

            # ===== STEP 1: READ HEADERS TO MAP COLUMNS =====
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.text.strip().replace('\xa0', ' ') for th in header_row.find_all(['th', 'td'])]
                safe_headers = [h.replace('Δ', 'Change') for h in headers]
                logger.info(f"Detected {len(headers)} columns: {safe_headers}")

            col_map = {header: idx for idx, header in enumerate(headers)}

            # ===== STEP 2: PARSE DATA ROWS =====
            data = []
            rows = table.find_all('tr')[1:]  # Skip header row

            for row in rows:
                cols = row.find_all('td')
                if len(cols) < len(headers):
                    continue

                try:
                    trade_type = cols[col_map.get('Trade Type', 7)].text.strip()
                    if 'P' not in trade_type.upper():
                        continue

                    filing_date = cols[col_map.get('Filing Date', 1)].text.strip()
                    trade_date = cols[col_map.get('Trade Date', 2)].text.strip()
                    ticker = cols[col_map.get('Ticker', 3)].text.strip()

                    price_str = cols[col_map.get('Price', 8)].text.strip().replace('$', '').replace(',', '')
                    qty_str = cols[col_map.get('Qty', 9)].text.strip().replace(',', '').replace('+', '')
                    value_str = cols[col_map.get('Value', 12)].text.strip().replace('$', '').replace(',', '')

                    if not all([price_str, qty_str, value_str, ticker]):
                        continue

                    price = float(price_str)
                    qty = int(qty_str)
                    value = float(value_str)

                    if qty <= 0 or value <= 0:
                        continue
                    if value < config.MIN_TRADE_VALUE:
                        logger.debug(f"Skipping {ticker}: value ${value} below minimum ${config.MIN_TRADE_VALUE}")
                        continue

                    record = {
                        'ticker': ticker,
                        'company': cols[col_map.get('Company Name', 4)].text.strip(),
                        'insider': cols[col_map.get('Insider Name', 5)].text.strip(),
                        'title': cols[col_map.get('Title', 6)].text.strip(),
                        'trade_date': trade_date,
                        'trade_type': trade_type,
                        'price': price,
                        'qty': qty,
                        'value': value,
                        'filing_date': filing_date,
                        '1d_change': cols[col_map.get('1d', 13)].text.strip() if col_map.get('1d') else '',
                        '1w_change': cols[col_map.get('1w', 14)].text.strip() if col_map.get('1w') else '',
                    }

                    data.append(record)
                    logger.debug(f"Parsed purchase: {ticker} - {qty} shares @ ${price} (Value: ${value})")

                except (ValueError, IndexError, KeyError) as e:
                    ticker_info = cols[col_map.get('Ticker', 3)].text.strip() if len(cols) > 3 else "Unknown"
                    logger.debug(f"Error parsing row for {ticker_info}: {e}")
                    continue

            # ===== STEP 5: CREATE DATAFRAME AND PROCESS =====
            df = pd.DataFrame(data)

            if not df.empty:
                try:
                    df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
                    df['filing_date'] = pd.to_datetime(df['filing_date'], errors='coerce')

                    week_ago = datetime.now() - timedelta(days=7)
                    initial_count = len(df)
                    df = df[df['trade_date'] >= week_ago]

                    if len(df) < initial_count:
                        logger.info(f"Filtered out {initial_count - len(df)} older trades (before {week_ago.date()})")

                    logger.info(f"Successfully scraped {len(df)} valid insider purchases")
                    if len(df) > 0:
                        logger.info(f"   Example: {df.iloc[0]['ticker']} - ${df.iloc[0]['value']:,.0f} by {df.iloc[0]['insider']}")

                except Exception as e:
                    logger.error(f"Error processing dates in DataFrame: {e}")
                    return pd.DataFrame()
            else:
                logger.info("No purchase transactions found matching criteria")

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while scraping OpenInsider: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in scraper: {e}")
            return pd.DataFrame()