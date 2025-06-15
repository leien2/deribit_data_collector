import requests
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta

# Deribit API credentials
API_KEY = "VoAzluxQ"
API_SECRET = "nKtJcddYm5r_Ec6ElAR02YGSxx7pURKKK9lUIEGhh9E"

# Deribit REST API URL
DERIBIT_API_URL = "https://www.deribit.com/api/v2"

# Data directory structure
BASE_DIR = "deribit_data"
ORDERBOOK_DIR = f"{BASE_DIR}/orderbook"
TRADES_DIR = f"{BASE_DIR}/trades"
COMBINED_DIR = f"{BASE_DIR}/combined"

# Create directories
for directory in [ORDERBOOK_DIR, TRADES_DIR, COMBINED_DIR]:
    os.makedirs(directory, exist_ok=True)

def get_order_book(instrument, depth=10):
    """Get the order book data of the specified depth"""
    url = f"{DERIBIT_API_URL}/public/get_order_book"
    params = {
        "instrument_name": instrument,
        "depth": depth
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data["result"]
    except Exception as e:
        print(f"Failed to obtain order book data: {e}")
        return None

def get_trades(instrument, start_timestamp, end_timestamp, count=1000):
    """Get historical transaction data"""
    url = f"{DERIBIT_API_URL}/public/get_last_trades_by_instrument_and_time"
    params = {
        "instrument_name": instrument,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "include_old": True,
        "count": count
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "result" in data and "trades" in data["result"]:
            return data["result"]["trades"]
        else:
            print(f"No transaction data found")
            return []
    except Exception as e:
        print(f"Failed to obtain transaction data: {e}")
        return []

def save_optimized_orderbook(orderbook_data, timestamp_str, instrument):
    """Optimize order book data storage"""
    # 1. Save complete JSON (as backup and reference)
    json_file = f"{ORDERBOOK_DIR}/{instrument}_orderbook_{timestamp_str}.json"
    with open(json_file, 'w') as f:
        json.dump(orderbook_data, f, indent=2)

    # 2. Store bids and asks as separate CSV files (easier for analysis and import)
    # Process bids
    if "bids" in orderbook_data and orderbook_data["bids"]:
        bids_df = pd.DataFrame(orderbook_data["bids"], columns=["price", "amount"])
        bids_df["timestamp"] = orderbook_data["timestamp"]
        bids_df["instrument"] = orderbook_data["instrument_name"]
        bids_df.to_csv(f"{ORDERBOOK_DIR}/{instrument}_bids_{timestamp_str}.csv", index=False)

    # Process asks
    if "asks" in orderbook_data and orderbook_data["asks"]:
        asks_df = pd.DataFrame(orderbook_data["asks"], columns=["price", "amount"])
        asks_df["timestamp"] = orderbook_data["timestamp"]
        asks_df["instrument"] = orderbook_data["instrument_name"]
        asks_df.to_csv(f"{ORDERBOOK_DIR}/{instrument}_asks_{timestamp_str}.csv", index=False)

    # 3. Store order book summary information
    summary_df = pd.DataFrame({
        "instrument_name": [orderbook_data["instrument_name"]],
        "timestamp": [orderbook_data["timestamp"]],
        "index_price": [orderbook_data.get("index_price", None)],
        "mark_price": [orderbook_data.get("mark_price", None)],
        "last_price": [orderbook_data.get("last_price", None)],
        "open_interest": [orderbook_data.get("open_interest", None)],
        "best_bid_price": [orderbook_data["bids"][0][0] if orderbook_data["bids"] else None],
        "best_ask_price": [orderbook_data["asks"][0][0] if orderbook_data["asks"] else None],
        "bid_ask_spread": [
            orderbook_data["asks"][0][0] - orderbook_data["bids"][0][0] 
            if (orderbook_data["asks"] and orderbook_data["bids"]) else None
        ]
    })
    
    summary_df.to_csv(f"{ORDERBOOK_DIR}/{instrument}_summary_{timestamp_str}.csv", index=False)
    
    return {
        "json_path": json_file,
        "summary": summary_df,
        "timestamp": orderbook_data["timestamp"]
    }

def save_trades(trades_data, start_time, end_time, instrument):
    """Save transaction data"""
    if not trades_data:
        return None

    # Create DataFrame
    trades_df = pd.DataFrame(trades_data)

    # Format time as string
    time_str = datetime.fromtimestamp(start_time/1000).strftime("%Y%m%d_%H%M%S")

    # Save as CSV
    csv_path = f"{TRADES_DIR}/{instrument}_trades_{time_str}.csv"
    trades_df.to_csv(csv_path, index=False)

    # Also save raw JSON
    json_path = f"{TRADES_DIR}/{instrument}_trades_{time_str}.json"
    with open(json_path, 'w') as f:
        json.dump(trades_data, f, indent=2)
    
    return {
        "csv_path": csv_path,
        "json_path": json_path,
        "df": trades_df
    }

def combine_data(orderbook_result, trades_result, instrument, timestamp_str):
    """Combine order book and trade data for easier analysis"""
    if not orderbook_result or not trades_result:
        return

    # Get order book summary
    orderbook_summary = orderbook_result["summary"]

    # Extract key metrics from trade data
    trades_df = trades_result["df"]

    # Calculate trade statistics
    trade_stats = {
        "trade_count": len(trades_df),
        "buy_volume": trades_df[trades_df["direction"] == "buy"]["amount"].sum() if "direction" in trades_df.columns else 0,
        "sell_volume": trades_df[trades_df["direction"] == "sell"]["amount"].sum() if "direction" in trades_df.columns else 0,
        "avg_price": trades_df["price"].mean() if "price" in trades_df.columns else 0,
        "min_price": trades_df["price"].min() if "price" in trades_df.columns else 0,
        "max_price": trades_df["price"].max() if "price" in trades_df.columns else 0
    }

    # Create combined data
    combined_data = pd.DataFrame({
        "instrument": [instrument],
        "timestamp": [orderbook_result["timestamp"]],
        "best_bid": [orderbook_summary["best_bid_price"].iloc[0]],
        "best_ask": [orderbook_summary["best_ask_price"].iloc[0]],
        "last_price": [orderbook_summary["last_price"].iloc[0]],
        "index_price": [orderbook_summary["index_price"].iloc[0]],
        "mark_price": [orderbook_summary["mark_price"].iloc[0]],
        "open_interest": [orderbook_summary["open_interest"].iloc[0]],
        "trade_count": [trade_stats["trade_count"]],
        "buy_volume": [trade_stats["buy_volume"]],
        "sell_volume": [trade_stats["sell_volume"]],
        "avg_trade_price": [trade_stats["avg_price"]],
    })
    
    # Save merged data
    combined_path = f"{COMBINED_DIR}/{instrument}_combined_{timestamp_str}.csv"
    combined_data.to_csv(combined_path, index=False)

    print(f"Combined data saved: {combined_path}")
    return combined_path

def collect_data(instrument, include_trades=True, orderbook_depth=10, time_window_minutes=5):
    """Collect order book and trade data for a specific time window"""
    print(f"Starting data collection for {instrument}...")
    
    # Create timestamp
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    
    # 1. Get order book data
    orderbook_data = get_order_book(instrument, orderbook_depth)
    if not orderbook_data:
        print("Failed to obtain order book data, operation aborted")
        return

    # 2. Save optimized order book data
    orderbook_result = save_optimized_orderbook(orderbook_data, timestamp_str, instrument)
    print(f"Order book data saved, depth: {orderbook_depth}")

    # 3. Get and save trade data (if needed)
    trades_result = None
    if include_trades:
        end_time = int(now.timestamp() * 1000)
        start_time = int((now - timedelta(minutes=time_window_minutes)).timestamp() * 1000)
        
        trades_data = get_trades(instrument, start_time, end_time)
        if trades_data:
            trades_result = save_trades(trades_data, start_time, end_time, instrument)
            print(f"Trade data saved, total {len(trades_data)} records")
        else:
            print("No trade data found")

    # 4. Combine data (if both types of data are available)
    if include_trades and trades_result:
        combine_data(orderbook_result, trades_result, instrument, timestamp_str)

def scheduled_data_collection(instrument, interval_minutes=5, duration_hours=24, 
                             orderbook_depth=10, time_window_minutes=5):
    """Schedule periodic data collection"""
    print(f"Starting scheduled data collection for {instrument}, interval {interval_minutes} minutes, duration {duration_hours} hours")

    end_time = datetime.now() + timedelta(hours=duration_hours)
    
    while datetime.now() < end_time:
        try:
            collect_data(instrument, True, orderbook_depth, time_window_minutes)

            # Wait for the next interval
            print(f"Waiting for {interval_minutes} minutes before next data collection...")
            time.sleep(interval_minutes * 60)
        except Exception as e:
            print(f"Error occurred during data collection: {e}")
            # Pause briefly and then continue
            time.sleep(30)

if __name__ == "__main__":
    # Set parameters
    instrument = "BTC-PERPETUAL"
    orderbook_depth = 15  # Order book depth
    collection_interval = 5  # Collect data every 5 minutes
    trade_window = 5  # Get trade data for the past 5 minutes

    # Run one-time data collection
    collect_data(instrument, True, orderbook_depth, trade_window)