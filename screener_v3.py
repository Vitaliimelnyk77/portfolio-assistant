#!/usr/bin/env python3
"""Screener v3 - Finnhub quotes + Twelve Data history"""
import os, requests, json, time
import pandas as pd
from datetime import datetime

with open(os.path.expanduser("~/.streamlit/secrets.toml")) as f:
    for line in f:
        if "=" in line:
            key, val = line.strip().split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"')

TOKEN = os.environ.get("TELEGRAM_TOKEN","")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID","")
TD_KEY = "93825a6528b84e4aa2896b0d879f04fe"
FH_KEY = "d7fpfj1r01qqb8rh4ocgd7fpfj1r01qqb8rh4od0"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

# Universe загружается из universe.json
try:
    UNIVERSE = json.load(open("/root/portfolio-assistant/universe.json"))
except:
    UNIVERSE = ["AAPL","MSFT","GOOGL","META","NVDA","AMD","TSLA"]

import finnhub
fh = finnhub.Client(api_key=FH_KEY)

def get_history_td(ticker):
    """Получаем 60 дней истории через Twelve Data"""
    try:
        r = requests.get(
            f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize=60&apikey={TD_KEY}",
            timeout=15
        )
        data = r.json()
        if "values" not in data:
            return None
        rows = data["values"]
        df = pd.DataFrame(rows)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except:
        return None

def calc_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_indicators(ticker):
    df = get_history_td(ticker)
    if df is None or len(df) < 20:
        return None
    try:
        c = df["close"]
        v = df["volume"]
        rsi = calc_rsi(c)
        ma20 = c.rolling(20).mean()
        ma50 = c.rolling(50).mean() if len(c) >= 50 else c.rolling(20).mean()
        ema12 = c.ewm(span=12).mean()
        ema26 = c.ewm(span=26).mean()
        macd = ema12 - ema26
        macd_sig = macd.ewm(span=9).mean()
        bb_mid = c.rolling(20).mean()
        bb_std = c.rolling(20).std()
        bb_low = bb_mid - 2 * bb_std
        l = len(c) - 1
        p = l - 1
        p2 = l - 2 if l >= 2 else p
        return {
            "price": c.iloc[l],
            "rsi": rsi.iloc[l] if not pd.isna(rsi.iloc[l]) else 50,
            "ma20": ma20.iloc[l],
            "ma50": ma50.iloc[l] if not pd.isna(ma50.iloc[l]) else ma20.iloc[l],
            "change_1d": (c.iloc[l] - c.iloc[p]) / c.iloc[p] * 100,
            "change_1w": (c.iloc[l] - c.iloc[max(l-5,0)]) / c.iloc[max(l-5,0)] * 100,
            "above_ma50": c.iloc[l] > ma50.iloc[l] if not pd.isna(ma50.iloc[l]) else True,
            "below_bb": c.iloc[l] < bb_low.iloc[l] if not pd.isna(bb_low.iloc[l]) else False,
            "macd_cross_up": macd.iloc[p2] < macd_sig.iloc[p2] and macd.iloc[l] > macd_sig.iloc[l] if not pd.isna(macd_sig.iloc[p2]) else False,
            "volume": v.iloc[l],
            "avg_volume": v.mean(),
            "vol_ratio": v.iloc[l] / v.mean() if v.mean() > 0 else 1,
        }
    except:
        return None

def score_stock(d):
    score = 0
    reasons = []
    if d["rsi"] < 25:
        score += 3; reasons.append(f"RSI={d['rsi']:.0f} сильно перепродан")
    elif d["rsi"] < 30:
        score += 2; reasons.append(f"RSI={d['rsi']:.0f} перепродан")
    elif d["rsi"] > 75:
        score -= 1; reasons.append(f"RSI={d['rsi']:.0f} перекуплен")
    if d["below_bb"]:
        score += 2; reasons.append("ниже Bollinger Band")
    if d["macd_cross_up"]:
        score += 2; reasons.append("MACD бычье пересечение")
    if d["above_ma50"]:
        score += 1; reasons.append("выше MA50")
    if d["change_1w"] < -15:
        score += 3; reasons.append(f"обвал {d['change_1w']:.1f}%/нед")
    elif d["change_1w"] < -10:
        score += 2; reasons.append(f"падение {d['change_1w']:.1f}%/нед")
    elif d["change_1w"] < -5:
        score += 1; reasons.append(f"снижение {d['change_1w']:.1f}%/нед")
    if d["vol_ratio"] > 2:
        score += 2; reasons.append(f"объём x{d['vol_ratio']:.1f}")
    elif d["vol_ratio"] > 1.5:
        score += 1; reasons.append(f"объём x{d['vol_ratio']:.1f}")
    return score, reasons

if __name__ == "__main__":
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    print(f"Скрининг {len(UNIVERSE)} активов...")
    signals = []
    for i, ticker in enumerate(UNIVERSE):
        if (i + 1) % 7 == 0:
            time.sleep(62)
            print(f"  {i+1}/{len(UNIVERSE)}... (пауза)")
        d = get_indicators(ticker)
        if not d:
            print(f"  {ticker}: skip")
            continue
        score, reasons = score_stock(d)
        if score >= 3:
            signals.append((score, ticker, d, reasons))
            print(f"  {ticker}: SIGNAL score={score}")
        time.sleep(1)
    signals.sort(reverse=True)
    results = []
    for score, ticker, d, reasons in signals[:15]:
        results.append({"ticker": ticker, "score": score, "price": round(d["price"],2), "rsi": round(d["rsi"],1), "change_1d": round(d["change_1d"],2), "change_1w": round(d["change_1w"],2), "reasons": reasons})
    with open("screener_results.json","w") as rf:
        json.dump({"date": now, "count": len(signals), "total": len(UNIVERSE), "results": results}, rf, ensure_ascii=False, indent=2)
    if signals:
        lines = [f"🔍 <b>Скрининг рынка {now}</b>\n", f"Проверено {len(UNIVERSE)} активов, найдено {len(signals)} сигналов:\n"]
        for score, ticker, d, reasons in signals[:10]:
            stars = "⭐" * min(score, 5)
            lines.append(f"{stars} <b>{ticker}</b>")
            lines.append(f"   ${d['price']:.2f} | RSI={d['rsi']:.0f} | 1д:{d['change_1d']:+.1f}% | 1нед:{d['change_1w']:+.1f}%")
            lines.append(f"   {', '.join(reasons)}\n")
        lines.append("💡 Информация для анализа, не торговый совет!")
        send("\n".join(lines))
        print(f"\nОтправлено {len(signals)} сигналов в Telegram!")
    else:
        send(f"🔍 <b>Скрининг {now}</b>\n\nСильных сигналов не найдено.")
        print("Сигналов нет")
