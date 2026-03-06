import pandas as pd
from datetime import datetime, timedelta
import structlog
from src.config import config
import logging

logger = structlog.get_logger()
logger = logging.getLogger(__name__)

class SignalFilter:
    def __init__(self):
        # Normalize required titles to lowercase for consistent matching
        self.required_titles = [t.lower() for t in config.REQUIRED_TITLES]
        
    def filter_high_conviction(self, df):
        """Apply multiple filters for high-conviction signals"""
        if df.empty:
            return df
        
        filtered = df.copy()
        
        # 1. Filter by insider title (case-insensitive, substring match)
        title_mask = filtered['title'].apply(
            lambda x: any(req in str(x).lower() for req in self.required_titles)
        )
        excluded_titles = filtered[~title_mask]
        if not excluded_titles.empty:
            for _, row in excluded_titles.iterrows():
                logger.info(
                    f"Excluded by title: {row['ticker']} - {row['insider']} ({row['title']})"
                )
        filtered = filtered[title_mask]
        
        if filtered.empty:
            logger.info("No signals match the required titles filter")
            return filtered
        
        # 2. Minimum transaction value
        value_mask = filtered['value'] >= config.MIN_TRADE_VALUE
        excluded_value = filtered[~value_mask]
        if not excluded_value.empty:
            for _, row in excluded_value.iterrows():
                logger.info(
                    f"Excluded by value: {row['ticker']} - {row['insider']} (${row['value']}) below threshold"
                )
        filtered = filtered[value_mask]
        
        if filtered.empty:
            logger.info("No signals match the minimum value filter")
            return filtered
        
        # 3. Recent trades (last 5 days)
        recent_date = datetime.now() - timedelta(days=5)
        date_mask = filtered['trade_date'] >= recent_date
        excluded_date = filtered[~date_mask]
        if not excluded_date.empty:
            for _, row in excluded_date.iterrows():
                logger.info(
                    f"Excluded by date: {row['ticker']} - {row['insider']} "
                    f"(trade_date={row['trade_date']}) older than {recent_date.date()}"
                )
        filtered = filtered[date_mask]
        
        if filtered.empty:
            logger.info("No signals match the recent trades filter")
            return filtered
        
        # 4. Identify cluster buys
        filtered = self._identify_cluster_buys(filtered)
        
        # 5. Calculate conviction score
        scores = filtered.apply(self._calculate_score, axis=1)
        filtered['conviction_score'] = scores
        
        # 6. Rank by conviction
        filtered = filtered.sort_values('conviction_score', ascending=False)
        
        logger.info(f"Filtered to {len(filtered)} high-conviction signals")
        return filtered
    
    def _identify_cluster_buys(self, df):
        """Identify stocks with multiple insider buys"""
        if df.empty:
            return df
        
        df = df.copy()
        
        # Count buys per ticker
        ticker_counts = df['ticker'].value_counts()
        cluster_tickers = ticker_counts[ticker_counts >= 2].index
        
        # Mark cluster buys
        df['is_cluster'] = df['ticker'].isin(cluster_tickers)
        df['cluster_size'] = df['ticker'].map(ticker_counts)
        
        return df
    
    def _calculate_score(self, row):
        """Calculate conviction score from 0-100"""
        try:
            score = 0
            
            # Value-based scoring
            value = float(row['value'])
            if value >= 1000000:
                score += 40
            elif value >= 100000:
                score += 30
            elif value >= 25000:
                score += 20
                
            # Title-based scoring (case-insensitive)
            title = str(row['title']).lower()
            if 'ceo' in title:
                score += 30
            elif 'cfo' in title:
                score += 25
            elif 'director' in title or 'dir' in title:
                score += 20
            
            # Cluster bonus
            is_cluster = row.get('is_cluster', False)
            if is_cluster:
                cluster_size = row.get('cluster_size', 1)
                score += min(20, int(cluster_size) * 10)
                
            # Recentness bonus
            trade_date = row['trade_date']
            if pd.notna(trade_date):
                if isinstance(trade_date, str):
                    trade_date = pd.to_datetime(trade_date)
                if hasattr(trade_date, 'tz') and trade_date.tz is not None:
                    trade_date = trade_date.tz_localize(None)
                
                days_old = (datetime.now() - trade_date).days
                recency_bonus = max(0, 10 - days_old * 2)
                score += recency_bonus
            
            return int(min(100, max(0, score)))
        except Exception as e:
            logger.warning(f"Error calculating score for row: {e}")
            return 0