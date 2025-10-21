# Phase 2 Implementation: Wallet SDK Integration

## Overview

Phase 2 adds real trade execution capabilities to Polly using the py-clob-client wallet SDK. Users can now execute actual trades on Polymarket while maintaining the existing paper trading functionality.

## Implementation Date

October 21, 2025

## Key Features Implemented

### 1. Dual Trading Modes
- **Paper Mode (Default)**: Simulated trades with no real money
- **Real Mode**: Actual trade execution on Polymarket via Polygon network
- Global configuration toggle in `~/.polly/config.yml`

### 2. Trading Service
**File**: `polly/services/trading.py`
- Wraps py-clob-client for authenticated trading
- Direct EOA (Externally Owned Account) authentication - simplest method for CLI
- Market buy/sell order execution
- Balance checking functionality
- Error handling and validation

### 3. Manual Trade Commands
**Files**: `polly/commands/trade.py`

#### `/trade <market_num> <outcome> [amount]`
- Manually execute trades in real mode
- Validates market, outcome, and balance
- Confirms with user before execution
- Records trade to database

#### `/close <trade_id>`
- Close active positions (placeholder for future enhancement)
- Requires token_id storage enhancement

### 4. Enhanced Research Flow
**File**: `polly/commands/research.py`
- Supports both paper and real trade execution
- Clear mode indicators (PAPER vs REAL MONEY)
- Double confirmation for real trades ("confirm" required)
- Automatic execution via py-clob-client
- Records execution details (price, order ID, shares)

### 5. Safety & Validation
**File**: `polly/services/validators.py`
- Trade size validation against balance and risk limits
- Token ID validation
- USDC balance checking
- Market activity validation
- Comprehensive error messages

### 6. Database Schema Updates
**File**: `polly/storage/trades.py`
- Added `trade_mode` column: "paper" or "real"
- Added `order_id` column: Polymarket order ID for real trades
- Backward compatible with existing databases (automatic migration)

### 7. Configuration Updates
**Files**: `polly/config.py`, `polly/cli.py`
- Renamed `PaperTradingConfig` → `TradingConfig`
- Added trading mode setting
- Added Polygon chain configuration
- Backward compatible with old `paper_trading` config key

### 8. Portfolio Enhancements
**File**: `polly/commands/portfolio.py`
- Displays current trading mode (PAPER/REAL badge)
- Shows on-chain USDC balances in real mode
- Separates tracked cash vs actual balances

### 9. Updated Models
**File**: `polly/models.py`
- Trade model includes `trade_mode` and `order_id`
- Supports both paper and real trade records

## Technical Implementation Details

### Authentication Method
- **Direct EOA Trading**: Uses wallet private key directly without proxy contracts
- Simplest method for CLI applications
- No signature_type or funder address needed

### Order Execution Strategy
- **Market Orders via Limit Orders**: Simulates market orders using limit orders with slippage tolerance
- Buy orders: 2% above best ask, capped at 0.99
- Sell orders: 2% below best bid, floored at 0.01
- Good-Till-Cancelled (GTC) orders

### Safety Features
1. **Mode Indicators**: Clear visual indicators showing paper vs real mode
2. **Confirmation Prompts**: 
   - Initial yes/no for trade acceptance
   - "confirm" required for real money trades
3. **Balance Checks**: Validate sufficient USDC before execution
4. **Risk Limits**: Respect `max_risk_per_trade_pct` from config
5. **Error Handling**: Graceful handling with clear error messages

## Configuration

### Environment Variables
```bash
XAI_API_KEY=your_xai_api_key_here                    # Required
POLYGON_PRIVATE_KEY=your_polygon_private_key_here    # Required for real trading
```

### Config File (`~/.polly/config.yml`)
```yaml
trading:
  mode: paper                     # "paper" or "real"
  default_stake: 100
  starting_cash: 10000
  chain_id: 137                   # Polygon
  clob_host: "https://clob.polymarket.com"
```

## New Commands

| Command | Description | Mode |
|---------|-------------|------|
| `/trade <market> <outcome> [amount]` | Execute manual trade | Real only |
| `/close <trade_id>` | Close active position | Real only |
| `/portfolio` | View portfolio (now shows mode) | Both |
| `/research <poll_id>` | Research + trade (mode-aware) | Both |

## Files Modified

### Core Services
- `polly/services/trading.py` (NEW)
- `polly/services/validators.py` (NEW)
- `polly/services/polymarket.py`

### Commands
- `polly/commands/trade.py` (NEW)
- `polly/commands/research.py` (MODIFIED)
- `polly/commands/portfolio.py` (MODIFIED)
- `polly/commands/help.py` (MODIFIED)

### Configuration & Models
- `polly/config.py` (MODIFIED)
- `polly/models.py` (MODIFIED)
- `polly/storage/trades.py` (MODIFIED)

### CLI Integration
- `polly/cli.py` (MODIFIED)

### Documentation
- `README.md` (MODIFIED)
- `QUICKSTART.md` (MODIFIED)
- `PHASE2_IMPLEMENTATION.md` (NEW)

## Testing Checklist

- [x] Paper mode continues to work (no regressions)
- [ ] Real mode initializes with valid private key
- [ ] Real mode shows warning without private key
- [ ] Trade execution records to database correctly
- [ ] Mode indicator displays correctly in portfolio
- [ ] Double confirmation works for real trades
- [ ] Balance checking validates USDC availability
- [ ] Error handling displays clear messages
- [ ] Config migration from `paper_trading` to `trading` works
- [ ] Database migration adds new columns correctly

## Security Considerations

1. **Private Key Storage**: Only in `.env` file, never in code or config
2. **Double Confirmation**: Required for all real trades
3. **Balance Validation**: Pre-trade balance checks
4. **Error Handling**: No exposure of sensitive data in error messages
5. **Mode Indicators**: Clear visual distinction between paper and real modes

## Known Limitations

1. **Position Closing**: `/close` command requires token_id storage enhancement
2. **Order Status**: No real-time order status monitoring
3. **Partial Fills**: No handling of partial order fills
4. **Slippage**: Fixed 2% slippage tolerance (not configurable)
5. **Order Types**: Only market orders (via limit orders), no advanced order types

## Future Enhancements

1. Store `token_id` with trades for proper position closing
2. Real-time order status monitoring
3. Configurable slippage tolerance
4. Advanced order types (stop-loss, take-profit)
5. Multi-wallet support
6. Position management dashboard
7. Trade history export
8. Performance analytics for real vs paper trades

## Migration Guide

### For Existing Users

1. **No Action Required**: Paper trading continues to work by default
2. **Config Migration**: Old `paper_trading` key still supported, automatically migrated to `trading`
3. **Database Migration**: New columns added automatically on first run

### To Enable Real Trading

1. Add `POLYGON_PRIVATE_KEY` to `.env`
2. Edit `~/.polly/config.yml`:
   ```yaml
   trading:
     mode: real
   ```
3. Ensure USDC balance on Polygon network
4. Restart Polly

## Dependencies

No new dependencies required. Uses existing:
- `py-clob-client>=0.20.0`
- `requests>=2.32.0`

## Support

For issues or questions:
1. Check documentation in `README.md` and `QUICKSTART.md`
2. Review configuration in `~/.polly/config.yml`
3. Verify environment variables in `.env`
4. Check logs for error messages

## Acknowledgments

- Polymarket py-clob-client team for excellent SDK
- Phase 1 foundation for research and paper trading
- Direct EOA authentication for CLI simplicity

