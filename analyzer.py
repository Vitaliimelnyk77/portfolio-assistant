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
}

def send(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": CHAT_ID, "text": msg})

lines = ["Текущие позиции:"]
total = 0
for name, d in PORTFOLIO.items():
    try:
        price = yf.Ticker(d["ticker"]).fast_info.last_price
        pl = (price - d["open_price"]) * d["volume"]
        total += pl
        lines.append(f"{name}: {price:.2f} | P&L: {pl:+.2f}")
    except Exception as e:
        lines.append(f"{name}: нет данных ({e})")
lines.append(f"Общий P&L: {total:+.2f}")
market = "\n".join(lines)

client = anthropic.Anthropic(api_key=KEY)
resp = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=500,
    messages=[{"role": "user", "content": f"Портфель:\n{market}\n\nДай краткий анализ и одну рекомендацию."}]
)
analysis = resp.content[0].text

now = datetime.now().strftime("%d.%m.%Y %H:%M")
send(f"Автоанализ {now}\n\n{market}\n\nАнализ ИИ:\n{analysis}")
print("Готово!")
