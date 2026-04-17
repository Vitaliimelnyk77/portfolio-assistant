#!/usr/bin/env python3
import os, json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv("/root/portfolio-assistant/.env")

PORTFOLIO_FILE = "/root/portfolio-assistant/portfolio.json"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

def send_telegram(text):
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_price(ticker):
    import finnhub
    try:
        c = finnhub.Client(api_key=FINNHUB_KEY)
        q = c.quote(ticker)
        if q and q.get("c", 0) > 0:
            return q["c"]
    except:
        pass
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
        ticker = pos["ticker"]
        if "." in ticker:
            remaining.append(pos)
            continue
        price = get_price(ticker)
        if not price:
            remaining.append(pos)
            print(f"No price for {ticker}")
            continue
        print(f"{ticker}: price={price:.2f}, SL={sl}, TP={tp}")
        triggered = None
        if sl and price <= sl:
            triggered = "STOP-LOSS"
            trig_val = sl
        elif tp and price >= tp:
            triggered = "TAKE-PROFIT"
            trig_val = tp
        if triggered:
            rate = 3.59 if pos.get("currency") == "USD" else 4.23
            cost = pos.get("cost_pln", pos["open_price"] * pos["volume"] * rate)
            current_val = price * pos["volume"] * rate
            pl = current_val - cost
            pct = (price - pos["open_price"]) / pos["open_price"] * 100
            emoji = "\U0001f534" if triggered == "STOP-LOSS" else "\U0001f7e2"
            msg = f"{emoji} <b>{triggered}: {pos['name']}</b>\nPrice: ${price:.2f} (trigger: ${trig_val:.2f})\nEntry: ${pos['open_price']:.2f} | P&L: {pl:+.2f} PLN ({pct:+.1f}%)\nAccount: {pos['account']}"
            send_telegram(msg)
            print(f"{triggered}: {pos['name']} @ {price:.2f}")
            closed.append(pos["name"])
        else:
            remaining.append(pos)
            if sl:
                dist = (price - sl) / price * 100
                if dist < 5:
                    msg = f"Warning: <b>{pos['name']}</b> near SL!\nPrice: ${price:.2f} | SL: ${sl:.2f} ({dist:.1f}% left)"
                    send_telegram(msg)
                    print(f"WARNING: {pos['name']} close to SL ({dist:.1f}%)")
            if tp:
                dist = (tp - price) / price * 100
                if dist < 5:
                    msg = f"Target: <b>{pos['name']}</b> near TP!\nPrice: ${price:.2f} | TP: ${tp:.2f} ({dist:.1f}% left)"
                    send_telegram(msg)
                    print(f"ALERT: {pos['name']} close to TP ({dist:.1f}%)")
    if closed:
        portfolio["positions"] = remaining
        portfolio["updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)
        print(f"Closed: {", ".join(closed)}")

if __name__ == "__main__":
    main()
