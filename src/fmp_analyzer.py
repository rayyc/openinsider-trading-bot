#src/fmp_analyzer.py
import requests
import logging
from src.config import config

logger = logging.getLogger(__name__)

class FMPAnalyzer:
    """Financial Modeling Prep API integration for enhanced fundamental data"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or config.FMP_API_KEY
        self.base_url = "https://financialmodelingprep.com/api/v3"
        
    def get_key_metrics(self, ticker):
        """Get comprehensive fundamental metrics"""
        try:
            url = f"{self.base_url}/key-metrics/{ticker}?apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
                
            latest = data[0]
            
            return {
                'pe_ratio': latest.get('peRatio'),
                'price_to_book': latest.get('pbRatio'),
                'debt_to_equity': latest.get('debtToEquity'),
                'current_ratio': latest.get('currentRatio'),
                'roe': latest.get('roe'),
                'revenue_per_share': latest.get('revenuePerShare'),
                'earnings_per_share': latest.get('netIncomePerShare'),
                'market_cap': latest.get('marketCap')
            }
        except Exception as e:
            logger.warning(f"FMP key metrics failed for {ticker}: {e}")
            return None
    
    def get_financial_ratios(self, ticker):
        """Get profitability and efficiency ratios"""
        try:
            url = f"{self.base_url}/ratios/{ticker}?apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
                
            latest = data[0]
            
            return {
                'profit_margin': latest.get('netProfitMargin'),
                'operating_margin': latest.get('operatingProfitMargin'),
                'gross_margin': latest.get('grossProfitMargin'),
                'return_on_equity': latest.get('returnOnEquity'),
                'return_on_assets': latest.get('returnOnAssets'),
                'asset_turnover': latest.get('assetTurnover')
            }
        except Exception as e:
            logger.warning(f"FMP ratios failed for {ticker}: {e}")
            return None
    
    def get_growth_metrics(self, ticker):
        """Get revenue and earnings growth"""
        try:
            url = f"{self.base_url}/financial-growth/{ticker}?apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
                
            latest = data[0]
            
            return {
                'revenue_growth': latest.get('revenueGrowth'),
                'net_income_growth': latest.get('netIncomeGrowth'),
                'eps_growth': latest.get('epsgrowth'),
                'operating_income_growth': latest.get('operatingIncomeGrowth')
            }
        except Exception as e:
            logger.warning(f"FMP growth metrics failed for {ticker}: {e}")
            return None