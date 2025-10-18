# Polymarket Python CLOB Client Guide

## Overview

The Polymarket Py CLOB Client allows you to interact with Polymarket's Central Limit Order Book (CLOB) to fetch market data, place orders, and manage trading activities. For Phase 1, we'll focus on **read-only operations** to fetch market data.

## Installation

```bash
pip install py-clob-client
```

## Dependencies

```
eth-account==0.13.0
eth-utils==4.1.1
poly_eip712_structs==0.0.1
py_order_utils==0.3.2
requests==2.32.3
websockets==12.0
```

## Client Initialization (Read-Only Mode)

For Phase 1 (paper trading only), we don't need a private key. We can use the client in read-only mode:

```python
from py_clob_client.client import ClobClient

# Read-only mode (no private key needed)
host = "https://clob.polymarket.com"
client = ClobClient(host)
```

## Fetching Market Data

### Get All Markets

```python
# Fetch all available markets
markets = client.get_markets()

for market in markets:
    print(f"Market: {market['question']}")
    print(f"  Tokens: {market['tokens']}")
    print(f"  Active: {market['active']}")
    print(f"  Closed: {market['closed']}")
```

### Market Data Structure

Each market object contains:

```python
{
    "condition_id": str,          # Unique market identifier
    "question": str,              # The market question
    "description": str,           # Detailed description
    "tokens": [                   # List of outcome tokens
        {
            "token_id": str,
            "outcome": str,       # e.g., "Yes", "No"
            "price": float,       # Current price (0-1)
            "winner": bool
        }
    ],
    "end_date_iso": str,          # Resolution date
    "active": bool,               # Market is active
    "closed": bool,               # Market is closed
    "volume": float,              # 24h volume
    "liquidity": float,           # Available liquidity
    "category": str,              # Market category
    "tags": [str]                 # Market tags
}
```

## Filtering Markets for Phase 1

### Filter: Top 20 Liquid Non-Sports Markets

```python
def get_top_liquid_markets(client, exclude_sports=True, top_n=20):
    """
    Fetch top liquid markets excluding sports.
    
    Args:
        client: ClobClient instance
        exclude_sports: If True, exclude sports markets
        top_n: Number of markets to return
        
    Returns:
        List of market dictionaries sorted by liquidity
    """
    # Fetch all markets
    all_markets = client.get_markets()
    
    # Filter out closed markets
    active_markets = [m for m in all_markets if m.get('active', False) and not m.get('closed', False)]
    
    # Exclude sports if requested
    if exclude_sports:
        sports_tags = ['sports', 'esports', 'nfl', 'nba', 'mlb', 'nhl', 'soccer', 'football']
        active_markets = [
            m for m in active_markets 
            if not any(tag.lower() in sports_tags for tag in m.get('tags', []))
            and 'sport' not in m.get('category', '').lower()
        ]
    
    # Calculate liquidity score (open_interest + volume)
    for market in active_markets:
        market['liquidity_score'] = (
            market.get('liquidity', 0) * 0.7 + 
            market.get('volume', 0) * 0.3
        )
    
    # Sort by liquidity score
    sorted_markets = sorted(
        active_markets, 
        key=lambda m: m['liquidity_score'], 
        reverse=True
    )
    
    return sorted_markets[:top_n]
```

### Example Usage

```python
from py_clob_client.client import ClobClient

# Initialize client
client = ClobClient("https://clob.polymarket.com")

# Get top 20 non-sports markets
top_markets = get_top_liquid_markets(client, exclude_sports=True, top_n=20)

print(f"Found {len(top_markets)} markets\n")

for i, market in enumerate(top_markets, 1):
    print(f"{i}. {market['question']}")
    print(f"   Liquidity: ${market['liquidity']:,.0f}")
    print(f"   Volume (24h): ${market['volume']:,.0f}")
    print(f"   Category: {market.get('category', 'N/A')}")
    
    # Show outcome prices
    for token in market.get('tokens', []):
        print(f"   {token['outcome']}: {token['price']:.2f}")
    
    print()
```

## Getting Market Details

### Fetch Specific Market

```python
def get_market_by_id(client, condition_id):
    """
    Get detailed information for a specific market.
    
    Args:
        client: ClobClient instance
        condition_id: Market condition ID
        
    Returns:
        Market dictionary
    """
    markets = client.get_markets()
    market = next((m for m in markets if m['condition_id'] == condition_id), None)
    return market
```

### Get Current Odds

```python
def get_market_odds(market):
    """
    Extract current odds from a market.
    
    Args:
        market: Market dictionary
        
    Returns:
        Dictionary mapping outcome to current price
    """
    odds = {}
    for token in market.get('tokens', []):
        odds[token['outcome']] = token['price']
    return odds
```

## Market Metadata

### Calculate Time Remaining

```python
from datetime import datetime

def get_time_to_resolution(market):
    """
    Calculate time remaining until market resolution.
    
    Args:
        market: Market dictionary
        
    Returns:
        Timedelta object
    """
    end_date = datetime.fromisoformat(market['end_date_iso'].replace('Z', '+00:00'))
    now = datetime.now(end_date.tzinfo)
    return end_date - now
```

### Display Market Summary

```python
def display_market_summary(market):
    """
    Display a formatted summary of a market.
    
    Args:
        market: Market dictionary
    """
    print(f"Question: {market['question']}")
    print(f"Category: {market.get('category', 'N/A')}")
    print(f"Description: {market.get('description', 'N/A')[:100]}...")
    
    time_left = get_time_to_resolution(market)
    print(f"Resolves in: {time_left.days} days")
    
    print(f"\nCurrent Odds:")
    for token in market.get('tokens', []):
        print(f"  {token['outcome']}: {token['price']:.3f} ({token['price']*100:.1f}%)")
    
    print(f"\nLiquidity: ${market.get('liquidity', 0):,.0f}")
    print(f"Volume (24h): ${market.get('volume', 0):,.0f}")
```

## Complete Example: Fetch and Display Markets

```python
from py_clob_client.client import ClobClient
from datetime import datetime

class PolymarketDataFetcher:
    def __init__(self):
        self.client = ClobClient("https://clob.polymarket.com")
    
    def get_top_markets(self, exclude_sports=True, top_n=20):
        """Fetch top liquid non-sports markets"""
        all_markets = self.client.get_markets()
        
        # Filter active markets
        active_markets = [
            m for m in all_markets 
            if m.get('active', False) and not m.get('closed', False)
        ]
        
        # Exclude sports
        if exclude_sports:
            sports_keywords = ['sports', 'esports', 'nfl', 'nba', 'mlb', 'nhl', 'soccer']
            active_markets = [
                m for m in active_markets
                if not any(
                    keyword in m.get('category', '').lower() or
                    keyword in ' '.join(m.get('tags', [])).lower()
                    for keyword in sports_keywords
                )
            ]
        
        # Calculate liquidity score
        for market in active_markets:
            market['liquidity_score'] = (
                market.get('liquidity', 0) * 0.7 + 
                market.get('volume', 0) * 0.3
            )
        
        # Sort and return top N
        return sorted(
            active_markets,
            key=lambda m: m['liquidity_score'],
            reverse=True
        )[:top_n]
    
    def format_market_for_display(self, market):
        """Format market data for TUI display"""
        # Calculate time remaining
        end_date = datetime.fromisoformat(
            market['end_date_iso'].replace('Z', '+00:00')
        )
        now = datetime.now(end_date.tzinfo)
        time_left = end_date - now
        
        # Extract odds
        odds = {}
        for token in market.get('tokens', []):
            odds[token['outcome']] = token['price']
        
        return {
            'id': market['condition_id'],
            'question': market['question'],
            'description': market.get('description', ''),
            'category': market.get('category', 'N/A'),
            'odds': odds,
            'liquidity': market.get('liquidity', 0),
            'volume_24h': market.get('volume', 0),
            'days_left': time_left.days,
            'end_date': end_date,
            'tokens': market.get('tokens', [])
        }


# Usage
if __name__ == "__main__":
    fetcher = PolymarketDataFetcher()
    
    print("Fetching top 20 liquid non-sports markets...\n")
    markets = fetcher.get_top_markets(exclude_sports=True, top_n=20)
    
    for i, market in enumerate(markets, 1):
        formatted = fetcher.format_market_for_display(market)
        
        print(f"{i}. {formatted['question']}")
        print(f"   Category: {formatted['category']}")
        print(f"   Days left: {formatted['days_left']}")
        print(f"   Liquidity: ${formatted['liquidity']:,.0f}")
        
        # Show odds
        for outcome, price in formatted['odds'].items():
            print(f"   {outcome}: {price:.3f} ({price*100:.1f}%)")
        
        print()
```

## Price History (Optional)

```python
def get_price_history(client, token_id):
    """
    Fetch historical price data for a token.
    
    Args:
        client: ClobClient instance
        token_id: Token ID
        
    Returns:
        List of price points with timestamps
    """
    try:
        history = client.get_price_history(token_id)
        return history
    except Exception as e:
        print(f"Error fetching price history: {e}")
        return []
```

## Error Handling

```python
def safe_fetch_markets(client, max_retries=3):
    """
    Fetch markets with retry logic.
    
    Args:
        client: ClobClient instance
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of markets or empty list on failure
    """
    import time
    
    for attempt in range(max_retries):
        try:
            markets = client.get_markets()
            return markets
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print("Max retries reached. Returning empty list.")
                return []
```

## Phase 1 Integration Notes

For Phase 1 paper trading:

1. **No Authentication Required** - Read-only mode doesn't need private keys
2. **Focus on Data Fetching** - Only use `get_markets()` and related methods
3. **No Order Placement** - Skip all `create_order()` and `post_order()` functions
4. **Cache Market Data** - Store fetched markets to reduce API calls

## Data Refresh Strategy

```python
import time
from datetime import datetime, timedelta

class MarketDataCache:
    def __init__(self, client, cache_duration_minutes=5):
        self.client = client
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.last_fetch = None
        self.cached_markets = []
    
    def get_markets(self, force_refresh=False):
        """Get markets with caching"""
        now = datetime.now()
        
        # Check if cache is still valid
        if (not force_refresh and 
            self.last_fetch and 
            now - self.last_fetch < self.cache_duration):
            return self.cached_markets
        
        # Fetch fresh data
        try:
            self.cached_markets = self.client.get_markets()
            self.last_fetch = now
            return self.cached_markets
        except Exception as e:
            print(f"Error fetching markets: {e}")
            # Return cached data if available
            return self.cached_markets
```

## Best Practices

1. **Use Read-Only Mode** - No private key needed for Phase 1
2. **Cache Market Data** - Reduce API calls with smart caching
3. **Filter Efficiently** - Apply sports filter and liquidity sort
4. **Handle Errors** - Implement retry logic for network issues
5. **Rate Limiting** - Be mindful of API rate limits

## Resources

- [Polymarket CLOB Client GitHub](https://github.com/polymarket/py-clob-client)
- [Polymarket Documentation](https://docs.polymarket.com/)
- [Polymarket API Docs](https://docs.polymarket.com/developers)

