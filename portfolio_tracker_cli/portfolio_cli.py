#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portfolio Tracker CLI Tool
A professional command-line tool for tracking crypto and stock investments

Usage:
    portfolio add --symbol BTCUSD --platform binance --amount 4000 --qty 0.05
    portfolio report
    portfolio list
    portfolio edit --id 1 --symbol ETHUSD --platform coinbase --amount 2000 --qty 0.1
    portfolio delete --id 1
    portfolio --help
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# Initialize Rich console for beautiful output
console = Console()

# Configuration
DATA_FILE = Path("portfolio_data.json")
CONFIG_FILE = Path("portfolio_config.json")

class PortfolioError(Exception):
    """Custom exception for portfolio operations"""
    pass

# ========= Asset Classification Helper =========
def classify_asset(symbol: str) -> str:
    """Simple classification function: Trading pairs ending with "USD" are considered crypto, others default to stock/ETF"""
    return "crypto" if symbol.upper().endswith("USD") else "stock"

# ========= Price Fetching =========
class PriceFetcher:
    """Fetch real-time prices by platform (USD denominated)"""

    BINANCE_URL = "https://api.binance.us/api/v3/ticker/price"
    OKX_URL = "https://www.okx.com/api/v5/market/ticker"
    COINBASE_URL = "https://api.coinbase.com/v2/prices/{pair}/spot"
    STOOQ_URL = "https://stooq.pl/q/l/?s={ticker}&i=d"

    @staticmethod
    def stooq(symbol: str) -> float:
        """Supports any US stocks/ETFs (e.g., QQQM, AAPL)"""
        ticker = symbol.lower()
        if "." not in ticker:
            ticker += ".us"
        url = PriceFetcher.STOOQ_URL.format(ticker=ticker)
        hdrs = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=hdrs, timeout=15)
        resp.raise_for_status()
        last_line = resp.text.strip().splitlines()[-1]
        close_px = float(last_line.split(",")[6])
        return close_px

    @staticmethod
    def binance(symbol: str) -> float:
        resp = requests.get(PriceFetcher.BINANCE_URL, params={"symbol": symbol.upper()})
        resp.raise_for_status()
        return float(resp.json()["price"])

    @staticmethod
    def okx(symbol: str) -> float:
        if "-" not in symbol:
            symbol = symbol[:3] + "-" + symbol[3:]
        resp = requests.get(PriceFetcher.OKX_URL, params={"instId": symbol.upper()})
        resp.raise_for_status()
        return float(resp.json()["data"][0]["last"])

    @staticmethod
    def coinbase(symbol: str) -> float:
        if "-" not in symbol:
            symbol = symbol[:3] + "-" + symbol[3:]
        url = PriceFetcher.COINBASE_URL.format(pair=symbol.upper())
        resp = requests.get(url)
        resp.raise_for_status()
        return float(resp.json()["data"]["amount"])

    MAPPER = {
        "binance": binance.__func__,
        "okx": okx.__func__,
        "coinbase": coinbase.__func__,
        "stock_etf": stooq.__func__,
    }

# ========= Data Management =========
class PortfolioData:
    """Portfolio data management with unique transaction IDs"""
    
    def __init__(self):
        self.data_file = DATA_FILE
        self.transactions: Dict[str, Dict] = {}
        self.load_data()
    
    def load_data(self):
        """Load data from JSON file"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.transactions = data.get('transactions', {})
            except (json.JSONDecodeError, IOError) as e:
                console.print(f"[red]Error loading data: {e}[/red]")
                self.transactions = {}
        else:
            self.transactions = {}
    
    def save_data(self):
        """Save data to JSON file"""
        try:
            data = {
                'transactions': self.transactions,
                'last_updated': dt.datetime.now().isoformat()
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise PortfolioError(f"Failed to save data: {e}")
    
    def add_transaction(self, symbol: str, platform: str, amount: float, qty: float) -> str:
        """Add a new transaction and return its ID"""
        transaction_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID
        
        transaction = {
            'id': transaction_id,
            'symbol': symbol.upper(),
            'platform': platform.lower(),
            'amount': amount,
            'qty': qty,
            'timestamp': dt.datetime.now().isoformat(),
            'asset_class': classify_asset(symbol)
        }
        
        self.transactions[transaction_id] = transaction
        self.save_data()
        return transaction_id
    
    def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get transaction by ID"""
        return self.transactions.get(transaction_id)
    
    def update_transaction(self, transaction_id: str, **kwargs) -> bool:
        """Update transaction by ID"""
        if transaction_id not in self.transactions:
            return False
        
        transaction = self.transactions[transaction_id]
        for key, value in kwargs.items():
            if key in ['symbol', 'platform', 'amount', 'qty']:
                transaction[key] = value
                if key == 'symbol':
                    transaction['asset_class'] = classify_asset(value)
        
        transaction['last_modified'] = dt.datetime.now().isoformat()
        self.save_data()
        return True
    
    def delete_transaction(self, transaction_id: str) -> bool:
        """Delete transaction by ID"""
        if transaction_id in self.transactions:
            del self.transactions[transaction_id]
            self.save_data()
            return True
        return False
    
    def get_all_transactions(self) -> List[Dict]:
        """Get all transactions as a list"""
        return list(self.transactions.values())
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert transactions to pandas DataFrame"""
        if not self.transactions:
            return pd.DataFrame(columns=['id', 'timestamp', 'symbol', 'platform', 'amount', 'qty', 'asset_class'])
        
        data = []
        for transaction in self.transactions.values():
            data.append({
                'id': transaction['id'],
                'timestamp': transaction['timestamp'],
                'symbol': transaction['symbol'],
                'platform': transaction['platform'],
                'amount': transaction['amount'],
                'qty': transaction['qty'],
                'asset_class': transaction['asset_class']
            })
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df

# ========= Report Generation =========
class PortfolioReporter:
    """Generate beautiful portfolio reports"""
    
    def __init__(self, portfolio_data: PortfolioData):
        self.portfolio_data = portfolio_data
    
    def generate_report(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Generate portfolio report data"""
        df = self.portfolio_data.to_dataframe()
        
        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # ① Calculate weighted average cost by platform × symbol
        df["cost_per_unit"] = df["amount"] / df["qty"]
        grouped = (
            df.groupby(["platform", "symbol"])
            .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
            .reset_index()
        )
        grouped["avg_cost"] = grouped["total_cost"] / grouped["total_qty"]
        
        # ② Fetch current prices and calculate PnL
        current_prices = {}
        for _, row in grouped.iterrows():
            platform, symbol = row["platform"], row["symbol"]
            fetch_fn = PriceFetcher.MAPPER[platform]
            try:
                price = fetch_fn(symbol)
                current_prices[(platform, symbol)] = price
            except Exception as e:
                console.print(f"[yellow]⚠️  Failed to fetch price for {platform} {symbol}: {e}[/yellow]")
                current_prices[(platform, symbol)] = float("nan")
        
        grouped["live_price"] = grouped.apply(
            lambda r: current_prices[(r["platform"], r["symbol"])], axis=1
        )
        grouped["market_value"] = grouped["live_price"] * grouped["total_qty"]
        grouped["cost_value"] = grouped["total_cost"]
        grouped["pnl_$"] = grouped["market_value"] - grouped["total_cost"]
        grouped["pnl_%"] = grouped["pnl_$"] / grouped["total_cost"] * 100
        
        # ③ Average cost per symbol (cross-platform)
        coin_lvl = (
            df.groupby("symbol")
            .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
            .reset_index()
        )
        coin_lvl["avg_cost_all_platform"] = coin_lvl["total_cost"] / coin_lvl["total_qty"]
        
        # ④ Asset class (Crypto vs Stock) summary returns
        grouped["asset_class"] = grouped["symbol"].apply(classify_asset)
        asset_summary = (
            grouped.groupby("asset_class")
            .agg(total_cost=("cost_value", "sum"), market_value=("market_value", "sum"))
            .reset_index()
        )
        asset_summary["pnl_$"] = asset_summary["market_value"] - asset_summary["total_cost"]
        asset_summary["pnl_%"] = asset_summary["pnl_$"] / asset_summary["total_cost"] * 100
        
        return grouped, coin_lvl, asset_summary
    
    def display_report(self):
        """Display beautiful portfolio report"""
        grouped, coin_lvl, asset_summary = self.generate_report()
        
        if grouped.empty:
            console.print(Panel("📊 No transactions found. Add some transactions first!", 
                              title="Portfolio Report", border_style="blue"))
            return
        
        # Display detailed breakdown
        console.print("\n[bold blue]📊 Portfolio Detailed Breakdown[/bold blue]")
        detail_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        detail_table.add_column("Platform", style="cyan")
        detail_table.add_column("Symbol", style="cyan")
        detail_table.add_column("Total Qty", justify="right")
        detail_table.add_column("Avg Cost", justify="right")
        detail_table.add_column("Live Price", justify="right")
        detail_table.add_column("Cost Value", justify="right")
        detail_table.add_column("Market Value", justify="right")
        detail_table.add_column("PnL $", justify="right")
        detail_table.add_column("PnL %", justify="right")
        
        for _, row in grouped.iterrows():
            pnl_color = "green" if row['pnl_$'] > 0 else "red" if row['pnl_$'] < 0 else "white"
            detail_table.add_row(
                row['platform'],
                row['symbol'],
                f"{row['total_qty']:,.6f}",
                f"${row['avg_cost']:,.2f}",
                f"${row['live_price']:,.2f}" if pd.notna(row['live_price']) else "N/A",
                f"${row['cost_value']:,.2f}",
                f"${row['market_value']:,.2f}" if pd.notna(row['market_value']) else "N/A",
                f"${row['pnl_$']:,.2f}" if pd.notna(row['pnl_$']) else "N/A",
                f"{row['pnl_%']:,.2f}%" if pd.notna(row['pnl_%']) else "N/A",
                style=pnl_color
            )
        
        console.print(detail_table)
        
        # Display symbol summary
        console.print("\n[bold blue]📈 Symbol Summary (Cross-Platform)[/bold blue]")
        symbol_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        symbol_table.add_column("Symbol", style="cyan")
        symbol_table.add_column("Total Qty", justify="right")
        symbol_table.add_column("Total Cost", justify="right")
        symbol_table.add_column("Avg Cost", justify="right")
        
        for _, row in coin_lvl.iterrows():
            symbol_table.add_row(
                row['symbol'],
                f"{row['total_qty']:,.6f}",
                f"${row['total_cost']:,.2f}",
                f"${row['avg_cost_all_platform']:,.2f}"
            )
        
        console.print(symbol_table)
        
        # Display asset class summary
        console.print("\n[bold blue]🏦 Asset Class Summary[/bold blue]")
        asset_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        asset_table.add_column("Asset Class", style="cyan")
        asset_table.add_column("Total Cost", justify="right")
        asset_table.add_column("Market Value", justify="right")
        asset_table.add_column("PnL $", justify="right")
        asset_table.add_column("PnL %", justify="right")
        
        for _, row in asset_summary.iterrows():
            pnl_color = "green" if row['pnl_$'] > 0 else "red" if row['pnl_$'] < 0 else "white"
            asset_table.add_row(
                row['asset_class'],
                f"${row['total_cost']:,.2f}",
                f"${row['market_value']:,.2f}" if pd.notna(row['market_value']) else "N/A",
                f"${row['pnl_$']:,.2f}" if pd.notna(row['pnl_$']) else "N/A",
                f"{row['pnl_%']:,.2f}%" if pd.notna(row['pnl_%']) else "N/A",
                style=pnl_color
            )
        
        console.print(asset_table)
    
    def display_transactions(self):
        """Display all transactions in a table"""
        transactions = self.portfolio_data.get_all_transactions()
        
        if not transactions:
            console.print(Panel("📋 No transactions found. Add some transactions first!", 
                              title="Transaction List", border_style="blue"))
            return
        
        console.print("\n[bold blue]📋 All Transactions[/bold blue]")
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan")
        table.add_column("Date", style="cyan")
        table.add_column("Symbol", style="cyan")
        table.add_column("Platform", style="cyan")
        table.add_column("Amount", justify="right")
        table.add_column("Quantity", justify="right")
        table.add_column("Asset Class", style="cyan")
        
        for transaction in sorted(transactions, key=lambda x: x['timestamp'], reverse=True):
            timestamp = dt.datetime.fromisoformat(transaction['timestamp']).strftime('%Y-%m-%d %H:%M')
            table.add_row(
                transaction['id'],
                timestamp,
                transaction['symbol'],
                transaction['platform'],
                f"${transaction['amount']:,.2f}",
                f"{transaction['qty']:,.6f}",
                transaction['asset_class']
            )
        
        console.print(table)

# ========= CLI Commands =========
def add_transaction(args):
    """Add a new transaction"""
    try:
        portfolio = PortfolioData()
        transaction_id = portfolio.add_transaction(
            symbol=args.symbol,
            platform=args.platform,
            amount=args.amount,
            qty=args.qty
        )
        
        console.print(f"[green]✅ Transaction added successfully![/green]")
        console.print(f"[cyan]Transaction ID: {transaction_id}[/cyan]")
        
        # Show the added transaction
        transaction = portfolio.get_transaction(transaction_id)
        if transaction:
            table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            
            table.add_row("ID", transaction['id'])
            table.add_row("Symbol", transaction['symbol'])
            table.add_row("Platform", transaction['platform'])
            table.add_row("Amount", f"${transaction['amount']:,.2f}")
            table.add_row("Quantity", f"{transaction['qty']:,.6f}")
            table.add_row("Asset Class", transaction['asset_class'])
            table.add_row("Timestamp", transaction['timestamp'])
            
            console.print(table)
    
    except Exception as e:
        console.print(f"[red]❌ Error adding transaction: {e}[/red]")
        sys.exit(1)

def list_transactions(args):
    """List all transactions"""
    try:
        portfolio = PortfolioData()
        reporter = PortfolioReporter(portfolio)
        reporter.display_transactions()
    
    except Exception as e:
        console.print(f"[red]❌ Error listing transactions: {e}[/red]")
        sys.exit(1)

def generate_report(args):
    """Generate portfolio report"""
    try:
        portfolio = PortfolioData()
        reporter = PortfolioReporter(portfolio)
        reporter.display_report()
    
    except Exception as e:
        console.print(f"[red]❌ Error generating report: {e}[/red]")
        sys.exit(1)

def edit_transaction(args):
    """Edit an existing transaction"""
    try:
        portfolio = PortfolioData()
        transaction = portfolio.get_transaction(args.id)
        
        if not transaction:
            console.print(f"[red]❌ Transaction with ID {args.id} not found[/red]")
            sys.exit(1)
        
        # Show current transaction
        console.print(f"[cyan]Current transaction {args.id}:[/cyan]")
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan")
        table.add_column("Current Value")
        
        table.add_row("Symbol", transaction['symbol'])
        table.add_row("Platform", transaction['platform'])
        table.add_row("Amount", f"${transaction['amount']:,.2f}")
        table.add_row("Quantity", f"{transaction['qty']:,.6f}")
        
        console.print(table)
        
        # Update fields
        updates = {}
        if args.symbol:
            updates['symbol'] = args.symbol
        if args.platform:
            updates['platform'] = args.platform
        if args.amount is not None:
            updates['amount'] = args.amount
        if args.qty is not None:
            updates['qty'] = args.qty
        
        if not updates:
            console.print("[yellow]⚠️  No changes specified. Use --symbol, --platform, --amount, or --qty to modify fields.[/yellow]")
            return
        
        if portfolio.update_transaction(args.id, **updates):
            console.print(f"[green]✅ Transaction {args.id} updated successfully![/green]")
        else:
            console.print(f"[red]❌ Failed to update transaction {args.id}[/red]")
            sys.exit(1)
    
    except Exception as e:
        console.print(f"[red]❌ Error editing transaction: {e}[/red]")
        sys.exit(1)

def delete_transaction(args):
    """Delete a transaction"""
    try:
        portfolio = PortfolioData()
        transaction = portfolio.get_transaction(args.id)
        
        if not transaction:
            console.print(f"[red]❌ Transaction with ID {args.id} not found[/red]")
            sys.exit(1)
        
        # Show transaction to be deleted
        console.print(f"[yellow]⚠️  About to delete transaction {args.id}:[/yellow]")
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        
        table.add_row("Symbol", transaction['symbol'])
        table.add_row("Platform", transaction['platform'])
        table.add_row("Amount", f"${transaction['amount']:,.2f}")
        table.add_row("Quantity", f"{transaction['qty']:,.6f}")
        
        console.print(table)
        
        # Confirm deletion
        if not args.force:
            response = input("\nAre you sure you want to delete this transaction? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return
        
        if portfolio.delete_transaction(args.id):
            console.print(f"[green]✅ Transaction {args.id} deleted successfully![/green]")
        else:
            console.print(f"[red]❌ Failed to delete transaction {args.id}[/red]")
            sys.exit(1)
    
    except Exception as e:
        console.print(f"[red]❌ Error deleting transaction: {e}[/red]")
        sys.exit(1)

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Portfolio Tracker CLI - Track your crypto and stock investments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  portfolio add --symbol BTCUSD --platform binance --amount 4000 --qty 0.05
  portfolio add --symbol AAPL --platform fidelity --amount 1500 --qty 10
  portfolio report
  portfolio list
  portfolio edit --id abc12345 --symbol ETHUSD --amount 2000
  portfolio delete --id abc12345
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new transaction')
    add_parser.add_argument('--symbol', required=True, help='Symbol (e.g., BTCUSD, AAPL)')
    add_parser.add_argument('--platform', required=True, 
                           choices=list(PriceFetcher.MAPPER.keys()),
                           help='Trading platform')
    add_parser.add_argument('--amount', required=True, type=float, help='Amount spent (USD)')
    add_parser.add_argument('--qty', required=True, type=float, help='Quantity purchased')
    add_parser.set_defaults(func=add_transaction)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all transactions')
    list_parser.set_defaults(func=list_transactions)
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate portfolio report')
    report_parser.set_defaults(func=generate_report)
    
    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Edit an existing transaction')
    edit_parser.add_argument('--id', required=True, help='Transaction ID')
    edit_parser.add_argument('--symbol', help='New symbol')
    edit_parser.add_argument('--platform', choices=list(PriceFetcher.MAPPER.keys()), help='New platform')
    edit_parser.add_argument('--amount', type=float, help='New amount')
    edit_parser.add_argument('--qty', type=float, help='New quantity')
    edit_parser.set_defaults(func=edit_transaction)
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a transaction')
    delete_parser.add_argument('--id', required=True, help='Transaction ID')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    delete_parser.set_defaults(func=delete_transaction)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Display welcome message
    console.print(Panel.fit(
        "[bold blue]Portfolio Tracker CLI[/bold blue]\n"
        "Track your crypto and stock investments with ease!",
        border_style="blue"
    ))
    
    # Execute command
    args.func(args)

if __name__ == "__main__":
    main() 