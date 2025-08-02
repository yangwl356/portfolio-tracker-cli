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

# ========= 资产分类助手 =========
def classify_asset(symbol: str) -> str:
    """简易分类函数：以 "USD" 结尾的交易对视为加密货币 (crypto)，其余默认归为股票 / ETF (stock)"""
    return "crypto" if symbol.upper().endswith("USD") else "stock"

# ========= 价格抓取 =========
class PriceFetcher:
    """按平台抓实时价格（USD 计价）"""

    BINANCE_URL = "https://api.binance.us/api/v3/ticker/price"
    OKX_URL = "https://www.okx.com/api/v5/market/ticker"
    COINBASE_URL = "https://api.coinbase.com/v2/prices/{pair}/spot"
    STOOQ_URL = "https://stooq.pl/q/l/?s={ticker}&i=d"

    @staticmethod
    def stooq(symbol: str) -> float:
        """支持任意美股 / ETF（例如 QQQM、AAPL）"""
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

# ========= 数据文件读写 =========
def append_tx(symbol, platform, amount, qty):
    """追加一行交易记录到 CSV"""
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
    """保存交易数据到 CSV"""
    df.to_csv(DATA_FILE, index=False, header=False)

def delete_tx(index: int):
    """删除指定索引的交易"""
    df = read_tx()
    if 0 <= index < len(df):
        df = df.drop(index).reset_index(drop=True)
        save_tx(df)
        return True
    return False

def update_tx(index: int, symbol: str, platform: str, amount: float, qty: float):
    """更新指定索引的交易"""
    df = read_tx()
    if 0 <= index < len(df):
        df.loc[index, 'symbol'] = symbol.upper()
        df.loc[index, 'platform'] = platform.lower()
        df.loc[index, 'amount'] = amount
        df.loc[index, 'qty'] = qty
        save_tx(df)
        return True
    return False

# ========= 报表逻辑 =========
def build_portfolio_data(df: pd.DataFrame):
    """生成投资组合数据"""
    if df.empty:
        return None, None, None

    # ① 计算平台 × 币种的加权平均成本
    df["cost_per_unit"] = df["amount"] / df["qty"]
    grouped = (
        df.groupby(["platform", "symbol"])
        .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
        .reset_index()
    )
    grouped["avg_cost"] = grouped["total_cost"] / grouped["total_qty"]

    # ② 拉取当前价格并计算 PnL
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

    # ③ 各币种（跨平台）平均成本
    coin_lvl = (
        df.groupby("symbol")
        .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
        .reset_index()
    )
    coin_lvl["avg_cost_all_platform"] = coin_lvl["total_cost"] / coin_lvl["total_qty"]

    # ④ 资产大类（Crypto vs Stock）汇总收益
    grouped["asset_class"] = grouped["symbol"].apply(classify_asset)
    asset_summary = (
        grouped.groupby("asset_class")
        .agg(total_cost=("cost_value", "sum"), market_value=("market_value", "sum"))
        .reset_index()
    )
    asset_summary["pnl_$"] = asset_summary["market_value"] - asset_summary["total_cost"]
    asset_summary["pnl_%"] = asset_summary["pnl_$"] / asset_summary["total_cost"] * 100

    return grouped, coin_lvl, asset_summary

# ========= 交易编辑对话框 =========
class TransactionDialog:
    def __init__(self, parent, title, transaction_data=None):
        self.result = None
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # 创建变量
        self.symbol_var = tk.StringVar()
        self.platform_var = tk.StringVar()
        self.amount_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        
        # 如果有现有数据，填充它
        if transaction_data:
            self.symbol_var.set(transaction_data.get('symbol', ''))
            self.platform_var.set(transaction_data.get('platform', ''))
            self.amount_var.set(str(transaction_data.get('amount', '')))
            self.qty_var.set(str(transaction_data.get('qty', '')))
        
        self.create_widgets()
        
        # 等待对话框关闭
        self.dialog.wait_window()
    
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="交易信息", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=(0, 25))
        
        # 输入字段
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
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(25, 0))
        
        # 按钮
        ttk.Button(button_frame, text="保存", command=self.save, style="Accent.TButton").pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.RIGHT)
        
        # 绑定回车键
        self.dialog.bind('<Return>', lambda e: self.save())
        self.dialog.bind('<Escape>', lambda e: self.cancel())
        
        # 聚焦到第一个输入框
        symbol_entry.focus()
    
    def save(self):
        try:
            symbol = self.symbol_var.get().strip()
            platform = self.platform_var.get().strip()
            amount = float(self.amount_var.get())
            qty = float(self.qty_var.get())
            
            if not symbol or not platform:
                messagebox.showerror("错误", "请填写所有字段", parent=self.dialog)
                return
            
            if amount <= 0 or qty <= 0:
                messagebox.showerror("错误", "金额和数量必须大于0", parent=self.dialog)
                return
            
            self.result = {
                'symbol': symbol,
                'platform': platform,
                'amount': amount,
                'qty': qty
            }
            self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字", parent=self.dialog)
    
    def cancel(self):
        self.dialog.destroy()

# ========= 自定义表格组件 =========
class BeautifulTable(ttk.Frame):
    def __init__(self, parent, columns, title="", height=8):
        super().__init__(parent)
        self.columns = columns
        self.title = title
        self.height = height
        self.create_widgets()
    
    def create_widgets(self):
        # 标题
        if self.title:
            title_label = ttk.Label(self, text=self.title, font=("Helvetica", 12, "bold"))
            title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 创建表格框架
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建树形视图
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", height=self.height)
        
        # 设置列标题和宽度
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
        
        # 滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 设置交替行颜色
        self.tree.tag_configure('oddrow', background='#F8F9FA')
        self.tree.tag_configure('evenrow', background='#FFFFFF')
        self.tree.tag_configure('positive', foreground='#28A745')
        self.tree.tag_configure('negative', foreground='#DC3545')
    
    def clear(self):
        """清空表格"""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def add_data(self, data_list):
        """添加数据到表格"""
        self.clear()
        for i, row_data in enumerate(data_list):
            tags = ('evenrow' if i % 2 == 0 else 'oddrow',)
            
            # 为PnL添加颜色标签
            if len(row_data) > 7 and isinstance(row_data[7], (int, float)):
                if row_data[7] > 0:
                    tags += ('positive',)
                elif row_data[7] < 0:
                    tags += ('negative',)
            
            self.tree.insert('', 'end', values=row_data, tags=tags)

# ========= GUI 应用 =========
class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Tracker")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # 设置样式
        self.setup_styles()
        
        # 创建主框架
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 配置网格权重
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        
        self.create_widgets()
        self.refresh_data()

    def setup_styles(self):
        """设置自定义样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 定义颜色
        primary_color = "#007AFF"
        success_color = "#34C759"
        warning_color = "#FF9500"
        danger_color = "#FF3B30"
        
        # 标题样式
        style.configure("Title.TLabel", font=("Helvetica", 24, "bold"), foreground=primary_color)
        
        # 强调按钮样式
        style.configure("Accent.TButton", 
                       background=primary_color, 
                       foreground="white",
                       font=("Helvetica", 11, "bold"))
        
        # 成功按钮样式
        style.configure("Success.TButton",
                       background=success_color,
                       foreground="white",
                       font=("Helvetica", 11, "bold"))
        
        # 危险按钮样式
        style.configure("Danger.TButton",
                       background=danger_color,
                       foreground="white",
                       font=("Helvetica", 11, "bold"))

    def create_widgets(self):
        # 标题
        title_label = ttk.Label(self.main_frame, text="📊 Portfolio Tracker", style="Title.TLabel")
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 25))

        # 左侧面板 - 交易管理
        left_frame = ttk.Frame(self.main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 15))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)

        # 添加交易框架
        add_frame = ttk.LabelFrame(left_frame, text="➕ 添加新交易", padding="20")
        add_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        add_frame.columnconfigure(1, weight=1)
        add_frame.columnconfigure(3, weight=1)

        # 交易输入字段
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

        # 添加按钮
        add_button = ttk.Button(add_frame, text="➕ 添加交易", command=self.add_transaction, style="Success.TButton")
        add_button.grid(row=2, column=0, columnspan=4, pady=(20, 0))

        # 交易列表框架
        transactions_frame = ttk.LabelFrame(left_frame, text="📋 交易历史", padding="15")
        transactions_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        transactions_frame.columnconfigure(0, weight=1)
        transactions_frame.rowconfigure(0, weight=1)

        # 交易列表
        columns = ("Time", "Symbol", "Platform", "Amount", "Quantity")
        self.transactions_tree = ttk.Treeview(transactions_frame, columns=columns, show="headings", height=8)
        
        # 设置列标题和宽度
        column_widths = {"Time": 120, "Symbol": 80, "Platform": 80, "Amount": 100, "Quantity": 100}
        for col in columns:
            self.transactions_tree.heading(col, text=col)
            self.transactions_tree.column(col, width=column_widths.get(col, 100), minwidth=80)
        
        # 滚动条
        transactions_scrollbar = ttk.Scrollbar(transactions_frame, orient=tk.VERTICAL, command=self.transactions_tree.yview)
        self.transactions_tree.configure(yscrollcommand=transactions_scrollbar.set)
        
        self.transactions_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        transactions_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 交易操作按钮
        transactions_buttons_frame = ttk.Frame(transactions_frame)
        transactions_buttons_frame.grid(row=1, column=0, columnspan=2, pady=(15, 0))
        
        ttk.Button(transactions_buttons_frame, text="✏️ 编辑", command=self.edit_transaction).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(transactions_buttons_frame, text="🗑️ 删除", command=self.delete_transaction, style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(transactions_buttons_frame, text="🔄 刷新", command=self.refresh_data).pack(side=tk.LEFT)

        # 右侧面板 - 报表
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # 创建报表标签页
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 详细报表标签页
        detail_frame = ttk.Frame(self.notebook)
        self.notebook.add(detail_frame, text="📊 详细报表")
        
        # 平台-币种明细表格
        self.detail_table = BeautifulTable(detail_frame, 
                                          ["Platform", "Symbol", "Total Qty", "Avg Cost", "Live Price", 
                                           "Cost Value", "Market Value", "PnL $", "PnL %"],
                                          "各平台-币种明细")
        self.detail_table.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # 币种汇总表格
        self.coin_table = BeautifulTable(detail_frame, 
                                        ["Symbol", "Total Qty", "Total Cost", "Avg Cost All"],
                                        "币种整体平均成本（跨平台合并）")
        self.coin_table.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # 资产大类汇总表格
        self.asset_table = BeautifulTable(detail_frame, 
                                         ["Asset Class", "Total Cost", "Market Value", "PnL $", "PnL %"],
                                         "资产大类汇总收益")
        self.asset_table.pack(fill=tk.BOTH, expand=True)

        # 绑定双击事件
        self.transactions_tree.bind("<Double-1>", lambda e: self.edit_transaction())

    def add_transaction(self):
        """添加新交易"""
        try:
            symbol = self.symbol_var.get().strip()
            platform = self.platform_var.get().strip()
            amount = float(self.amount_var.get())
            qty = float(self.qty_var.get())

            if not symbol or not platform:
                messagebox.showerror("错误", "请填写所有字段")
                return

            if amount <= 0 or qty <= 0:
                messagebox.showerror("错误", "金额和数量必须大于0")
                return

            append_tx(symbol, platform, amount, qty)
            
            # 清空输入字段
            self.symbol_var.set("")
            self.platform_var.set("")
            self.amount_var.set("")
            self.qty_var.set("")
            
            messagebox.showinfo("成功", "✅ 交易已添加！")
            self.refresh_data()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
        except Exception as e:
            messagebox.showerror("错误", f"添加交易失败: {str(e)}")

    def edit_transaction(self):
        """编辑选中的交易"""
        selection = self.transactions_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要编辑的交易")
            return
        
        item = self.transactions_tree.item(selection[0])
        index = int(item['values'][0])  # 第一列是索引
        
        # 获取当前交易数据
        df = read_tx()
        if 0 <= index < len(df):
            transaction_data = {
                'symbol': df.iloc[index]['symbol'],
                'platform': df.iloc[index]['platform'],
                'amount': df.iloc[index]['amount'],
                'qty': df.iloc[index]['qty']
            }
            
            # 打开编辑对话框
            dialog = TransactionDialog(self.root, "编辑交易", transaction_data)
            
            if dialog.result:
                # 更新交易
                if update_tx(index, dialog.result['symbol'], dialog.result['platform'], 
                           dialog.result['amount'], dialog.result['qty']):
                    messagebox.showinfo("成功", "✅ 交易已更新！")
                    self.refresh_data()
                else:
                    messagebox.showerror("错误", "更新交易失败")

    def delete_transaction(self):
        """删除选中的交易"""
        selection = self.transactions_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的交易")
            return
        
        if messagebox.askyesno("确认删除", "确定要删除选中的交易吗？"):
            item = self.transactions_tree.item(selection[0])
            index = int(item['values'][0])  # 第一列是索引
            
            if delete_tx(index):
                messagebox.showinfo("成功", "✅ 交易已删除！")
                self.refresh_data()
            else:
                messagebox.showerror("错误", "删除交易失败")

    def refresh_data(self):
        """刷新数据和报表"""
        def update_data():
            try:
                df = read_tx()
                
                # 更新交易列表
                self.root.after(0, lambda: self.update_transactions_list(df))
                
                # 更新报表表格
                portfolio_data = build_portfolio_data(df)
                self.root.after(0, lambda: self.update_portfolio_tables(portfolio_data))
                
            except Exception as e:
                error_msg = f"刷新数据失败: {str(e)}"
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))

        # 在后台线程中执行
        threading.Thread(target=update_data, daemon=True).start()

    def update_transactions_list(self, df):
        """更新交易列表显示"""
        # 清空现有项目
        for item in self.transactions_tree.get_children():
            self.transactions_tree.delete(item)
        
        # 添加交易数据
        for index, row in df.iterrows():
            time_str = row['time'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['time']) else 'N/A'
            self.transactions_tree.insert('', 'end', values=(
                index,  # 索引
                time_str,
                row['symbol'],
                row['platform'],
                f"${row['amount']:,.2f}",
                f"{row['qty']:,.6f}"
            ))

    def update_portfolio_tables(self, portfolio_data):
        """更新投资组合表格"""
        if portfolio_data[0] is None:  # 没有数据
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