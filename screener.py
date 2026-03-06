import os, requests, yfinance as yf
from datetime import datetime

with open(os.path.expanduser("~/.streamlit/secrets.toml")) as f:
    for line in f:
        if "=" in line:
            key, val = line.strip().split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"')

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

# Топ акции для скрининга
UNIVERSE = [
    # Технологии
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "CRM", "ADBE", "ORCL",
    # Финансы
    "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "SQ",
    # Здравоохранение
    "JNJ", "PFE", "MRK", "ABBV", "UNH",
    # Потребительские
    "AMZN", "TSLA", "NKE", "MCD", "SBUX", "KO", "PG",
    # Энергетика
    "XOM", "CVX", "BP",
    # Финтех/Рост
    "SOFI", "AFRM", "UPST", "COIN",
    # ETF крипто
    "BTC-USD", "ETH-USD", "SOL-USD",
    # Европейские ETF
    "VGWL.DE", "CSPX.L",
]

def get_indicators(ticker):
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if len(h) < 20:
            return None
        h['MA20'] = h['Close'].rolling(20).mean()
        h['MA50'] = h['Close'].rolling(50).mean()
        delta = h['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        h['RSI'] = 100 - (100 / (1 + gain / loss))
        l = h.iloc[-1]
        prev = h.iloc[-2]
        week_ago = h.iloc[-6] if len(h) >= 6 else h.iloc[0]
        return {
            "price": l['Close'],
            "rsi": l['RSI'],
            "ma20": l['MA20'],
            "ma50": l['MA50'],
            "change_1d": (l['Close'] - prev['Close']) / prev['Close'] * 100,
            "change_1w": (l['Close'] - week_ago['Close']) / week_ago['Close'] * 100,
            "above_ma50": l['Close'] > l['MA50'],
            "volume": l['Volume'],
            "avg_volume": h['Volume'].mean(),
        }
    except:
        return None

def score_stock(d):
    score = 0
    reasons = []
    
    # RSI перепродан
    if d['rsi'] < 25:
        score += 3
        reasons.append(f"RSI={d['rsi']:.0f} (сильно перепродан)")
    elif d['rsi'] < 35:
        score += 2
        reasons.append(f"RSI={d['rsi']:.0f} (перепродан)")
    
    # Выше MA50 (восходящий тренд)
    if d['above_ma50']:
        score += 1
        reasons.append("выше MA50")
    
    # Падение за неделю (возможный отскок)
    if d['change_1w'] < -10:
        score += 2
        reasons.append(f"падение {d['change_1w']:.1f}% за неделю")
    elif d['change_1w'] < -5:
        score += 1
        reasons.append(f"падение {d['change_1w']:.1f}% за неделю")
    
    # Высокий объём
    if d['volume'] > d['avg_volume'] * 1.5:
        score += 1
        reasons.append("объём +50% от среднего")
    
    return score, reasons

now = datetime.now().strftime("%d.%m.%Y %H:%M")
print(f"Скрининг {len(UNIVERSE)} активов...")

signals = []
for ticker in UNIVERSE:
    d = get_indicators(ticker)
    if not d:
        continue
    score, reasons = score_stock(d)
    if score >= 3:  # Только сильные сигналы
        signals.append((score, ticker, d, reasons))

# Сортируем по силе сигнала
signals.sort(reverse=True)

if signals:
    lines = [f"🔍 <b>Скрининг рынка {now}</b>\n"]
    lines.append(f"Проверено {len(UNIVERSE)} активов, найдено {len(signals)} сигналов:\n")
    
    for score, ticker, d, reasons in signals[:8]:  # Топ 8
        stars = "⭐" * min(score, 5)
        lines.append(f"{stars} <b>{ticker}</b>")
        lines.append(f"   Цена: {d['price']:.2f} | RSI={d['rsi']:.0f} | 1д: {d['change_1d']:+.1f}%")
        lines.append(f"   📋 {', '.join(reasons)}\n")
    
    lines.append("💡 Это информация для анализа, не торговый совет!")
    # Сохраняем результаты
    import json as jjson
    results = []
    for score, ticker, d, reasons in signals[:8]:
        results.append({"ticker": ticker, "score": score, "price": d["price"], "rsi": d["rsi"], "change_1d": d["change_1d"], "reasons": reasons})
    with open("screener_results.json","w") as rf:
        jjson.dump({"date": now, "count": len(signals), "total": len(UNIVERSE), "results": results}, rf, ensure_ascii=False, indent=2)
    send("\n".join(lines))
    print(f"Отправлено {len(signals)} сигналов!")
else:
    print("Сигналов не найдено")
    send(f"🔍 <b>Скрининг {now}</b>\n\nСильных сигналов не найдено. Рынок в нейтральной зоне.")
