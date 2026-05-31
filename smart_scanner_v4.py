import streamlit as st
import requests
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(layout="wide")
st.title("🚀 Ultra Smart Scanner PRO V4 (AI Multi-Timeframe Beast)")

session = requests.Session()

# =========================
# 📦 COINS
# =========================
@st.cache_data(ttl=3600)
def get_all_products():
    try:
        url = "https://api.exchange.coinbase.com/products"
        r = session.get(url, timeout=10).json()

        return list(set([
            item["base_currency"]
            for item in r
            if item.get("quote_currency") == "USD"
        ]))

    except:
        return []


# =========================
# 📊 DATA
# =========================
@st.cache_data(ttl=60)
def get_data(symbol, tf=3600):
    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles?granularity={tf}"
        r = session.get(url, timeout=10).json()

        if not isinstance(r, list) or len(r) < 150:
            return None

        df = pd.DataFrame(r, columns=["time","low","high","open","close","volume"])
        df = df.sort_values("time").reset_index(drop=True).astype(float)

        return df

    except:
        return None


# =========================
# 📈 INDICATORS V4
# =========================
def add_indicators(df):

    # EMA
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    # RSI
    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    rs = pd.Series(gain).ewm(span=14).mean() / (pd.Series(loss).ewm(span=14).mean() + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9).mean()

    # VWAP
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()

    # Volume MA
    df["vol_ma"] = df["volume"].rolling(20).mean()

    # Support / Resistance
    df["support"] = df["low"].rolling(20).min()
    df["resistance"] = df["high"].rolling(20).max()

    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    # MFI
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]

    pos = np.where(tp > tp.shift(1), mf, 0)
    neg = np.where(tp < tp.shift(1), mf, 0)

    mfr = pd.Series(pos).rolling(14).sum() / (pd.Series(neg).rolling(14).sum() + 1e-9)
    df["mfi"] = 100 - (100 / (1 + mfr))

    # ADX (simplified but stable)
    plus_dm = df["high"].diff()
    minus_dm = df["low"].diff().abs()

    tr14 = tr.rolling(14).mean()
    df["adx"] = (abs(plus_dm - minus_dm) / (tr14 + 1e-9)).rolling(14).mean() * 100

    # OBV
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i-1]:
            obv.append(obv[-1] + df["volume"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i-1]:
            obv.append(obv[-1] - df["volume"].iloc[i])
        else:
            obv.append(obv[-1])

    df["obv"] = obv

    return df.dropna()


# =========================
# 🧠 MULTI TIMEFRAME
# =========================
def get_mtf_confirmation(symbol):

    df_1h = get_data(symbol, 3600)
    df_4h = get_data(symbol, 14400)

    if df_1h is None or df_4h is None:
        return False

    df_1h = add_indicators(df_1h)
    df_4h = add_indicators(df_4h)

    # Trend alignment
    cond1 = df_1h["ema50"].iloc[-1] > df_1h["ema200"].iloc[-1]
    cond2 = df_4h["ema50"].iloc[-1] > df_4h["ema200"].iloc[-1]

    return cond1 and cond2


# =========================
# 🧠 SMART FILTER V4
# =========================
def smart_filter(df):

    latest = df.iloc[-1]

    if len(df) < 150:
        return False

    if latest["volume"] < df["volume"].mean() * 0.6:
        return False

    if latest["adx"] < 15:
        return False

    if latest["atr"] / latest["close"] < 0.008:
        return False

    return True


# =========================
# 🎯 ANALYSIS V4
# =========================
def analyze(df):

    latest = df.iloc[-1]
    score = 0

    # Trend
    if latest["ema50"] > latest["ema200"]:
        score += 15

    # VWAP confirmation
    if latest["close"] > latest["vwap"]:
        score += 10

    # RSI
    if latest["rsi"] < 40:
        score += 10

    # MACD
    if latest["macd"] > latest["signal"]:
        score += 10

    # MFI
    if latest["mfi"] < 40:
        score += 10

    # ADX
    if latest["adx"] > 20:
        score += 10

    # OBV trend
    if df["obv"].iloc[-1] > df["obv"].iloc[-5]:
        score += 10

    # Breakout
    if latest["close"] > df["resistance"].iloc[-2]:
        score += 10

    # Support bounce
    if latest["close"] <= latest["support"] * 1.02:
        score += 10

    signal = (
        "🔥 قوي جدًا" if score >= 80 else
        "🟢 فرصة" if score >= 65 else
        "⚠️ مراقبة" if score >= 50 else
        "❌ ضعيف"
    )

    return signal, score


# =========================
# 🛑 RISK V4
# =========================
def risk_management(df):

    latest = df.iloc[-1]

    entry = latest["close"]
    atr = latest["atr"]

    if pd.isna(atr):
        return None

    sl = entry - (1.8 * atr)
    risk = entry - sl

    tp1 = entry + risk
    tp2 = entry + (risk * 2)
    tp3 = entry + (risk * 3)

    return entry, sl, tp1, tp2, tp3


# =========================
# ⚙️ PROCESS COIN
# =========================
def process_coin(coin):

    df = get_data(coin, 3600)

    if df is None:
        return None

    df = add_indicators(df)

    if not smart_filter(df):
        return None

    # Multi timeframe confirmation
    if not get_mtf_confirmation(coin):
        return None

    signal, score = analyze(df)

    if score < 60:
        return None

    risk = risk_management(df)

    if risk is None:
        return None

    entry, sl, tp1, tp2, tp3 = risk

    return {
        "Symbol": coin,
        "Signal": signal,
        "Score": score,
        "Entry": round(entry, 4),
        "SL": round(sl, 4),
        "TP1": round(tp1, 4),
        "TP2": round(tp2, 4),
        "TP3": round(tp3, 4),
    }


# =========================
# 🚀 SCANNER
# =========================
results = []

if st.button("🚀 Scan Market V4 (AI MODE)"):

    coins = get_all_products()

    if not coins:
        st.warning("No coins loaded")
        st.stop()

    progress = st.progress(0)

    with ThreadPoolExecutor(max_workers=8) as executor:

        for i, result in enumerate(executor.map(process_coin, coins)):

            if result:
                results.append(result)

            progress.progress((i + 1) / len(coins))

    if results:
        df_res = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.success("🔥 AI Quality Signals Found")
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("❌ No setups found")
