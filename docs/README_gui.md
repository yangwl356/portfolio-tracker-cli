# Portfolio Tracker for macOS

A simple GUI application to track your cryptocurrency and stock investments across different platforms.

## Features

- Add transactions with symbol, platform, amount, and quantity
- Real-time price fetching from multiple platforms:
  - Binance (crypto)
  - OKX (crypto)
  - Coinbase (crypto)
  - Fidelity/Stooq (stocks/ETFs)
- Automatic profit/loss calculation
- Portfolio summary by asset class
- Clean, native macOS interface

## Quick Start

### Option 1: Run as Python Script (Simplest)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
python portfolio_gui.py
```

### Option 2: Create Standalone macOS App

1. Install py2app:
```bash
pip install py2app
```

2. Build the app:
```bash
python setup.py py2app
```

3. The app will be created in `dist/Portfolio Tracker.app`

4. Double-click to run, or drag to Applications folder

## Usage

1. **Add a Transaction:**
   - Enter the symbol (e.g., BTCUSD, ETHUSD, AAPL)
   - Select the platform (binance, okx, coinbase, fidelity)
   - Enter the amount spent in USD
   - Enter the quantity purchased
   - Click "Add Transaction"

2. **View Portfolio:**
   - The report automatically updates when you add transactions
   - Click "Refresh Report" to get latest prices
   - View detailed breakdown by platform and symbol
   - See overall portfolio performance by asset class

## Data Storage

All transaction data is stored in `transactions.csv` in the same directory as the app.

## Supported Platforms

- **Crypto:** Binance, OKX, Coinbase
- **Stocks/ETFs:** Fidelity (via Stooq data)

## Example Transactions

- Buy 0.05 BTC for $4000 on Binance: Symbol=`BTCUSD`, Platform=`binance`, Amount=`4000`, Quantity=`0.05`
- Buy 10 shares of AAPL for $1500: Symbol=`AAPL`, Platform=`fidelity`, Amount=`1500`, Quantity=`10`

## Troubleshooting

- If price fetching fails, check your internet connection
- Make sure to use correct symbol formats (e.g., BTCUSD not BTC-USD for Binance)
- The app will show "NaN" for prices that can't be fetched 