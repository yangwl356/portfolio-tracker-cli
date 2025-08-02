#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portfolio Tracker GUI App for macOS
A beautiful GUI interface for tracking crypto and stock investments
"""
import csv
import datetime as dt
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, scrolledtext
import threading

import pandas as pd
import requests

DATA_FILE = Path("transactions.csv")

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
        "fidelity": stooq.__func__,
    }

# ========= Data File I/O =========
def append_tx(symbol, platform, amount, qty):
    """Append a transaction record to CSV"""
    DATA_FILE.touch(exist_ok=True)
    with DATA_FILE.open("a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            dt.datetime.now().isoformat(timespec="seconds"),
            symbol.upper(),
            platform.lower(),
            float(amount),
            float(qty),
        ])

def read_tx() -> pd.DataFrame:
    if not DATA_FILE.exists():
        return pd.DataFrame(columns=["time", "symbol", "platform", "amount", "qty"])
    return pd.read_csv(
        DATA_FILE,
        names=["time", "symbol", "platform", "amount", "qty"],
        parse_dates=["time"],
    )

def save_tx(df: pd.DataFrame):
    """Save transaction data to CSV"""
    df.to_csv(DATA_FILE, index=False, header=False)

def delete_tx(index: int):
    """Delete transaction at specified index"""
    df = read_tx()
    if 0 <= index < len(df):
        df = df.drop(index).reset_index(drop=True)
        save_tx(df)
        return True
    return False

def update_tx(index: int, symbol: str, platform: str, amount: float, qty: float):
    """Update transaction at specified index"""
    df = read_tx()
    if 0 <= index < len(df):
        df.loc[index, 'symbol'] = symbol.upper()
        df.loc[index, 'platform'] = platform.lower()
        df.loc[index, 'amount'] = amount
        df.loc[index, 'qty'] = qty
        save_tx(df)
        return True
    return False

# ========= Report Logic =========
def build_portfolio_data(df: pd.DataFrame):
    """Generate portfolio data"""
    if df.empty:
        return None, None, None

    # 1. Calculate weighted average cost by platform × symbol
    df["cost_per_unit"] = df["amount"] / df["qty"]
    grouped = (
        df.groupby(["platform", "symbol"])
        .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
        .reset_index()
    )
    grouped["avg_cost"] = grouped["total_cost"] / grouped["total_qty"]

    # 2. Fetch current prices and calculate PnL
    current_prices = {}
    for _, row in grouped.iterrows():
        platform, symbol = row["platform"], row["symbol"]
        fetch_fn = PriceFetcher.MAPPER[platform]
        try:
            price = fetch_fn(symbol)
            current_prices[(platform, symbol)] = price
        except Exception as e:
            current_prices[(platform, symbol)] = float("nan")

    grouped["live_price"] = grouped.apply(
        lambda r: current_prices[(r["platform"], r["symbol"])], axis=1
    )
    grouped["market_value"] = grouped["live_price"] * grouped["total_qty"]
    grouped["cost_value"] = grouped["total_cost"]
    grouped["pnl_$"] = grouped["market_value"] - grouped["total_cost"]
    grouped["pnl_%"] = grouped["pnl_$"] / grouped["total_cost"] * 100

    # 3. Average cost by symbol (cross-platform)
    coin_lvl = (
        df.groupby("symbol")
        .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
        .reset_index()
    )
    coin_lvl["avg_cost_all_platform"] = coin_lvl["total_cost"] / coin_lvl["total_qty"]

    # 4. Asset class (Crypto vs Stock) summary returns
    grouped["asset_class"] = grouped["symbol"].apply(classify_asset)
    asset_summary = (
        grouped.groupby("asset_class")
        .agg(total_cost=("cost_value", "sum"), market_value=("market_value", "sum"))
        .reset_index()
    )
    asset_summary["pnl_$"] = asset_summary["market_value"] - asset_summary["total_cost"]
    asset_summary["pnl_%"] = asset_summary["pnl_$"] / asset_summary["total_cost"] * 100

    return grouped, coin_lvl, asset_summary

# ========= Transaction Edit Dialog =========
class TransactionDialog:
    def __init__(self, parent, title, transaction_data=None):
        self.result = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center display
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # Create variables
        self.symbol_var = tk.StringVar()
        self.platform_var = tk.StringVar()
        self.amount_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        
        # If existing data, populate it
        if transaction_data:
            self.symbol_var.set(transaction_data.get('symbol', ''))
            self.platform_var.set(transaction_data.get('platform', ''))
            self.amount_var.set(str(transaction_data.get('amount', '')))
            self.qty_var.set(str(transaction_data.get('qty', '')))
        
        self.create_widgets()
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Transaction Details", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=(0, 25))
        
        # Input fields
        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True)
        
        # Symbol
        ttk.Label(fields_frame, text="Symbol:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        symbol_entry = ttk.Entry(fields_frame, textvariable=self.symbol_var, font=("Helvetica", 11))
        symbol_entry.pack(fill=tk.X, pady=(0, 20))
        
        # Platform
        ttk.Label(fields_frame, text="Platform:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        platform_combo = ttk.Combobox(fields_frame, textvariable=self.platform_var, 
                                     values=list(PriceFetcher.MAPPER.keys()), 
                                     font=("Helvetica", 11))
        platform_combo.pack(fill=tk.X, pady=(0, 20))
        
        # Amount
        ttk.Label(fields_frame, text="Amount (USD):", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        amount_entry = ttk.Entry(fields_frame, textvariable=self.amount_var, font=("Helvetica", 11))
        amount_entry.pack(fill=tk.X, pady=(0, 20))
        
        # Quantity
        ttk.Label(fields_frame, text="Quantity:", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        qty_entry = ttk.Entry(fields_frame, textvariable=self.qty_var, font=("Helvetica", 11))
        qty_entry.pack(fill=tk.X, pady=(0, 25))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(25, 0))
        
        # Buttons
        ttk.Button(button_frame, text="Save", command=self.save, style="Accent.TButton").pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        
        # Bind enter key
        self.dialog.bind('<Return>', lambda e: self.save())
        self.dialog.bind('<Escape>', lambda e: self.cancel())
        
        # Focus first input
        symbol_entry.focus()
    
    def save(self):
        try:
            symbol = self.symbol_var.get().strip()
            platform = self.platform_var.get().strip()
            amount = float(self.amount_var.get())
            qty = float(self.qty_var.get())
            
            if not symbol or not platform:
                messagebox.showerror("Error", "Please fill in all fields", parent=self.dialog)
                return
            
            if amount <= 0 or qty <= 0:
                messagebox.showerror("Error", "Amount and quantity must be greater than 0", parent=self.dialog)
                return
            
            self.result = {
                'symbol': symbol,
                'platform': platform,
                'amount': amount,
                'qty': qty
            }
            self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers", parent=self.dialog)
    
    def cancel(self):
        self.dialog.destroy()

# ========= Custom Table Widget =========
class BeautifulTable(ttk.Frame):
    def __init__(self, parent, columns, title="", height=8):
        super().__init__(parent)
        self.columns = columns
        self.title = title
        self.height = height
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        if self.title:
            title_label = ttk.Label(self, text=self.title, font=("Helvetica", 12, "bold"))
            title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Create table frame
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", height=self.height)
        
        # Set column headers and widths
        column_widths = {
            "Platform": 80,
            "Symbol": 80,
            "Total Qty": 100,
            "Avg Cost": 100,
            "Live Price": 100,
            "Cost Value": 120,
            "Market Value": 120,
            "PnL $": 100,
            "PnL %": 80,
            "Asset Class": 100,
            "Total Cost": 120,
            "Avg Cost All": 120,
            "Time": 120,
            "Amount": 100,
            "Quantity": 100
        }
        
        for col in self.columns:
            self.tree.heading(col, text=col)
            width = column_widths.get(col, 100)
            self.tree.column(col, width=width, minwidth=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Set alternating row colors
        self.tree.tag_configure('oddrow', background='#F8F9FA')
        self.tree.tag_configure('evenrow', background='#FFFFFF')
        self.tree.tag_configure('positive', foreground='#28A745')
        self.tree.tag_configure('negative', foreground='#DC3545')
    
    def clear(self):
        """Clear table"""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def add_data(self, data_list):
        """Add data to table"""
        self.clear()
        for i, row_data in enumerate(data_list):
            tags = ('evenrow' if i % 2 == 0 else 'oddrow',)
            
            # Add color tags for PnL
            if len(row_data) > 7 and isinstance(row_data[7], (int, float)):
                if row_data[7] > 0:
                    tags += ('positive',)
                elif row_data[7] < 0:
                    tags += ('negative',)
            
            self.tree.insert('', 'end', values=row_data, tags=tags)

# ========= GUI Application =========
class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Tracker")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # Set styles
        self.setup_styles()
        
        # Create main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Configure grid weights
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        
        self.create_widgets()
        self.refresh_data()

    def setup_styles(self):
        """Set custom styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Define colors
        primary_color = "#007AFF"
        success_color = "#34C759"
        warning_color = "#FF9500"
        danger_color = "#FF3B30"
        
        # Title style
        style.configure("Title.TLabel", font=("Helvetica", 24, "bold"), foreground=primary_color)
        
        # Accent button style
        style.configure("Accent.TButton", 
                       background=primary_color, 
                       foreground="white",
                       font=("Helvetica", 11, "bold"))
        
        # Success button style
        style.configure("Success.TButton",
                       background=success_color,
                       foreground="white",
                       font=("Helvetica", 11, "bold"))
        
        # Danger button style
        style.configure("Danger.TButton",
                       background=danger_color,
                       foreground="white",
                       font=("Helvetica", 11, "bold"))

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.main_frame, text="📊 Portfolio Tracker", style="Title.TLabel")
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 25))

        # Left panel - Transaction Management
        left_frame = ttk.Frame(self.main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 15))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)

        # Add transaction frame
        add_frame = ttk.LabelFrame(left_frame, text="➕ Add New Transaction", padding="20")
        add_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        add_frame.columnconfigure(1, weight=1)
        add_frame.columnconfigure(3, weight=1)

        # Transaction input fields
        ttk.Label(add_frame, text="Symbol:", font=("Helvetica", 11, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=8)
        self.symbol_var = tk.StringVar()
        self.symbol_entry = ttk.Entry(add_frame, textvariable=self.symbol_var, font=("Helvetica", 11))
        self.symbol_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15), pady=8)

        ttk.Label(add_frame, text="Platform:", font=("Helvetica", 11, "bold")).grid(row=0, column=2, sticky=tk.W, padx=(0, 8), pady=8)
        self.platform_var = tk.StringVar()
        platform_combo = ttk.Combobox(add_frame, textvariable=self.platform_var, 
                                     values=list(PriceFetcher.MAPPER.keys()), 
                                     font=("Helvetica", 11))
        platform_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 15), pady=8)

        ttk.Label(add_frame, text="Amount (USD):", font=("Helvetica", 11, "bold")).grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=8)
        self.amount_var = tk.StringVar()
        self.amount_entry = ttk.Entry(add_frame, textvariable=self.amount_var, font=("Helvetica", 11))
        self.amount_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 15), pady=8)

        ttk.Label(add_frame, text="Quantity:", font=("Helvetica", 11, "bold")).grid(row=1, column=2, sticky=tk.W, padx=(0, 8), pady=8)
        self.qty_var = tk.StringVar()
        self.qty_entry = ttk.Entry(add_frame, textvariable=self.qty_var, font=("Helvetica", 11))
        self.qty_entry.grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(0, 15), pady=8)

        # Add button
        add_button = ttk.Button(add_frame, text="➕ Add Transaction", command=self.add_transaction, style="Success.TButton")
        add_button.grid(row=2, column=0, columnspan=4, pady=(20, 0))

        # Transaction list frame
        transactions_frame = ttk.LabelFrame(left_frame, text="📋 Transaction History", padding="15")
        transactions_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        transactions_frame.columnconfigure(0, weight=1)
        transactions_frame.rowconfigure(0, weight=1)

        # Transaction list
        columns = ("Time", "Symbol", "Platform", "Amount", "Quantity")
        self.transactions_tree = ttk.Treeview(transactions_frame, columns=columns, show="headings", height=8)
        
        # Set column headers and widths
        column_widths = {"Time": 120, "Symbol": 80, "Platform": 80, "Amount": 100, "Quantity": 100}
        for col in columns:
            self.transactions_tree.heading(col, text=col)
            self.transactions_tree.column(col, width=column_widths.get(col, 100), minwidth=80)
        
        # Scrollbar
        transactions_scrollbar = ttk.Scrollbar(transactions_frame, orient=tk.VERTICAL, command=self.transactions_tree.yview)
        self.transactions_tree.configure(yscrollcommand=transactions_scrollbar.set)
        
        self.transactions_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        transactions_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Transaction operation buttons
        transactions_buttons_frame = ttk.Frame(transactions_frame)
        transactions_buttons_frame.grid(row=1, column=0, columnspan=2, pady=(15, 0))
        
        ttk.Button(transactions_buttons_frame, text="✏️ Edit", command=self.edit_transaction).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(transactions_buttons_frame, text="🗑️ Delete", command=self.delete_transaction, style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(transactions_buttons_frame, text="🔄 Refresh", command=self.refresh_data).pack(side=tk.LEFT)

        # Right panel - Reports
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Create report tabs
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Detailed report tab
        detail_frame = ttk.Frame(self.notebook)
        self.notebook.add(detail_frame, text="📊 Detailed Report")
        
        # Platform-Symbol detail table
        self.detail_table = BeautifulTable(detail_frame, 
                                          ["Platform", "Symbol", "Total Qty", "Avg Cost", "Live Price", 
                                           "Cost Value", "Market Value", "PnL $", "PnL %"],
                                          "Platform-Symbol Details")
        self.detail_table.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Symbol summary table
        self.coin_table = BeautifulTable(detail_frame, 
                                        ["Symbol", "Total Qty", "Total Cost", "Avg Cost All"],
                                        "Symbol Overall Average Cost (Cross-Platform)")
        self.coin_table.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Asset class summary table
        self.asset_table = BeautifulTable(detail_frame, 
                                         ["Asset Class", "Total Cost", "Market Value", "PnL $", "PnL %"],
                                         "Asset Class Summary Returns")
        self.asset_table.pack(fill=tk.BOTH, expand=True)

        # Bind double-click event
        self.transactions_tree.bind("<Double-1>", lambda e: self.edit_transaction())

    def add_transaction(self):
        """Add new transaction"""
        try:
            symbol = self.symbol_var.get().strip()
            platform = self.platform_var.get().strip()
            amount = float(self.amount_var.get())
            qty = float(self.qty_var.get())

            if not symbol or not platform:
                messagebox.showerror("Error", "Please fill in all fields")
                return

            if amount <= 0 or qty <= 0:
                messagebox.showerror("Error", "Amount and quantity must be greater than 0")
                return

            append_tx(symbol, platform, amount, qty)
            
            # Clear input fields
            self.symbol_var.set("")
            self.platform_var.set("")
            self.amount_var.set("")
            self.qty_var.set("")
            
            messagebox.showinfo("Success", "✅ Transaction added!")
            self.refresh_data()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add transaction: {str(e)}")

    def edit_transaction(self):
        """Edit selected transaction"""
        selection = self.transactions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a transaction to edit")
            return
        
        item = self.transactions_tree.item(selection[0])
        index = int(item['values'][0])  # First column is index
        
        # Get current transaction data
        df = read_tx()
        if 0 <= index < len(df):
            transaction_data = {
                'symbol': df.iloc[index]['symbol'],
                'platform': df.iloc[index]['platform'],
                'amount': df.iloc[index]['amount'],
                'qty': df.iloc[index]['qty']
            }
            
            # Open edit dialog
            dialog = TransactionDialog(self.root, "Edit Transaction", transaction_data)
            
            if dialog.result:
                # Update transaction
                if update_tx(index, dialog.result['symbol'], dialog.result['platform'], 
                           dialog.result['amount'], dialog.result['qty']):
                    messagebox.showinfo("Success", "✅ Transaction updated!")
                    self.refresh_data()
                else:
                    messagebox.showerror("Error", "Failed to update transaction")

    def delete_transaction(self):
        """Delete selected transaction"""
        selection = self.transactions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a transaction to delete")
            return
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected transaction?"):
            item = self.transactions_tree.item(selection[0])
            index = int(item['values'][0])  # First column is index
            
            if delete_tx(index):
                messagebox.showinfo("Success", "✅ Transaction deleted!")
                self.refresh_data()
            else:
                messagebox.showerror("Error", "Failed to delete transaction")

    def refresh_data(self):
        """Refresh data and reports"""
        def update_data():
            try:
                df = read_tx()
                
                # Update transaction list
                self.root.after(0, lambda: self.update_transactions_list(df))
                
                # Update report tables
                portfolio_data = build_portfolio_data(df)
                self.root.after(0, lambda: self.update_portfolio_tables(portfolio_data))
                
            except Exception as e:
                error_msg = f"Failed to refresh data: {str(e)}"
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))

        # Execute in background thread
        threading.Thread(target=update_data, daemon=True).start()

    def update_transactions_list(self, df):
        """Update transaction list display"""
        # Clear existing items
        for item in self.transactions_tree.get_children():
            self.transactions_tree.delete(item)
        
        # Add transaction data
        for index, row in df.iterrows():
            time_str = row['time'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['time']) else 'N/A'
            self.transactions_tree.insert('', 'end', values=(
                index,  # Index
                time_str,
                row['symbol'],
                row['platform'],
                f"${row['amount']:,.2f}",
                f"{row['qty']:,.6f}"
            ))

    def update_portfolio_tables(self, portfolio_data):
        """Update portfolio tables"""
        if portfolio_data[0] is None:  # No data
            self.detail_table.add_data([])
            self.coin_table.add_data([])
            self.asset_table.add_data([])
            return
        
        grouped, coin_lvl, asset_summary = portfolio_data
        
        # 更新详细报表表格
        detail_data = []
        for _, row in grouped.iterrows():
            detail_data.append([
                row['platform'],
                row['symbol'],
                f"{row['total_qty']:,.6f}",
                f"${row['avg_cost']:,.2f}",
                f"${row['live_price']:,.2f}" if pd.notna(row['live_price']) else "N/A",
                f"${row['cost_value']:,.2f}",
                f"${row['market_value']:,.2f}" if pd.notna(row['market_value']) else "N/A",
                f"${row['pnl_$']:,.2f}" if pd.notna(row['pnl_$']) else "N/A",
                f"{row['pnl_%']:,.2f}%" if pd.notna(row['pnl_%']) else "N/A"
            ])
        self.detail_table.add_data(detail_data)
        
        # 更新币种汇总表格
        coin_data = []
        for _, row in coin_lvl.iterrows():
            coin_data.append([
                row['symbol'],
                f"{row['total_qty']:,.6f}",
                f"${row['total_cost']:,.2f}",
                f"${row['avg_cost_all_platform']:,.2f}"
            ])
        self.coin_table.add_data(coin_data)
        
        # 更新资产大类汇总表格
        asset_data = []
        for _, row in asset_summary.iterrows():
            asset_data.append([
                row['asset_class'],
                f"${row['total_cost']:,.2f}",
                f"${row['market_value']:,.2f}" if pd.notna(row['market_value']) else "N/A",
                f"${row['pnl_$']:,.2f}" if pd.notna(row['pnl_$']) else "N/A",
                f"{row['pnl_%']:,.2f}%" if pd.notna(row['pnl_%']) else "N/A"
            ])
        self.asset_table.add_data(asset_data)

def main():
    root = tk.Tk()
    app = PortfolioApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 