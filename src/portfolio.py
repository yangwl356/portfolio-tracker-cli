#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crypto_portfolio.py
用法举例：
    # 记一笔买入：在 Binance 以 4 000 USD 买入 0.05 BTC
    python crypto_portfolio.py add --symbol BTCUSD --platform binance --amount 4000 --qty 0.05

    # 查看汇总报表
    python crypto_portfolio.py report
"""
import argparse
import csv
import datetime as dt
import os
import sys
from pathlib import Path

import pandas as pd
import requests

DATA_FILE = Path("transactions.csv")


# ========= 资产分类助手 =========
def classify_asset(symbol: str) -> str:
    """
    简易分类函数：
      • 以 “USD” 结尾的交易对视为加密货币 (crypto)
      • 其余默认归为股票 / ETF (stock)
    如需更精确的分类逻辑，可在此函数中扩展。
    """
    return "crypto" if symbol.upper().endswith("USD") else "stock"


# ========= 价格抓取 =========
class PriceFetcher:
    """按平台抓实时价格（USD 计价）"""

    BINANCE_URL = "https://api.binance.us/api/v3/ticker/price"  #  [oai_citation:0‡docs.binance.us](https://docs.binance.us/)
    OKX_URL = "https://www.okx.com/api/v5/market/ticker"        #  [oai_citation:1‡OKX United States](https://app.okx.com/docs-v5/en/)
    COINBASE_URL = "https://api.coinbase.com/v2/prices/{pair}/spot"  #  [oai_citation:2‡Stack Overflow](https://stackoverflow.com/questions/70868199/coinbase-api-call-to-get-crypto-spot-prices)
    STOOQ_URL    = "https://stooq.pl/q/l/?s={ticker}&i=d"

    @staticmethod
    def yahoo(symbol: str) -> float:
        """
        任意符号（如 AAPL、QQQM、BTC-USD 等）返回 regularMarketPrice
        """
        resp = requests.get(PriceFetcher.YAHOO_URL, params={"symbols": symbol})
        resp.raise_for_status()
        data = resp.json()["quoteResponse"]["result"]
        if not data:
            raise ValueError(f"Yahoo 无法找到报价: {symbol}")
        return float(data[0]["regularMarketPrice"])
    
    @staticmethod
    def stooq(symbol: str) -> float:
        """
        支持任意美股 / ETF（例如 QQQM、AAPL）。
        Stooq 规则：美股代码末尾加 '.US'，返回 CSV:
            Symbol,Date,Time,Open,High,Low,Close,Volume
        我们取 Close 作为“最新价格”（日粒度）。
        """
        ticker = symbol.lower()
        if "." not in ticker:          # QQQM  →  qqqm.us
            ticker += ".us"
        url = PriceFetcher.STOOQ_URL.format(ticker=ticker)
        hdrs = {"User-Agent": "Mozilla/5.0"}  # 防 CDN 拒绝
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
        # OKX 使用连字符写法，如 BTC-USD；若只给 BTCUSD，自行转为 BTC-USD
        if "-" not in symbol:
            symbol = symbol[:3] + "-" + symbol[3:]
        resp = requests.get(PriceFetcher.OKX_URL, params={"instId": symbol.upper()})
        resp.raise_for_status()
        return float(resp.json()["data"][0]["last"])

    @staticmethod
    def coinbase(symbol: str) -> float:
        # Coinbase 使用 BTC-USD 形式
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
        writer.writerow(
            [
                dt.datetime.now().isoformat(timespec="seconds"),
                symbol.upper(),
                platform.lower(),
                float(amount),
                float(qty),
            ]
        )


def read_tx() -> pd.DataFrame:
    if not DATA_FILE.exists():
        return pd.DataFrame(
            columns=["time", "symbol", "platform", "amount", "qty"]
        )
    return pd.read_csv(
        DATA_FILE,
        names=["time", "symbol", "platform", "amount", "qty"],
        parse_dates=["time"],
    )


# ========= 报表逻辑 =========
def build_report(df: pd.DataFrame) -> None:
    if df.empty:
        print("尚无任何交易记录，先用 add 子命令录入吧！")
        return

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
            print(f"⚠️  获取 {platform} {symbol} 行情失败：{e}")
            current_prices[(platform, symbol)] = float("nan")

    grouped["live_price"] = grouped.apply(
        lambda r: current_prices[(r["platform"], r["symbol"])], axis=1
    )
    grouped["market_value"] = grouped["live_price"] * grouped["total_qty"]
    grouped["cost_value"] = grouped["total_cost"]
    grouped["pnl_$"] = grouped["market_value"] - grouped["total_cost"]
    grouped["pnl_%"] = grouped["pnl_$"] / grouped["total_cost"] * 100

    # ③ 输出
    pd.set_option("display.float_format", lambda x: f"{x:,.6f}")
    print("\n=== 各平台-币种明细 ===")
    print(
        grouped[
            [
                "platform",
                "symbol",
                "total_qty",
                "avg_cost",
                "live_price",
                "cost_value",
                "market_value",
                "pnl_$",
                "pnl_%",
            ]
        ].to_string(index=False)
    )

    # ④ 各币种（跨平台）平均成本
    coin_lvl = (
        df.groupby("symbol")
        .agg(total_qty=("qty", "sum"), total_cost=("amount", "sum"))
        .reset_index()
    )
    coin_lvl["avg_cost_all_platform"] = coin_lvl["total_cost"] / coin_lvl["total_qty"]
    print("\n=== 币种整体平均成本（跨平台合并） ===")
    print(coin_lvl[["symbol", "total_qty", "total_cost", "avg_cost_all_platform"]].to_string(index=False))

    # ⑤ 资产大类（Crypto vs Stock）汇总收益
    grouped["asset_class"] = grouped["symbol"].apply(classify_asset)
    asset_summary = (
        grouped.groupby("asset_class")
        .agg(
            total_cost=("cost_value", "sum"),
            market_value=("market_value", "sum"),
        )
        .reset_index()
    )
    asset_summary["pnl_$"] = asset_summary["market_value"] - asset_summary["total_cost"]
    asset_summary["pnl_%"] = asset_summary["pnl_$"] / asset_summary["total_cost"] * 100
    print("\n=== 资产大类汇总收益 ===")
    print(asset_summary.to_string(index=False))


# ========= CLI =========
def cli():
    # ---------- 新增：双击 .app 时默认显示报表 ----------
    if len(sys.argv) == 1:          # 没给任何参数
        sys.argv.append("report")   # 注入默认子命令
    # ---------------------------------------------------
    parser = argparse.ArgumentParser(description="记录并汇总加密货币投资")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # add
    p_add = subparsers.add_parser("add", help="录入一笔购买")
    p_add.add_argument("--symbol", required=True, help="币对，如 BTCUSD / ETHUSD / BNBUSD")
    ALLOWED_PLATFORMS = list(PriceFetcher.MAPPER.keys())
    p_add.add_argument("--platform", required=True, choices=ALLOWED_PLATFORMS)
    p_add.add_argument("--amount", required=True, type=float, help="花费金额（USD）")
    p_add.add_argument("--qty", required=True, type=float, help="买入数量")

    # report
    subparsers.add_parser("report", help="生成汇总报表")

    args = parser.parse_args()

    if args.cmd == "add":
        append_tx(args.symbol, args.platform, args.amount, args.qty)
        print("✅ 已记录！")
    elif args.cmd == "report":
        build_report(read_tx())


if __name__ == "__main__":
    cli()