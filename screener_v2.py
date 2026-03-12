import os, requests, yfinance as yf, json
from datetime import datetime
import pandas as pd

# Загрузка ключей
with open(os.path.expanduser("~/.streamlit/secrets.toml")) as f:
    for line in f:
        if "=" in line:
            key, val = line.strip().split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"')

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

def get_sp500():
    try:
        from io import StringIO
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers)
        df = pd.read_html(StringIO(r.text))[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except:
        return []

def get_nasdaq100():
    try:
        from io import StringIO
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://en.wikipedia.org/wiki/Nasdaq-100", headers=headers)
        for df in pd.read_html(StringIO(r.text)):
            if "Ticker" in df.columns:
                return df["Ticker"].tolist()
            if "Symbol" in df.columns:
                return df["Symbol"].tolist()
    except:
        pass
    return []

def get_yahoo_screener():
    """Получаем trending/most active тикеры"""
    tickers = set()
    try:
        for s in ["most_actives", "day_gainers", "day_losers"]:
            sc = yf.Screener()
            sc.set_default_body(s)
            data = sc.response
            if data and "finance" in data and "result" in data["finance"]:
                for r in data["finance"]["result"]:
                    for q in r.get("quotes", []):
                        sym = q.get("symbol", "")
                        if sym and "." not in sym and len(sym) <= 5:
                            tickers.add(sym)
    except:
        pass
    return list(tickers)

EXTRA = [
    "SOFI", "AFRM", "UPST", "COIN", "NIO", "PLTR", "RIVN", "LCID",
    "MARA", "RIOT", "HOOD", "RBLX", "SNAP", "PINS", "DKNG",
    "BTC-USD", "ETH-USD", "SOL-USD",
    "VGWL.DE", "CSPX.L",
]

def get_indicators(ticker):
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if len(h) < 20:
            return None
        h["MA20"] = h["Close"].rolling(20).mean()
        h["MA50"] = h["Close"].rolling(50).mean()
        delta = h["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        h["RSI"] = 100 - (100 / (1 + rs))
        # Bollinger Bands
        h["BB_mid"] = h["Close"].rolling(20).mean()
        h["BB_std"] = h["Close"].rolling(20).std()
        h["BB_low"] = h["BB_mid"] - 2 * h["BB_std"]
        h["BB_high"] = h["BB_mid"] + 2 * h["BB_std"]
        # MACD
        ema12 = h["Close"].ewm(span=12).mean()
        ema26 = h["Close"].ewm(span=26).mean()
        h["MACD"] = ema12 - ema26
        h["MACD_signal"] = h["MACD"].ewm(span=9).mean()
        l = h.iloc[-1]
        prev = h.iloc[-2]
        prev2 = h.iloc[-3] if len(h) >= 3 else prev
        week_ago = h.iloc[-6] if len(h) >= 6 else h.iloc[0]
        return {
            "price": l["Close"],
            "rsi": l["RSI"],
            "ma20": l["MA20"],
            "ma50": l["MA50"],
            "change_1d": (l["Close"] - prev["Close"]) / prev["Close"] * 100,
            "change_1w": (l["Close"] - week_ago["Close"]) / week_ago["Close"] * 100,
            "above_ma50": l["Close"] > l["MA50"],
            "below_bb": l["Close"] < l["BB_low"],
            "above_bb": l["Close"] > l["BB_high"],
            "macd_cross_up": prev2["MACD"] < prev2["MACD_signal"] and l["MACD"] > l["MACD_signal"],
            "macd_cross_down": prev2["MACD"] > prev2["MACD_signal"] and l["MACD"] < l["MACD_signal"],
            "volume": l["Volume"],
            "avg_volume": h["Volume"].mean(),
            "vol_ratio": l["Volume"] / h["Volume"].mean() if h["Volume"].mean() > 0 else 1,
        }
    except:
        return None

def score_stock(d):
    score = 0
    reasons = []
    # RSI
    if d["rsi"] < 25:
        score += 3
        reasons.append(f"RSI={d['rsi']:.0f} сильно перепродан")
    elif d["rsi"] < 30:
        score += 2
        reasons.append(f"RSI={d['rsi']:.0f} перепродан")
    elif d["rsi"] > 75:
        score -= 1
        reasons.append(f"RSI={d['rsi']:.0f} перекуплен")
    # Bollinger
    if d["below_bb"]:
        score += 2
        reasons.append("ниже Bollinger Band")
    # MACD
    if d["macd_cross_up"]:
        score += 2
        reasons.append("MACD бычье пересечение")
    # Тренд
    if d["above_ma50"]:
        score += 1
        reasons.append("выше MA50")
    # Падение за неделю
    if d["change_1w"] < -15:
        score += 3
        reasons.append(f"обвал {d['change_1w']:.1f}% за неделю")
    elif d["change_1w"] < -10:
        score += 2
        reasons.append(f"падение {d['change_1w']:.1f}% за неделю")
    elif d["change_1w"] < -5:
        score += 1
        reasons.append(f"снижение {d['change_1w']:.1f}% за неделю")
    # Объём
    if d["vol_ratio"] > 2:
        score += 2
        reasons.append(f"объём x{d['vol_ratio']:.1f} от среднего")
    elif d["vol_ratio"] > 1.5:
        score += 1
        reasons.append(f"объём x{d['vol_ratio']:.1f}")
    return score, reasons

if __name__ == "__main__":
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    # Собираем тикеры из разных источников
    all_tickers = set(EXTRA)
    print("Загрузка S&P 500...")
    sp = get_sp500()
    all_tickers.update(sp)
    print(f"  S&P 500: {len(sp)} тикеров")
    
    print("Загрузка NASDAQ-100...")
    nq = get_nasdaq100()
    all_tickers.update(nq)
    print(f"  NASDAQ-100: {len(nq)} тикеров")
    
    print("Загрузка Yahoo trending...")
    ysc = get_yahoo_screener()
    all_tickers.update(ysc)
    print(f"  Yahoo trending: {len(ysc)} тикеров")
    
    tickers = sorted(all_tickers)
    print(f"\nСкрининг {len(tickers)} активов...")
    
    signals = []
    errors = 0
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(tickers)}...")
        d = get_indicators(ticker)
        if not d:
            errors += 1
            continue
        score, reasons = score_stock(d)
        if score >= 4:
            signals.append((score, ticker, d, reasons))
    
    signals.sort(reverse=True)
    print(f"\nНайдено {len(signals)} сигналов (ошибок: {errors})")
    
    # Сохраняем результаты
    results = []
    for score, ticker, d, reasons in signals[:15]:
        results.append({
            "ticker": ticker, "score": score,
            "price": round(d["price"], 2),
            "rsi": round(d["rsi"], 1),
            "change_1d": round(d["change_1d"], 2),
            "change_1w": round(d["change_1w"], 2),
            "reasons": reasons
        })
    
    with open("screener_results.json", "w") as rf:
        json.dump({"date": now, "count": len(signals), "total": len(tickers), "results": results}, rf, ensure_ascii=False, indent=2)
    
    if signals:
        lines = [f"🔍 <b>Скрининг рынка {now}</b>\n"]
        lines.append(f"Проверено {len(tickers)} активов, найдено {len(signals)} сигналов:\n")
        for score, ticker, d, reasons in signals[:10]:
            stars = "⭐" * min(score, 5)
            lines.append(f"{stars} <b>{ticker}</b>")
            lines.append(f"   Цена: {d['price']:.2f} | RSI={d['rsi']:.0f} | 1д: {d['change_1d']:+.1f}% | 1нед: {d['change_1w']:+.1f}%")
            lines.append(f"   📋 {', '.join(reasons)}\n")
        lines.append("💡 Информация для анализа, не торговый совет!")
        send("\n".join(lines))
        print("Отправлено в Telegram!")
    else:
        send(f"🔍 <b>Скрининг {now}</b>\n\nСильных сигналов не найдено. Рынок в нейтральной зоне.")
        print("Сигналов нет")
