# Polymarket Trading Setup Guide - FINAL

## ✅ Confirmed Working Configuration

### Required Setup:

1. **Proxy Wallet Mode** (NOT Direct EOA)
   - `signature_type: 2`
   - `polymarket_proxy_address: "0x72dB4a2F113c73Bbf270e92D7ece446710B658b9"`

2. **Funds Location**
   - **CRITICAL:** Funds MUST be in the PROXY wallet, not your EOA wallet
   - Transfer USDC/USDC.e TO: `0x72dB4a2F113c73Bbf270e92D7ece446710B658b9`
   - Your EOA (`0xE471...`) is just for signing, not holding trading funds

3. **Required Approvals** (one-time setup)
   - USDC.e approval for CTF Exchange (for buying)
   - USDC approval for CTF Exchange (for buying)  
   - CTF tokens approval for CTF Exchange (for selling)
   - All handled automatically on first trade!

## 📋 Complete Setup Steps

### Step 1: Create Polymarket Account
1. Go to https://polymarket.com
2. Connect MetaMask with your wallet
3. **Deposit funds** via their interface (this creates your proxy wallet)
4. **Execute one trade** on the website (initializes your account)
5. Note your proxy address from account settings or transactions

### Step 2: Configure Polly
Add to `~/.polly/config.yml`:
```yaml
trading:
  mode: real
  signature_type: 2
  polymarket_proxy_address: "YOUR_PROXY_ADDRESS"
```

### Step 3: Fund Your Proxy Wallet
- Send USDC or USDC.e to your proxy address
- This is where Polymarket pulls trading funds from

### Step 4: Trade!
```bash
polly> /trade 1 Yes
# Enter amount
# Confirm
```

First trade will auto-approve all necessary contracts (~$0.03 in gas fees).

## 🔑 Key Insights

### Why Direct EOA Doesn't Work:
- Direct EOA mode (no signature_type, no proxy) is **READ-ONLY**
- Can fetch markets, orderbooks, balances ✅
- **Cannot post orders** ❌

### Why Proxy Mode is Required:
- Polymarket uses a proxy wallet system for trading
- Your funds live in the proxy contract
- Your EOA signs transactions but doesn't hold trading funds
- This is how ALL Polymarket web users trade

### Wallet Architecture:
```
Your EOA Wallet (0xE471...)
├── Holds: MATIC (for gas), maybe some USDC
├── Purpose: Sign transactions
└── Controls → Your Proxy Wallet (0x72dB...)
                ├── Holds: Trading USDC/USDC.e ($48)
                ├── Purpose: Execute trades
                └── Managed by: Polymarket smart contracts
```

## 💰 Balance Display

When in proxy mode, `/portfolio` shows:
- **Proxy wallet balance**: $48.00 USDC.e (your trading funds)
- This is what's available for trading

## ⚡ Trading Flow

### Opening Position:
1. Command: `/trade 1 Yes`
2. Shows proxy wallet balance
3. Enter stake amount
4. Polymarket debits from PROXY wallet
5. Position created

### Closing Position:
1. Command: `/close 1`
2. Shows current P&L from live API
3. Confirm close
4. Polymarket credits back to PROXY wallet
5. Position closed

## 🎯 Current Status

- ✅ Configuration: Proxy mode enabled
- ✅ Proxy address: `0x72dB4a2F113c73Bbf270e92D7ece446710B658b9`
- ✅ Funds: $48 USDC.e in proxy wallet
- ✅ Approvals: Auto-handled on first trade
- ✅ Ready to trade!

## 🚀 You're Ready!

Restart Polly and try trading:
```bash
python -m polly
polly> /trade 1 Yes
```

Everything should work now! The proxy wallet has your funds and all approvals will be automatic.

