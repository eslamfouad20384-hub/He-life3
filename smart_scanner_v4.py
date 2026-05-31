import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 Ultra Smart Analyzer PRO (1000 Candles + Data Quality + Strength)")

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
# 📡 DATA QUALITY (هل الداتا سليمة)
# =========================
def data_quality(df):

    score = 0
    reasons = []

    if len(df) >= 950:
        score += 25
        reasons.append(f"عدد شموع ممتاز ({len(df)})")
    else:
        reasons.append(f"شموع ناقصة ({len(df)})")

    if df.isnull().sum().sum() == 0:
        score += 25
        reasons.append("لا توجد قيم ناقصة")
    else:
        reasons.append("يوجد قيم ناقصة")

    if df["time"].duplicated().sum() == 0:
        score += 20
        reasons.append("لا يوجد تكرار بيانات")
    else:
        reasons.append("يوجد تكرار بيانات")

    diffs = df["time"].diff().dropna()
    if len(diffs) > 0 and (diffs == diffs.mode()[0]).mean() > 0.90:
        score += 20
        reasons.append("توقيت الشموع منتظم")
    else:
        reasons.append("توقيت غير منتظم")

    if df["volume"].min() > 0:
        score += 10
        reasons.append("حجم تداول طبيعي")
    else:
        reasons.append("يوجد شموع بدون حجم")

    if score >= 85:
        label = "🔥 بيانات موثوقة جدًا"
    elif score >= 70:
        label = "🟢 بيانات جيدة"
    elif score >= 50:
        label = "⚠️ بيانات متوسطة"
    else:
        label = "❌ بيانات ضعيفة"

    return score, label, reasons


# =========================
# 📡 DATA STRENGTH (نشاط السوق)
# =========================
def data_strength(df):

    candles_score = min(len(df) / 1000 * 100, 100)

    vol_score = min((df["volume"].mean() / (df["volume"].std() + 1e-9)) * 10, 100)

    atr_score = min((df["atr"].mean() / df["close"].mean()) * 500, 100)

    strength = (candles_score + vol_score + atr_score) / 3

    if strength > 75:
        label = "🔥 سوق نشط قوي"
    elif strength > 55:
        label = "🟢 سوق طبيعي"
    elif strength > 35:
        label = "⚠️ سوق ضعيف"
    else:
        label = "❌ سوق ميت"

    return strength, label


# =========================
# 🧠 ANALYSIS
# =========================
def analyze(df):

    latest = df.iloc[-1]

    score = 0
    reasons = []

    if latest["rsi"] < 35:
        score += 15
        reasons.append(f"RSI منخفض ({latest['rsi']:.2f})")

    if latest["macd"] > latest["signal"]:
        score += 15
        reasons.append("MACD إيجابي")

    if latest["ema50"] > latest["ema200"]:
        score += 15
        reasons.append("ترند صاعد")

    if latest["close"] <= latest["support"] * 1.02:
        score += 10
        reasons.append("قريب من الدعم")

    if latest["volume"] > latest["vol_ma"]:
        score += 10
        reasons.append("حجم قوي")

    if latest["atr"] > df["atr"].mean():
        score += 10
        reasons.append("حركة قوية ATR")

    if latest["close"] > df["close"].iloc[-5:].mean():
        score += 10
        reasons.append("زخم صاعد")

    if df["close"].iloc[-10:].mean() > df["close"].iloc[-30:-10].mean():
        score += 5
        reasons.append("اتجاه صاعد")

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

    dq_score, dq_label, dq_reasons = data_quality(df)
    ds_score, ds_label = data_strength(df)

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
    # 📡 DATA QUALITY
    # =========================
    st.subheader("📡 Data Quality")
    st.metric("جودة البيانات", f"{dq_score}/100", dq_label)

    for r in dq_reasons:
        st.write("•", r)

    # =========================
    # 📡 DATA STRENGTH
    # =========================
    st.subheader("📊 Market Strength")
    st.metric("قوة السوق", f"{ds_score:.1f}/100", ds_label)

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
