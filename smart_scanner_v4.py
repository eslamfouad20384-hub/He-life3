import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 Ultra Smart Analyzer PRO (1000 Candles + Full Status)")

session = requests.Session()

# =========================
# 📊 GET DATA (1000 CANDLES)
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, target_candles=1000, granularity=3600):

    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles"

        all_data = []
        end = None

        while len(all_data) < target_candles:

            params = {"granularity": granularity}
            if end:
                params["end"] = end

            r = session.get(url, params=params, timeout=10).json()

            if not isinstance(r, list) or len(r) == 0:
                break

            all_data.extend(r)

            oldest = min(r, key=lambda x: x[0])[0]
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

    rs = pd.Series(gain).ewm(alpha=1/14).mean() / (pd.Series(loss).ewm(alpha=1/14).mean() + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()
    df["support"] = df["low"].rolling(20).min()
    df["resistance"] = df["high"].rolling(20).max()

    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

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
        reasons.append(f"RSI ({latest['rsi']:.2f}) → تشبع بيعي +15")
    else:
        reasons.append(f"RSI ({latest['rsi']:.2f}) → لا إشارة (0)")

    if latest["macd"] > latest["signal"]:
        score += 15
        reasons.append("MACD إيجابي +15")
    else:
        reasons.append("MACD سلبي (0)")

    if latest["ema50"] > latest["ema200"]:
        score += 15
        reasons.append("ترند صاعد +15")
    else:
        reasons.append("ترند ضعيف (0)")

    if latest["close"] <= latest["support"] * 1.02:
        score += 10
        reasons.append("قريب من الدعم +10")
    else:
        reasons.append("بعيد عن الدعم (0)")

    if latest["volume"] > latest["vol_ma"]:
        score += 10
        reasons.append("حجم قوي +10")
    else:
        reasons.append("حجم ضعيف (0)")

    if latest["atr"] > df["atr"].mean():
        score += 10
        reasons.append("حركة قوية ATR +10")
    else:
        reasons.append("حركة ضعيفة ATR (0)")

    if latest["close"] > df["close"].iloc[-5:].mean():
        score += 10
        reasons.append("زخم صاعد +10")
    else:
        reasons.append("زخم ضعيف (0)")

    if df["close"].iloc[-10:].mean() > df["close"].iloc[-30:-10].mean():
        score += 5
        reasons.append("اتجاه صاعد +5")
    else:
        reasons.append("اتجاه ضعيف (0)")

    signal = (
        "🔥 قوي جدًا" if score >= 80 else
        "🟢 فرصة" if score >= 65 else
        "⚠️ مراقبة" if score >= 50 else
        "❌ ضعيف"
    )

    return score, signal, reasons


# =========================
# 🛑 RISK MANAGEMENT
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
coin = st.text_input("🔎 اكتب العملة (BTC, ETH, SOL...)")

if st.button("🚀 Analyze") and coin:

    df = get_data(coin.upper(), 1000)

    if df is None:
        st.error("❌ مفيش بيانات كفاية")
        st.stop()

    df = add_indicators(df)

    score, signal, reasons = analyze(df)
    entry, sl, tp1, tp2, tp3 = risk_management(df)

    latest = df.iloc[-1]

    # =========================
    # 📊 MARKET DATA
    # =========================
    st.subheader("📊 Market Data")
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
    }]))

    # =========================
    # 📡 DATA STATUS (رجع زي الأول)
    # =========================
    st.subheader("📡 Data Status")

    candles_count = len(df)
    completion = (candles_count / 1000) * 100

    st.write(f"📊 عدد الشموع: {candles_count}")
    st.write(f"📈 نسبة الاكتمال: {completion:.1f}%")

    if candles_count >= 950:
        st.success("🔥 البيانات كاملة")
    elif candles_count >= 700:
        st.warning("⚠️ البيانات ناقصة جزئياً")
    else:
        st.error("❌ البيانات ضعيفة أو غير مكتملة")

    # =========================
    # 🎯 TRADE PLAN
    # =========================
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

    # =========================
    # 🧠 REASONS
    # =========================
    st.subheader("🧠 Why this score?")
    for r in reasons:
        st.write("•", r)
