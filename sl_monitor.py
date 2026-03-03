#!/usr/bin/env python3
import json, os, yfinance as yf
from datetime import datetime

PORTFOLIO_FILE = "portfolio.json"
TELEGRAM_BOT_TOKEN = "7759029855:AAH4VrpXQqHBCMzHpBmFo2_gLKGqEzTmnYw"
TELEGRAM_CHAT_ID = "882482912"

def send_telegram(text):
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info.last_price
    except:
        return None

def main():
    if not os.path.exists(PORTFOLIO_FILE):
        return
    portfolio = json.load(open(PORTFOLIO_FILE))
    closed = []
    remaining = []
    for pos in portfolio["positions"]:
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        if not sl and not tp:
            remaining.append(pos)
            continue
        price = get_price(pos["ticker"])
        if not price:
            remaining.append(pos)
            continue
        triggered = None
        if sl and price <= sl:
            triggered = "STOP-LOSS"
            trig_val = sl
        elif tp and price >= tp:
            triggered = "TAKE-PROFIT"
            trig_val = tp
        if triggered:
            rate = 3.68 if pos.get("currency") == "USD" else 4.27
            cost = pos.get("cost_pln", pos["open_price"] * pos["volume"] * rate)
            current_val = price * pos["volume"] * rate
            pl = current_val - cost
            pct = (price - pos["open_price"]) / pos["open_price"] * 100
            portfolio["accounts"][pos["account"]]["cash"] = portfolio["accounts"][pos["account"]].get("cash", 0) + current_val
            closed.append(pos["name"])
            emoji = "🔴" if triggered == "STOP-LOSS" else "🟢"
            msg = f"{emoji} <b>{triggered}: {pos['name']}</b>\nЦена: {price:.2f} (триггер: {trig_val:.2f})\nВход: {pos['open_price']:.2f} | P&L: {pl:+.2f} PLN ({pct:+.1f}%)\nСчёт: {pos['account']}\nВремя: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            send_telegram(msg)
            print(f"{triggered}: {pos['name']} @ {price:.2f}")
        else:
            remaining.append(pos)
            if sl:
                dist = (price - sl) / price * 100
                if dist < 3:
                    msg = f"⚠️ <b>{pos['name']}</b> близко к SL!\nЦена: {price:.2f} | SL: {sl:.2f} (осталось {dist:.1f}%)"
                    send_telegram(msg)
            if tp:
                dist = (tp - price) / price * 100
                if dist < 3:
                    msg = f"🎯 <b>{pos['name']}</b> близко к TP!\nЦена: {price:.2f} | TP: {tp:.2f} (осталось {dist:.1f}%)"
                    send_telegram(msg)
    if closed:
        portfolio["positions"] = remaining
        portfolio["updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)
        print(f"Closed: {', '.join(closed)}")

if __name__ == "__main__":
    main()
