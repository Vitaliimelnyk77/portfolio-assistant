import os, requests, anthropic, yfinance as yf
from datetime import datetime

with open(os.path.expanduser("~/.streamlit/secrets.toml")) as f:
    for line in f:
        if "=" in line:
            key, val = line.strip().split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"')

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
KEY = os.environ["ANTHROPIC_API_KEY"]

PORTFOLIO = {
    "CHAINLINK": {"ticker": "LINK-USD", "volume": 8, "open_price": 12.715},
    "SXR8.DE": {"ticker": "SXR8.DE", "volume": 0.0327, "open_price": 627.94},
    "EUNL.DE": {"ticker": "EUNL.DE", "volume": 0.1386, "open_price": 110.925},
    "SXRV.DE": {"ticker": "SXRV.DE", "volume": 0.0036, "open_price": 1250.0},
    "BTC": {"ticker": "BTC-USD", "volume": 0.0, "open_price": 0},
}

WATCHLIST = ["PLTR", "SOFI", "F", "BAC", "NVDA", "MSFT", "VGWL.DE", "BTC-USD", "LINK-USD"]

def send(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

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
            "ma20": l['MA20'],
            "ma50": l['MA50'],
            "rsi": l['RSI'],
            "volume": l['Volume'],
            "change_pct": (l['Close'] - prev['Close']) / prev['Close'] * 100,
            "above_ma50": l['Close'] > l['MA50'],
            "above_ma20": l['Close'] > l['MA20'],
        }
    except:
        return None

def get_signal(name, d):
    signals = []
    if d['rsi'] < 35 and d['above_ma50']:
        signals.append("🟢 ПОКУПКА: RSI перепродан + выше MA50")
    elif d['rsi'] < 30:
        signals.append("🟢 ПОКУПКА: RSI сильно перепродан")
    elif d['rsi'] > 70 and not d['above_ma50']:
        signals.append("🔴 ПРОДАЖА: RSI перекуплен + ниже MA50")
    elif d['rsi'] > 65:
        signals.append("🟡 ОСТОРОЖНО: RSI перекуплен")
    else:
        signals.append("⚪ НАБЛЮДЕНИЕ: нет чёткого сигнала")
    return signals[0]

def get_portfolio_data():
    lines = ["<b>📊 Портфель:</b>"]
    total_pl = 0
    for name, data in PORTFOLIO.items():
        if data['volume'] == 0:
            continue
        d = get_indicators(data['ticker'])
        if d:
            pl = (d['price'] - data['open_price']) * data['volume']
            total_pl += pl
            lines.append(f"{'🟢' if pl > 0 else '🔴'} {name}: ${d['price']:.2f} | P&L: {pl:+.2f} PLN | RSI={d['rsi']:.0f}")
        else:
            lines.append(f"⚪ {name}: нет данных")
    lines.append(f"\n<b>Общий P&L: {total_pl:+.2f} PLN</b>")
    return "\n".join(lines)

def get_market_signals():
    lines = ["<b>🎯 Торговые сигналы (Watchlist):</b>"]
    opportunities = []
    for sym in WATCHLIST:
        d = get_indicators(sym)
        if not d:
            continue
        signal = get_signal(sym, d)
        change = f"{d['change_pct']:+.1f}%"
        lines.append(f"{signal}\n   {sym}: ${d['price']:.2f} ({change}) | RSI={d['rsi']:.0f}")
        if "ПОКУПКА" in signal:
            opportunities.append((sym, d))
    return "\n".join(lines), opportunities

def get_ai_analysis(portfolio, signals, opportunities):
    opp_text = ""
    if opportunities:
        opp_text = "\n\nПотенциальные возможности для покупки:\n"
        for sym, d in opportunities:
            opp_text += f"- {sym}: ${d['price']:.2f}, RSI={d['rsi']:.0f}\n"

    client = anthropic.Anthropic(api_key=KEY)
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": f"""Ты инвестиционный ассистент. Профиль инвестора: умеренный, горизонт 5+ лет, цель — пассивный доход, бюджет для трейдинга 300 PLN.

Портфель:
{portfolio}

Рыночные сигналы:
{signals}
{opp_text}

Дай краткий анализ (4-5 предложений):
1. Состояние портфеля
2. Лучшая возможность для трейдинга прямо сейчас (если есть)
3. На что обратить внимание сегодня"""}]
    )
    return resp.content[0].text

now = datetime.now().strftime("%d.%m.%Y %H:%M")
portfolio = get_portfolio_data()
signals_text, opportunities = get_market_signals()
analysis = get_ai_analysis(portfolio, signals_text, opportunities)

send(f"🤖 <b>Автоанализ {now}</b>\n\n{portfolio}\n\n{signals_text}\n\n💡 <b>ИИ:</b>\n{analysis}")
print("Готово!")
