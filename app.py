import streamlit as st
import base64
import json
import os
from datetime import datetime
from groq import Groq
from xtb_parser import parse_xtb_file
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
HISTORY_FILE = "chat_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(messages):
    to_save = [m for m in messages if isinstance(m["content"], str)]
    with open(HISTORY_FILE, "w") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

def get_system_prompt():
    system = open("system_prompt.txt", "r", encoding="utf-8").read()
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
                system += f"- {s['ticker']}: цена={s['price']:.2f} USD, RSI={s['rsi']:.0f}, изм. за неделю={s['change_1w']:.1f}%, {chr(44).join(s['reasons'])}\n"
    except:
        pass
    return system

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

def get_history_chart(ticker, period="1mo"):
    try:
        return yf.Ticker(ticker).history(period=period)
    except:
        return None

def load_portfolio():
    try:
        return json.load(open("portfolio.json"))
    except:
        return None

def card(name, price, open_price, volume, eur_pln=4.22, cost_pln=None, currency="EUR", usd_pln=3.57):
    pct = (price - open_price) / open_price * 100
    if cost_pln:
        rate = usd_pln if currency == "USD" else eur_pln
        pl = price * volume * rate - cost_pln
    else:
        pl = (price - open_price) * volume * eur_pln
    color = "#00c853" if pct >= 0 else "#ff1744"
    arrow = "▲" if pct >= 0 else "▼"
    return f"""
    <div style='background:#f8f9fa;padding:14px;border-radius:10px;border-left:4px solid {color};margin-bottom:8px;'>
        <div style='color:#555;font-size:12px;margin-bottom:4px;'>{name}</div>
        <div style='color:#222;font-size:18px;font-weight:bold;'>{price:.2f}</div>
        <div style='color:{color};font-size:13px;'>{arrow} {pct:+.2f}% &nbsp; P&L: {pl:+.2f} PLN</div>
    </div>
    """

# CSS для фиксированного чата
st.markdown("""
<style>
.chat-container {
    height: 500px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 16px;
    background: #fafafa;
    display: flex;
    flex-direction: column;
    margin-bottom: 8px;
}
.msg-user {
    background: #1976d2;
    color: white;
    padding: 10px 14px;
    border-radius: 18px 18px 4px 18px;
    margin: 4px 0 4px 20%;
    font-size: 14px;
    word-wrap: break-word;
}
.msg-assistant {
    background: white;
    color: #222;
    padding: 10px 14px;
    border-radius: 18px 18px 18px 4px;
    margin: 4px 20% 4px 0;
    font-size: 14px;
    border: 1px solid #e8e8e8;
    word-wrap: break-word;
    white-space: pre-wrap;
}
.msg-time {
    font-size: 10px;
    color: #aaa;
    margin: 2px 4px;
}
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

client = Groq(api_key=GROQ_API_KEY)
st.set_page_config(page_title="Инвестиционный помощник", page_icon="💼", layout="wide")

portfolio = load_portfolio()

if portfolio:
    ike_bal = portfolio["accounts"].get("IKE", {}).get("balance", 0)
    tr_bal = portfolio["accounts"].get("Transakcje", {}).get("balance", 0)
    total = ike_bal + tr_bal
    eur_pln, usd_pln = get_rates()

    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#1976d2,#1565c0);padding:20px;border-radius:14px;margin-bottom:16px;'>
        <div style='color:rgba(255,255,255,0.7);font-size:13px;'>Общий баланс портфеля</div>
        <div style='color:white;font-size:38px;font-weight:bold;margin:4px 0;'>{total:,.2f} PLN</div>
        <div style='display:flex;gap:24px;margin-top:8px;'>
            <div><span style='color:rgba(255,255,255,0.7);font-size:12px;'>IKE</span><br><span style='color:white;font-size:16px;'>{ike_bal:,.2f} PLN</span></div>
            <div><span style='color:rgba(255,255,255,0.7);font-size:12px;'>Transakcje</span><br><span style='color:white;font-size:16px;'>{tr_bal:,.2f} PLN</span></div>
            <div><span style='color:rgba(255,255,255,0.7);font-size:12px;'>EUR/PLN</span><br><span style='color:white;font-size:16px;'>{eur_pln:.4f}</span></div>
            <div><span style='color:rgba(255,255,255,0.7);font-size:12px;'>USD/PLN</span><br><span style='color:white;font-size:16px;'>{usd_pln:.4f}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_ike, col_tr = st.columns(2)
    ike_positions = [p for p in portfolio["positions"] if p["account"] == "IKE" and p["volume"] > 0]
    tr_positions = [p for p in portfolio["positions"] if p["account"] == "Transakcje" and p["volume"] > 0]
    prices = {}

    with col_ike:
        st.markdown("#### 🏦 IKE")
        for p in ike_positions:
            price = get_price(p["ticker"])
            if price:
                prices[p["name"]] = price
                st.markdown(card(p["name"], price, p["open_price"], p["volume"], eur_pln, p.get("cost_pln"), p.get("currency", "EUR"), usd_pln), unsafe_allow_html=True)
        st.markdown(f"<div style='color:#888;font-size:12px;'>Свободные средства: {portfolio['accounts']['IKE']['cash']:.2f} PLN</div>", unsafe_allow_html=True)

    with col_tr:
        st.markdown("#### 💼 Moje Transakcje")
        for p in tr_positions:
            price = get_price(p["ticker"])
            if price:
                prices[p["name"]] = price
                st.markdown(card(p["name"], price, p["open_price"], p["volume"], eur_pln, p.get("cost_pln"), p.get("currency", "USD"), usd_pln), unsafe_allow_html=True)
        st.markdown(f"<div style='color:#888;font-size:12px;'>Свободные средства: {portfolio['accounts']['Transakcje']['cash']:.2f} PLN</div>", unsafe_allow_html=True)

    st.markdown("---")

    col_chart1, col_chart2 = st.columns([2, 1])
    with col_chart1:
        st.markdown("#### 📈 График актива")
        all_positions = ike_positions + tr_positions
        tickers = {p["name"]: p["ticker"] for p in all_positions}
        selected = st.selectbox("Выберите актив", list(tickers.keys()))
        period = st.radio("Период", ["1mo", "3mo", "6mo", "1y"], horizontal=True)
        hist = get_history_chart(tickers[selected], period)
        if hist is not None and not hist.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name=selected,
                                     line=dict(color="#1976d2", width=2), fill="tozeroy", fillcolor="rgba(25,118,210,0.1)"))
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=250,
                              xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
                              plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

    with col_chart2:
        st.markdown("#### 🥧 Структура IKE")
        labels, values = [], []
        for p in ike_positions:
            price = prices.get(p["name"])
            if price:
                rate = usd_pln if p.get("currency") == "USD" else eur_pln
                labels.append(p["name"])
                values.append(price * p["volume"] * rate)
        labels.append("Свободные средства")
        values.append(portfolio["accounts"]["IKE"]["cash"])
        fig2 = px.pie(values=values, names=labels, color_discrete_sequence=["#1976d2", "#ff9800", "#4caf50", "#e0e0e0"])
        fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=250)
        fig2.update_traces(textposition="inside", textinfo="percent")
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("### 🛠️ Панель")
    trade_ticker = st.text_input("Тикер", placeholder="BAC, SOFI, NVDA...")
    if st.button("📈 Торговый план", use_container_width=True):
        if trade_ticker:
            st.session_state.quick_command = f"Дай точный торговый план для {trade_ticker.upper()}: точки входа, стоп-лосс, тейк-профит 1 и 2, размер позиции из бюджета 300 PLN, соотношение риск/прибыль."
    st.markdown("---")
    uploaded_file = st.file_uploader("Файл XTB", type=["csv","xlsx","xls","zip"], key="xtb_file")
    if uploaded_file:
        parsed_text, count = parse_xtb_file(uploaded_file)
        if count > 0:
            st.success(f"Загружено {count} сделок")
            st.session_state.xtb_data = parsed_text
        else:
            st.error(parsed_text)
    screenshots = st.file_uploader("Скриншоты", type=["png","jpg","jpeg"], key="screenshot_file", accept_multiple_files=True)
    if screenshots:
        images = []
        for s in screenshots[:5]:
            st.image(s, use_column_width=True)
            s.seek(0)
            images.append({"data": base64.b64encode(s.read()).decode(), "type": s.type})
        st.session_state.screenshots = images
        st.success(f"Загружено {len(images)} фото!")
    st.markdown("---")
    commands = {
        "📊 Портфель": "/портфель",
        "🔍 Скрининг": "/сигналы скрининга",
        "🎯 Сигналы": "/сигналы",
        "🌍 Рынок": "/рынок",
        "⚠️ Риски": "/риски",
        "🔄 Ребаланс": "/ребаланс",
        "🎯 Стратегия": "/стратегия",
        "₿ Крипто": "/крипто",
    }
    for label, command in commands.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_command = command
    if st.button("🗑️ Очистить чат", use_container_width=True):
        st.session_state.messages = []
        save_history([])
        st.rerun()

with col2:
    st.markdown("### 💬 Чат с помощником")

    for message in st.session_state.messages[-20:]:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for block in message["content"]:
                    if block["type"] == "text":
                        st.markdown(block["text"])
            else:
                st.markdown(message["content"])

    # Поле ввода
    if "quick_command" in st.session_state:
        prompt = st.session_state.pop("quick_command")
    else:
        prompt = st.chat_input("Введите сообщение или команду...")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Анализирую..."):
            system = get_system_prompt()
            if "xtb_data" in st.session_state:
                system += f"\n\nДАННЫЕ ПОРТФЕЛЯ XTB:\n{st.session_state.xtb_data}"
            messages_api = [{"role": "system", "content": system}]
            for m in st.session_state.messages[-6:]:
                if isinstance(m["content"], str):
                    messages_api.append({"role": m["role"], "content": m["content"]})
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages_api,
                max_tokens=2048
            )
            reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_history(st.session_state.messages)
        st.rerun()
