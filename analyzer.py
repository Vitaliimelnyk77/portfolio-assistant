import os, requests, json, yfinance as yf
from groq import Groq
from datetime import datetime

with open(os.path.expanduser("~/.streamlit/secrets.toml")) as f:
    for line in f:
        if "=" in line:
            key, val = line.strip().split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"')

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

WATCHLIST = ["SOFI", "NVDA", "GOOGL", "BTC-USD", "VGWL.DE"]

def send(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def load_portfolio():
    try:
        return json.load(open("portfolio.json"))
    except:
        return None

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
        return {
            "price": l['Close'],
            "rsi": l['RSI'],
            "change_pct": (l['Close'] - prev['Close']) / prev['Close'] * 100,
            "above_ma50": l['Close'] > l['MA50'],
        }
    except:
        return None

def get_signal(d):
    if d['rsi'] < 35 and d['above_ma50']:
        return "🟢 ПОКУПКА: RSI перепродан + выше MA50"
    elif d['rsi'] < 30:
        return "🟢 ПОКУПКА: RSI сильно перепродан"
    elif d['rsi'] > 70 and not d['above_ma50']:
        return "🔴 ПРОДАЖА: RSI перекуплен + ниже MA50"
    elif d['rsi'] > 65:
        return "🟡 ОСТОРОЖНО: RSI перекуплен"
    else:
        return "⚪ НАБЛЮДЕНИЕ"

def get_portfolio_data():
    portfolio = load_portfolio()
    if not portfolio:
        return "Портфель не загружен"
    
    try:
        eur_pln = yf.Ticker("EURPLN=X").fast_info.last_price
        usd_pln = yf.Ticker("USDPLN=X").fast_info.last_price
    except:
        eur_pln, usd_pln = 4.22, 3.57

    lines = ["<b>📊 Портфель IKE:</b>"]
    for p in portfolio["positions"]:
        if p["volume"] == 0:
            continue
        d = get_indicators(p["ticker"])
        if d:
            pct = (d['price'] - p['open_price']) / p['open_price'] * 100
            rate = usd_pln if p.get("currency") == "USD" else eur_pln
            cost = p.get("cost_pln", p['open_price'] * p['volume'] * rate)
            pl = d['price'] * p['volume'] * rate - cost
            icon = "🟢" if pl > 0 else "🔴"
            lines.append(f"{icon} {p['name']}: {d['price']:.2f} ({pct:+.1f}%) | P&L: {pl:+.2f} PLN | RSI={d['rsi']:.0f}")
    
    ike_bal = portfolio["accounts"].get("IKE", {}).get("balance", 0)
    tr_bal = portfolio["accounts"].get("Transakcje", {}).get("balance", 0)
    lines.append(f"\n💰 IKE: {ike_bal:.2f} PLN | Transakcje: {tr_bal:.2f} PLN")
    lines.append(f"💱 EUR/PLN: {eur_pln:.4f} | USD/PLN: {usd_pln:.4f}")
    return "\n".join(lines)

def get_market_signals():
    lines = ["<b>🎯 Сигналы Watchlist:</b>"]
    opportunities = []
    for sym in WATCHLIST:
        d = get_indicators(sym)
        if not d:
            continue
        signal = get_signal(d)
        lines.append(f"{signal}\n   {sym}: {d['price']:.2f} ({d['change_pct']:+.1f}%) | RSI={d['rsi']:.0f}")
        if "ПОКУПКА" in signal:
            opportunities.append((sym, d))
    return "\n".join(lines), opportunities

def get_ai_analysis(portfolio_text, signals, opportunities):
    opp_text = ""
    if opportunities:
        opp_text = "\nВозможности для покупки:\n" + "\n".join([f"- {s}: {d['price']:.2f}, RSI={d['rsi']:.0f}" for s, d in opportunities])

    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=500,
        messages=[{"role": "user", "content": f"""Инвестиционный ассистент. Профиль: умеренный, горизонт 5+ лет, бюджет 300 PLN.

{portfolio_text}

{signals}
{opp_text}

Дай краткий анализ (3-4 предложения): состояние портфеля, лучшая возможность сейчас, на что обратить внимание."""}]
    )
    return resp.choices[0].message.content

now = datetime.now().strftime("%d.%m.%Y %H:%M")
portfolio_text = get_portfolio_data()
signals_text, opportunities = get_market_signals()
analysis = get_ai_analysis(portfolio_text, signals_text, opportunities)

send(f"🤖 <b>Автоанализ {now}</b>\n\n{portfolio_text}\n\n{signals_text}\n\n💡 <b>ИИ:</b>\n{analysis}")
print("Готово!")
