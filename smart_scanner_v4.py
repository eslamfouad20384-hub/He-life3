import streamlit as st
import requests
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(layout="wide")
st.title("🚀 Ultra Smart Scanner PRO V4 (Multi-Timeframe + Clean Data Filter)")

session = requests.Session()

# =========================
# 📦 COINS LIST
# =========================
@st.cache_data(ttl=3600)
def get_all_products():
    try:
        url = "https://api.exchange.coinbase.com/products"
        r = session.get(url, timeout=10).json()

        symbols = [
            item["base_currency"]
            for item in r
            if item.get("quote_currency") == "USD"
        ]

        return list(set(symbols))
    except Exception as e:
        st.error(f"Error loading coins: {e}")
        return []


# =========================
# 📊 MARKET DATA
# =========================
@st.cache_data(ttl=60)
def get_data(symbol, granularity):
    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles?granularity={granularity}"
        r = session.get(url, timeout=10).json()

        if not isinstance(r, list) or len(r) < 50:
            return None

        df = pd.DataFrame(r, columns=["time","low","high","open","close","volume"])
        df = df.dropna()
        df = df.sort_values("time").reset_index(drop=True)

        return df.astype(float)

    except:
        return None


# =========================
# 🧹 DATA VALIDATION (NEW)
# =========================
def validate_dataframe(df):

    required_cols = ["low", "high", "open", "close", "volume"]

    # missing columns
    for col in required_cols:
        if col not in df.columns:
            return False

    # empty / invalid prices
    if (df["close"] <= 0).any():
        return False

    # no volume
    if df["volume"].sum() == 0:
        return False

    # nulls
    if df.isnull().sum().sum() > 0:
        return False

    # invalid candles
    if (df["high"] < df["low"]).any():
        return False

    return True


# =========================
# 📈 INDICATORS
# =========================
def add_indicators(df):

    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = pd.Series(gain).ewm(alpha=1/14, adjust=False).mean()
    avg_loss = pd.Series(loss).ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()

    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()
    df["support"] = df["low"].rolling(20).min()
    df["resistance"] = df["high"].rolling(20).max()

    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    df = df.dropna()
    return df


# =========================
# 🧠 4H ANALYSIS (TREND FILTER)
# =========================
def analyze_4h(df):

    latest = df.iloc[-1]
    score = 0

    if latest["ema50"] > latest["ema200"]:
        score += 30

    if latest["rsi"] < 45:
        score += 20

    if latest["macd"] > latest["signal"]:
        score += 20

    if latest["volume"] > df["volume"].mean():
        score += 10

    return score


# =========================
# ⏱ 1H SIGNAL
# =========================
def analyze_1h(df):

    latest = df.iloc[-1]
    score = 0

    if latest["rsi"] < 35:
        score += 20

    if latest["macd"] > latest["signal"]:
        score += 20

    if latest["close"] > df["close"].iloc[-5:].mean():
        score += 15

    if latest["volume"] > df["vol_ma"]:
        score += 15

    if latest["close"] <= latest["support"] * 1.02:
        score += 15

    trend_strength = df["close"].iloc[-10:].mean() > df["close"].iloc[-30:-10].mean()
    if trend_strength:
        score += 15

    signal = (
        "🔥 قوي جدًا" if score >= 75 else
        "🟢 فرصة" if score >= 60 else
        "⚠️ مراقبة" if score >= 45 else
        "❌ ضعيف"
    )

    return signal, score


# =========================
# 🛑 RISK MANAGEMENT
# =========================
def risk_management(df):

    latest = df.iloc[-1]

    entry = latest["close"]
    atr = latest["atr"]
    resistance = latest["resistance"]

    if pd.isna(atr):
        return None

    stop_loss = entry - (1.5 * atr)
    risk = entry - stop_loss

    tp1 = entry + risk
    tp2 = entry + (risk * 2)
    tp3 = resistance

    return entry, stop_loss, tp1, tp2, tp3


# =========================
# ⚙️ PROCESS COIN
# =========================
def process_coin(coin):

    # ===== 4H DATA (60 days concept) =====
    df_4h = get_data(coin, 14400)
    if df_4h is None:
        return None

    df_4h = add_indicators(df_4h)

    if not validate_dataframe(df_4h):
        return None

    if len(df_4h) < 200:
        return None

    score_4h = analyze_4h(df_4h)

    if score_4h < 40:
        return None

    # ===== 1H DATA (10 days concept) =====
    df_1h = get_data(coin, 3600)
    if df_1h is None:
        return None

    df_1h = add_indicators(df_1h)

    if not validate_dataframe(df_1h):
        return None

    if len(df_1h) < 120:
        return None

    signal, score_1h = analyze_1h(df_1h)

    final_score = int((score_4h * 0.4) + (score_1h * 0.6))

    if final_score < 50:
        return None

    risk = risk_management(df_1h)
    if risk is None:
        return None

    entry, sl, tp1, tp2, tp3 = risk

    return {
        "Symbol": coin,
        "4H Score": score_4h,
        "1H Signal": signal,
        "Final Score": final_score,
        "Entry": round(entry, 4),
        "Stop Loss": round(sl, 4),
        "TP1": round(tp1, 4),
        "TP2": round(tp2, 4),
        "TP3": round(tp3, 4),
    }


# =========================
# 🚀 SCANNER
# =========================
results = []

if st.button("🚀 Scan Market PRO V4"):

    coins = get_all_products()

    if not coins:
        st.warning("No coins loaded")
        st.stop()

    progress = st.progress(0)

    with ThreadPoolExecutor(max_workers=10) as executor:

        for i, result in enumerate(executor.map(process_coin, coins)):

            if result:
                results.append(result)

            progress.progress((i + 1) / len(coins))

    if results:
        df_res = pd.DataFrame(results).sort_values("Final Score", ascending=False)
        st.success("🔥 Clean Multi-Timeframe Signals")
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("❌ No clean setups found")
