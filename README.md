# Portfolio Tracker CLI

A professional command-line tool for tracking your cryptocurrency and stock investments across multiple platforms with beautiful, real-time reporting.

![Portfolio Tracker CLI](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![PyPI](https://img.shields.io/badge/PyPI-portfolio--tracker--cli-blue.svg)

## ✨ Features

- **📊 Real-time Portfolio Tracking**: Monitor your investments with live price data
- **🆔 Unique Transaction IDs**: Each transaction gets a unique identifier for easy management
- **💼 Multi-Platform Support**: Track investments across Binance, OKX, Coinbase, and Fidelity
- **📈 Beautiful Reports**: Rich, color-coded tables showing detailed portfolio analysis
- **🔄 Full CRUD Operations**: Add, view, edit, and delete transactions
- **🎨 Professional CLI**: Beautiful terminal output with Rich library
- **📱 Cross-Platform**: Works on macOS, Linux, and Windows

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI
pip install portfolio-tracker-cli

# Or install from source
git clone https://github.com/yourusername/portfolio-tracker-cli.git
cd portfolio-tracker-cli
pip install -e .
```

### Basic Usage

```bash
# Add a crypto transaction
portfolio add --symbol BTCUSD --platform binance --amount 4000 --qty 0.05

# Add a stock transaction
portfolio add --symbol AAPL --platform fidelity --amount 1500 --qty 10

# View your portfolio report
portfolio report

# List all transactions
portfolio list

# Edit a transaction
portfolio edit --id abc12345 --symbol ETHUSD --amount 2000

# Delete a transaction
portfolio delete --id abc12345
```

## 📋 Commands

### `add` - Add New Transaction

Add a new investment transaction to your portfolio.

```bash
portfolio add --symbol <SYMBOL> --platform <PLATFORM> --amount <AMOUNT> --qty <QUANTITY>
```

**Arguments:**
- `--symbol`: Investment symbol (e.g., BTCUSD, ETHUSD, AAPL, QQQM)
- `--platform`: Trading platform (binance, okx, coinbase, stock_etf)
- `--amount`: Amount spent in USD
- `--qty`: Quantity purchased

**Examples:**
```bash
# Buy Bitcoin on Binance
portfolio add --symbol BTCUSD --platform binance --amount 4000 --qty 0.05

# Buy Apple stock on Fidelity
portfolio add --symbol AAPL --platform fidelity --amount 1500 --qty 10

# Buy Ethereum on Coinbase
portfolio add --symbol ETHUSD --platform coinbase --amount 2000 --qty 0.1
```

### `report` - Generate Portfolio Report

Generate a comprehensive portfolio report with real-time prices and P&L calculations.

```bash
portfolio report
```

**Output includes:**
- 📊 Detailed breakdown by platform and symbol
- 📈 Symbol summary (cross-platform averages)
- 🏦 Asset class summary (crypto vs stocks)
- 💰 Real-time profit/loss calculations
- 🎨 Color-coded performance indicators

### `list` - List All Transactions

Display all transactions in a beautiful table format.

```bash
portfolio list
```

**Shows:**
- Transaction ID
- Date and time
- Symbol and platform
- Amount and quantity
- Asset class

### `edit` - Edit Transaction

Modify an existing transaction by its ID.

```bash
portfolio edit --id <TRANSACTION_ID> [--symbol <NEW_SYMBOL>] [--platform <NEW_PLATFORM>] [--amount <NEW_AMOUNT>] [--qty <NEW_QUANTITY>]
```

**Arguments:**
- `--id`: Transaction ID (required)
- `--symbol`: New symbol (optional)
- `--platform`: New platform (optional)
- `--amount`: New amount (optional)
- `--qty`: New quantity (optional)

**Example:**
```bash
# Change the amount of transaction abc12345
portfolio edit --id abc12345 --amount 2500

# Change symbol and platform
portfolio edit --id abc12345 --symbol ETHUSD --platform coinbase
```

### `delete` - Delete Transaction

Remove a transaction from your portfolio.

```bash
portfolio delete --id <TRANSACTION_ID> [--force]
```

**Arguments:**
- `--id`: Transaction ID (required)
- `--force`: Skip confirmation prompt (optional)

**Example:**
```bash
# Delete with confirmation
portfolio delete --id abc12345

# Delete without confirmation
portfolio delete --id abc12345 --force
```

## 🏦 Supported Platforms

| Platform | Type | Symbols | Description |
|----------|------|---------|-------------|
| **Binance** | Crypto | BTCUSD, ETHUSD, BNBUSD, etc. | Binance.US API |
| **OKX** | Crypto | BTC-USD, ETH-USD, etc. | OKX Exchange API |
| **Coinbase** | Crypto | BTC-USD, ETH-USD, etc. | Coinbase API |
| **Stock_ETF** | Stocks/ETFs | AAPL, QQQM, SPY, etc. | Via Stooq data |

## 📊 Data Storage

All portfolio data is stored locally in `portfolio_data.json` in your current directory. The file contains:

- Unique transaction IDs
- Transaction details (symbol, platform, amount, quantity)
- Timestamps
- Asset classification

**Example data structure:**
```json
{
  "transactions": {
    "abc12345": {
      "id": "abc12345",
      "symbol": "BTCUSD",
      "platform": "binance",
      "amount": 4000.0,
      "qty": 0.05,
      "timestamp": "2024-01-15T10:30:00",
      "asset_class": "crypto"
    }
  },
  "last_updated": "2024-01-15T10:30:00"
}
```

## 🎨 Beautiful Output

The CLI uses the Rich library to provide beautiful, color-coded output:

- **Green**: Positive P&L
- **Red**: Negative P&L
- **Cyan**: Headers and labels
- **Magenta**: Table headers
- **Blue**: Information panels

## 🔧 Configuration

The tool automatically creates necessary files in your current directory:

- `portfolio_data.json`: Your portfolio data
- `portfolio_config.json`: Configuration settings (future use)

## 🚀 Publishing to PyPI

To publish this tool to PyPI:

1. **Update setup_cli.py**:
   - Change author information
   - Update GitHub repository URL
   - Modify package name if needed

2. **Build and upload**:
   ```bash
   python setup_cli.py sdist bdist_wheel
   twine upload dist/*
   ```

3. **Install globally**:
   ```bash
   pip install portfolio-tracker-cli
   ```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- [Pandas](https://pandas.pydata.org/) for data manipulation
- [Requests](https://requests.readthedocs.io/) for API calls

## 📞 Support

If you encounter any issues or have questions:

1. Check the [GitHub Issues](https://github.com/yourusername/portfolio-tracker-cli/issues)
2. Create a new issue with detailed information
3. Include your operating system and Python version

---

**Happy Investing! 📈💰** 