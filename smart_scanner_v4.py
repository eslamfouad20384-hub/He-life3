import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 Ultra Smart Analyzer PRO (1000 Candles Version)")

session = requests.Session()

# =========================
# 📊 GET 1000+ CANDLES (PAGINATION)
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, target_candles=1000, granularity=3600):

    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles"

        all_data = []
        end = None

        while len(all_data) < target_candles:

            params = {
                "granularity": granularity,
            }

            if end:
                params["end"] = end

            r = session.get(url, params=params, timeout=10).json()

            if not isinstance(r, list) or len(r) == 0:
                break

            all_data.extend(r)

            # آخر شمعة (أقدم وقت)
            oldest = min(r, key=lambda x: x[0])[0]

            # نرجع بالوقت خطوة للخلف
            end = oldest - granularity

            if len(r) < 2:
                break

        df = pd.DataFrame(all_data, columns=["time","low","high","open","close","volume"])

        df = df.drop_duplicates(subset=["time"])
        df = df.sort_values("time").reset_index(drop=True)

        for col in ["low","high","open","close","volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna()

        if len(df) < 200:
            return None

        return df.tail(target_candles)

    except:
        return None


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

    return df.dropna()


# =========================
# 🧠 ANALYSIS
# =========================
def analyze(df):

    latest = df.iloc[-1]

    score = 0
    reasons = []

    if latest["rsi"] < 35:
        score += 15
        reasons.append("RSI منخفض (+15)")

    if latest["macd"] > latest["signal"]:
        score += 15
        reasons.append("MACD إيجابي (+15)")

    if latest["ema50"] > latest["ema200"]:
        score += 15
        reasons.append("ترند صاعد (+15)")

    if latest["close"] <= latest["support"] * 1.02:
        score += 10
        reasons.append("قريب من الدعم (+10)")

    if latest["volume"] > latest["vol_ma"]:
        score += 10
        reasons.append("حجم قوي (+10)")

    if latest["atr"] > df["atr"].mean():
        score += 10
        reasons.append("حركة قوية (+10)")

    if latest["close"] > df["close"].iloc[-5:].mean():
        score += 10
        reasons.append("زخم صاعد (+10)")

    if df["close"].iloc[-10:].mean() > df["close"].iloc[-30:-10].mean():
        score += 5
        reasons.append("اتجاه إيجابي (+5)")

    signal = (
        "🔥 قوي جدًا" if score >= 80 else
        "🟢 فرصة" if score >= 65 else
        "⚠️ مراقبة" if score >= 50 else
        "❌ ضعيف"
    )

    return score, signal, reasons


# =========================
# 🛑 RISK
# =========================
def risk_management(df):

    latest = df.iloc[-1]

    entry = latest["close"]
    atr = latest["atr"]
    resistance = latest["resistance"]

    sl = entry - (1.5 * atr)
    risk = entry - sl

    tp1 = entry + risk
    tp2 = entry + (risk * 2)
    tp3 = max(resistance, tp2)

    return entry, sl, tp1, tp2, tp3


# =========================
# 🚀 UI
# =========================
coin = st.text_input("🔎 اكتب العملة")

if st.button("🚀 Analyze 1000 Candles") and coin:

    df = get_data(coin.upper(), target_candles=1000)

    if df is None:
        st.error("❌ مفيش بيانات كفاية")
        st.stop()

    df = add_indicators(df)

    score, signal, reasons = analyze(df)
    entry, sl, tp1, tp2, tp3 = risk_management(df)

    latest = df.iloc[-1]

    st.subheader("📊 Market Data (1000 Candles)")
    st.dataframe(pd.DataFrame([{
        "Price": latest["close"],
        "RSI": latest["rsi"],
        "MACD": latest["macd"],
        "EMA50": latest["ema50"],
        "EMA200": latest["ema200"],
        "ATR": latest["atr"],
        "Volume": latest["volume"],
        "Support": latest["support"],
        "Resistance": latest["resistance"],
        "Candles": len(df)
    }]))

    st.subheader("🎯 Trade Plan")
    st.dataframe(pd.DataFrame([{
        "Entry": entry,
        "Stop Loss": sl,
        "TP1": tp1,
        "TP2": tp2,
        "TP3": tp3,
        "Score": score,
        "Signal": signal,
    }]))

    st.subheader("🧠 Why this score?")
    for r in reasons:
        st.write("•", r)
