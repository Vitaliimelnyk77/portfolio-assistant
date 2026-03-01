import os, json, requests, yfinance as yf
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

def send(msg, chat_id=None):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": chat_id or CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_offset():
    try:
        return int(open("/tmp/tg_offset.txt").read().strip())
    except:
        return 0

def save_offset(offset):
    open("/tmp/tg_offset.txt", "w").write(str(offset))

def get_updates(offset):
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                     params={"offset": offset, "timeout": 10})
    return r.json().get("result", [])

def load_portfolio():
    try:
        return json.load(open("portfolio.json"))
    except:
        return None

def get_rates():
    try:
        eur_pln = yf.Ticker("EURPLN=X").fast_info.last_price
        usd_pln = yf.Ticker("USDPLN=X").fast_info.last_price
        return eur_pln, usd_pln
    except:
        return 4.22, 3.57

def get_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info.last_price
    except:
        return None

def get_indicators(ticker):
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if len(h) < 20:
            return None
        delta = h['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        h['RSI'] = 100 - (100 / (1 + gain / loss))
        h['MA50'] = h['Close'].rolling(50).mean()
        l = h.iloc[-1]
        prev = h.iloc[-2]
        return {
            "price": l['Close'],
            "rsi": l['RSI'],
            "change_pct": (l['Close'] - prev['Close']) / prev['Close'] * 100,
            "above_ma50": bool(l['Close'] > l['MA50']),
        }
    except:
        return None

def get_system():
    system = open("system_prompt.txt").read()
    now = datetime.now().strftime("%A, %d %B %Y, %H:%M")
    system += f"\n\nСейчас: {now} (Варшава, CET)"
    try:
        eur_pln, usd_pln = get_rates()
        system += f"\n\nТЕКУЩИЕ КУРСЫ: EUR/PLN={eur_pln:.4f}, USD/PLN={usd_pln:.4f}"
    except:
        pass
    try:
        sr = json.load(open("screener_results.json"))
        if sr["signals"]:
            system += f"\n\nПОСЛЕДНИЙ СКРИНИНГ ({sr['date']}):\n"
            for s in sr["signals"][:5]:
                system += f"- {s['ticker']}: RSI={s['rsi']:.0f}, {', '.join(s['reasons'])}\n"
    except:
        pass
    return system

def cmd_portfolio(chat_id):
    portfolio = load_portfolio()
    if not portfolio:
        send("Портфель не загружен", chat_id)
        return
    eur_pln, usd_pln = get_rates()
    lines = [f"📊 <b>Портфель ({datetime.now().strftime('%d.%m.%Y %H:%M')})</b>\n"]
    lines.append("🏦 <b>IKE:</b>")
    for p in portfolio["positions"]:
        if p["account"] != "IKE" or p["volume"] == 0:
            continue
        price = get_price(p["ticker"])
        if price:
            pct = (price - p["open_price"]) / p["open_price"] * 100
            rate = usd_pln if p.get("currency") == "USD" else eur_pln
            cost = p.get("cost_pln", p["open_price"] * p["volume"] * rate)
            pl = price * p["volume"] * rate - cost
            icon = "🟢" if pl > 0 else "🔴"
            lines.append(f"{icon} {p['name']}: {price:.2f} ({pct:+.1f}%) | P&L: {pl:+.2f} PLN")
    ike_bal = portfolio["accounts"]["IKE"]["balance"]
    lines.append(f"💰 Баланс IKE: {ike_bal:.2f} PLN")
    lines.append("\n💼 <b>Moje Transakcje:</b>")
    for p in portfolio["positions"]:
        if p["account"] != "Transakcje" or p["volume"] == 0:
            continue
        price = get_price(p["ticker"])
        if price:
            pct = (price - p["open_price"]) / p["open_price"] * 100
            rate = usd_pln if p.get("currency", "USD") == "USD" else eur_pln
            cost = p.get("cost_pln", p["open_price"] * p["volume"] * rate)
            pl = price * p["volume"] * rate - cost
            icon = "🟢" if pl > 0 else "🔴"
            lines.append(f"{icon} {p['name']}: {price:.2f} ({pct:+.1f}%) | P&L: {pl:+.2f} PLN")
    tr_bal = portfolio["accounts"]["Transakcje"]["balance"]
    lines.append(f"💰 Баланс Transakcje: {tr_bal:.2f} PLN")
    lines.append(f"\n💱 EUR/PLN: {eur_pln:.4f} | USD/PLN: {usd_pln:.4f}")
    send("\n".join(lines), chat_id)

def cmd_signals(chat_id):
    WATCHLIST = ["SOFI", "NVDA", "GOOGL", "BTC-USD", "VGWL.DE", "BAC", "MA", "MSFT", "AMD", "JPM"]
    lines = [f"🎯 <b>Сигналы ({datetime.now().strftime('%d.%m %H:%M')})</b>\n"]
    buy_signals = []
    for sym in WATCHLIST:
        d = get_indicators(sym)
        if not d:
            continue
        if d['rsi'] < 30:
            signal = "🟢 ПОКУПКА"
            buy_signals.append(sym)
        elif d['rsi'] < 40 and d['above_ma50']:
            signal = "🟡 ИНТЕРЕСНО"
        elif d['rsi'] > 70:
            signal = "🔴 ПЕРЕКУПЛЕН"
        else:
            signal = "⚪ НАБЛЮДЕНИЕ"
        lines.append(f"{signal}: {sym} | {d['price']:.2f} ({d['change_pct']:+.1f}%) | RSI={d['rsi']:.0f}")
    if buy_signals:
        lines.append(f"\n🚨 Лучшие для покупки: {', '.join(buy_signals)}")
    send("\n".join(lines), chat_id)

def cmd_trade(chat_id, ticker):
    d = get_indicators(ticker)
    if not d:
        send(f"❌ Не могу получить данные по {ticker}", chat_id)
        return
    eur_pln, usd_pln = get_rates()
    budget_usd = 300 / usd_pln
    prompt = f"""Дай точный торговый план для {ticker}.
Цена: {d['price']:.2f}
RSI: {d['rsi']:.0f}
Выше MA50: {'да' if d['above_ma50'] else 'нет'}
Изменение за день: {d['change_pct']:+.1f}%
Бюджет: 300 PLN (~{budget_usd:.0f} USD)
Стиль: Swing Trading 2-14 дней, макс риск 2% (6 PLN)

Дай ТОЛЬКО в таком формате:
Вход: $XX.XX
Стоп-лосс: $XX.XX (-X%)
Тейк-профит 1: $XX.XX (+X%)
Тейк-профит 2: $XX.XX (+X%)
Размер позиции: XX акций (~XXX PLN)
Риск/Прибыль: 1:X
Обоснование: 2 предложения"""
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    send(f"📈 <b>Торговый план {ticker}</b>\n\n{resp.choices[0].message.content}", chat_id)

def cmd_ask(chat_id, question):
    system = get_system()
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=500,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question}
        ]
    )
    send(resp.choices[0].message.content, chat_id)

def cmd_analyze(chat_id, ticker):
    d = get_indicators(ticker)
    if not d:
        send(f"❌ Не могу получить данные по {ticker}", chat_id)
        return
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=400,
        messages=[{"role": "user", "content": f"Кратко проанализируй {ticker}: цена={d['price']:.2f}, RSI={d['rsi']:.0f}, выше MA50={'да' if d['above_ma50'] else 'нет'}, изменение={d['change_pct']:+.1f}%. Инвестор: цель 25-30% годовых, бюджет 300 PLN. Покупать/продавать/наблюдать? (3-4 предложения)"}]
    )
    send(f"📈 <b>Анализ {ticker}</b>\n\nЦена: {d['price']:.2f} ({d['change_pct']:+.1f}%)\nRSI: {d['rsi']:.0f}\n\n{resp.choices[0].message.content}", chat_id)

def cmd_help(chat_id):
    send("""🤖 <b>Команды бота:</b>

/портфель — текущее состояние
/сигналы — торговые сигналы
/анализ NVDA — анализ актива
/торговля BAC — точки входа/выхода
/вопрос Что думаешь о золоте? — вопрос ИИ
/помощь — список команд

📊 Автоотчёты: 8:00, 12:00, 18:00
🔍 Скрининг рынка: каждый день в 7:00""", chat_id)

def process_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text.startswith("/портфель"):
        cmd_portfolio(chat_id)
    elif text.startswith("/сигналы"):
        cmd_signals(chat_id)
    elif text.startswith("/анализ"):
        parts = text.split()
        ticker = parts[1].upper() if len(parts) > 1 else None
        if ticker:
            cmd_analyze(chat_id, ticker)
        else:
            send("Укажите тикер: /анализ NVDA", chat_id)
    elif text.startswith("/торговля"):
        parts = text.split()
        ticker = parts[1].upper() if len(parts) > 1 else None
        if ticker:
            cmd_trade(chat_id, ticker)
        else:
            send("Укажите тикер: /торговля BAC", chat_id)
    elif text.startswith("/вопрос"):
        question = text[8:].strip()
        if question:
            cmd_ask(chat_id, question)
        else:
            send("Укажите вопрос: /вопрос Что думаешь о золоте?", chat_id)
    elif text.startswith("/помощь") or text.startswith("/start"):
        cmd_help(chat_id)
    else:
        cmd_ask(chat_id, text)

offset = get_offset()
updates = get_updates(offset)
for update in updates:
    offset = update["update_id"] + 1
    if "message" in update:
        process_message(update["message"])
save_offset(offset)
