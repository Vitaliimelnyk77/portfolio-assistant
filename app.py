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
from streamlit_autorefresh import st_autorefresh

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
HISTORY_FILE = "chat_history.json"
PORTFOLIO_FILE = "portfolio.json"

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

def now_str():
    return datetime.now().strftime("%H:%M  %d.%m")

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
        return json.load(open(PORTFOLIO_FILE))
    except:
        return None

def save_portfolio(portfolio):
    portfolio["updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

def card(name, price, open_price, volume, eur_pln=4.22, cost_pln=None, currency="EUR", usd_pln=3.57, stop_loss=None, take_profit=None):
    pct = (price - open_price) / open_price * 100
    rate = usd_pln if currency == "USD" else eur_pln
    if cost_pln:
        pl = price * volume * rate - cost_pln
    else:
        pl = (price - open_price) * volume * rate
    color = "#00c853" if pct >= 0 else "#ff1744"
    arrow = "▲" if pct >= 0 else "▼"
    sl_html = ""
    if stop_loss or take_profit:
        sl_parts = []
        if stop_loss:
            sl_dist = (price - stop_loss) / price * 100
            sl_parts.append(f"<span style='color:#ff1744;'>SL: {stop_loss:.2f} ({sl_dist:.1f}%)</span>")
        if take_profit:
            tp_dist = (take_profit - price) / price * 100
            sl_parts.append(f"<span style='color:#00c853;'>TP: {take_profit:.2f} ({tp_dist:+.1f}%)</span>")
        sl_html = f"<div style='font-size:11px;margin-top:4px;'>{' &nbsp;|&nbsp; '.join(sl_parts)}</div>"
    return f"""
    <div style='background:#f8f9fa;padding:14px;border-radius:10px;border-left:4px solid {color};margin-bottom:8px;'>
        <div style='color:#555;font-size:12px;margin-bottom:4px;'>{name}</div>
        <div style='color:#222;font-size:18px;font-weight:bold;'>{price:.2f} <span style='font-size:12px;color:#999;'>{currency}</span></div>
        <div style='color:{color};font-size:13px;'>{arrow} {pct:+.2f}% &nbsp; P&L: {pl:+.2f} PLN</div>
        {sl_html}
    </div>
    """

st.markdown("""
<style>
.chat-container { height: 500px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 12px; padding: 16px; background: #fafafa; display: flex; flex-direction: column; margin-bottom: 8px; }
.msg-user { background: #1976d2; color: white; padding: 10px 14px; border-radius: 18px 18px 4px 18px; margin: 4px 0 4px 20%; font-size: 14px; word-wrap: break-word; }
.msg-assistant { background: white; color: #222; padding: 10px 14px; border-radius: 18px 18px 18px 4px; margin: 4px 20% 4px 0; font-size: 14px; border: 1px solid #e8e8e8; word-wrap: break-word; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = load_history()
client = Groq(api_key=GROQ_API_KEY)
st.set_page_config(page_title="Инвестиционный помощник", page_icon="💼", layout="wide")
st_autorefresh(interval=5*60*1000, limit=None, key="auto_refresh")
portfolio = load_portfolio()

if portfolio:
    eur_pln, usd_pln = get_rates()
    ike_cash = portfolio["accounts"].get("IKE", {}).get("cash", 0)
    tr_cash = portfolio["accounts"].get("Transakcje", {}).get("cash", 0)
    ike_positions_val = 0
    tr_positions_val = 0
    for p in portfolio["positions"]:
        pr = get_price(p["ticker"])
        if pr:
            rate = usd_pln if p.get("currency") == "USD" else eur_pln
            val = pr * p["volume"] * rate
            if p["account"] == "IKE":
                ike_positions_val += val
            else:
                tr_positions_val += val
    ike_bal = ike_positions_val + ike_cash
    tr_bal = tr_positions_val + tr_cash
    total = ike_bal + tr_bal
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#42a5f5,#1e88e5);padding:20px;border-radius:14px;margin-bottom:16px;'>
        <div style='color:rgba(255,255,255,0.7);font-size:26px;'>Общий баланс портфеля</div>
        <div style='color:{"#00c853" if total >= portfolio.get("initial_capital", 0) else "#ff1744"};font-size:38px;font-weight:bold;margin:4px 0;'>{total:,.2f} PLN</div>
        <div style='color:{"#00c853" if total >= portfolio.get("initial_capital", 0) else "#ff1744"};font-size:48px;margin-top:6px;'>{"▲" if total >= portfolio.get("initial_capital", 0) else "▼"} P&L: {total - portfolio.get("initial_capital", 0):+,.2f} PLN ({(total - portfolio.get("initial_capital", 0)) / portfolio.get("initial_capital", 1) * 100:+.2f}%)</div>
        <div style='display:flex;gap:24px;margin-top:8px;'>
            <div><span style='color:rgba(255,255,255,0.7);font-size:24px;'>IKE</span><br><span style='color:white;font-size:32px;'>{ike_bal:,.2f} PLN</span></div>
            <div><span style='color:rgba(255,255,255,0.7);font-size:24px;'>Transakcje</span><br><span style='color:white;font-size:32px;'>{tr_bal:,.2f} PLN</span></div>
            <div><span style='color:rgba(255,255,255,0.7);font-size:24px;'>EUR/PLN</span><br><span style='color:white;font-size:32px;'>{eur_pln:.4f}</span></div>
            <div><span style='color:rgba(255,255,255,0.7);font-size:24px;'>USD/PLN</span><br><span style='color:white;font-size:32px;'>{usd_pln:.4f}</span></div>
        </div>
        <div style='color:rgba(255,255,255,0.5);font-size:20px;margin-top:16px;'>Обновлено: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}</div>
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
                st.markdown(card(p["name"], price, p["open_price"], p["volume"], eur_pln, p.get("cost_pln"), p.get("currency", "EUR"), usd_pln, p.get("stop_loss"), p.get("take_profit")), unsafe_allow_html=True)
        st.markdown(f"<div style='color:#888;font-size:12px;'>Свободные средства: {portfolio['accounts']['IKE']['cash']:.2f} PLN</div>", unsafe_allow_html=True)
    with col_tr:
        st.markdown("#### 💼 Moje Transakcje")
        for p in tr_positions:
            price = get_price(p["ticker"])
            if price:
                prices[p["name"]] = price
                st.markdown(card(p["name"], price, p["open_price"], p["volume"], eur_pln, p.get("cost_pln"), p.get("currency", "USD"), usd_pln, p.get("stop_loss"), p.get("take_profit")), unsafe_allow_html=True)
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
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name=selected, line=dict(color="#1976d2", width=2), fill="tozeroy", fillcolor="rgba(25,118,210,0.1)"))
            sel_pos = next((p for p in all_positions if p["name"] == selected), None)
            if sel_pos:
                if sel_pos.get("stop_loss"):
                    fig.add_hline(y=sel_pos["stop_loss"], line_dash="dash", line_color="#ff1744", annotation_text=f"SL: {sel_pos['stop_loss']:.2f}")
                if sel_pos.get("take_profit"):
                    fig.add_hline(y=sel_pos["take_profit"], line_dash="dash", line_color="#00c853", annotation_text=f"TP: {sel_pos['take_profit']:.2f}")
                if sel_pos.get("open_price"):
                    fig.add_hline(y=sel_pos["open_price"], line_dash="dot", line_color="#ff9800", annotation_text=f"Entry: {sel_pos['open_price']:.2f}")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=250, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#f0f0f0"), plot_bgcolor="white", paper_bgcolor="white")
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
    st.markdown("#### ✏️ Управление позициями")
    action = st.selectbox("Действие", ["➕ Добавить", "✏️ Изменить", "❌ Удалить"], key="pos_action")
    if action == "➕ Добавить":
        with st.form("add_position", clear_on_submit=True):
            new_name = st.text_input("Название", placeholder="Apple")
            new_ticker = st.text_input("Тикер Yahoo", placeholder="AAPL")
            new_account = st.selectbox("Счёт", ["Transakcje", "IKE"])
            new_volume = st.number_input("Количество", min_value=0.0001, step=0.01, format="%.4f")
            new_open = st.number_input("Цена входа", min_value=0.01, step=0.01, format="%.2f")
            new_currency = st.selectbox("Валюта", ["USD", "EUR"])
            new_cost = st.number_input("Стоимость (PLN)", min_value=0.0, step=1.0, format="%.2f")
            new_sl = st.number_input("Стоп-лосс", min_value=0.0, step=0.01, format="%.2f", value=0.0)
            new_tp = st.number_input("Тейк-профит", min_value=0.0, step=0.01, format="%.2f", value=0.0)
            submitted = st.form_submit_button("✅ Добавить позицию", use_container_width=True)
            if submitted and new_ticker and new_volume > 0:
                new_pos = {"name": new_name or new_ticker.upper(), "ticker": new_ticker.upper(), "volume": new_volume, "open_price": new_open, "account": new_account, "currency": new_currency, "cost_pln": new_cost if new_cost > 0 else new_open * new_volume * (3.57 if new_currency == "USD" else 4.22), "stop_loss": new_sl if new_sl > 0 else None, "take_profit": new_tp if new_tp > 0 else None}
                portfolio["positions"].append(new_pos)
                save_portfolio(portfolio)
                st.success(f"✅ {new_pos['name']} добавлен!")
                st.rerun()
    elif action == "✏️ Изменить":
        portfolio = load_portfolio()
        if portfolio and portfolio["positions"]:
            pos_names = [f"{p['name']} ({p['account']})" for p in portfolio["positions"]]
            sel_idx = st.selectbox("Позиция", range(len(pos_names)), format_func=lambda i: pos_names[i], key="edit_sel")
            p = portfolio["positions"][sel_idx]
            with st.form("edit_position"):
                ed_volume = st.number_input("Количество", value=p["volume"], step=0.01, format="%.4f")
                ed_open = st.number_input("Цена входа", value=p["open_price"], step=0.01, format="%.2f")
                ed_cost = st.number_input("Стоимость (PLN)", value=p.get("cost_pln", 0.0), step=1.0, format="%.2f")
                ed_sl = st.number_input("Стоп-лосс", value=p.get("stop_loss") or 0.0, step=0.01, format="%.2f")
                ed_tp = st.number_input("Тейк-профит", value=p.get("take_profit") or 0.0, step=0.01, format="%.2f")
                submitted = st.form_submit_button("💾 Сохранить", use_container_width=True)
                if submitted:
                    portfolio["positions"][sel_idx].update({"volume": ed_volume, "open_price": ed_open, "cost_pln": ed_cost, "stop_loss": ed_sl if ed_sl > 0 else None, "take_profit": ed_tp if ed_tp > 0 else None})
                    save_portfolio(portfolio)
                    st.success(f"💾 {p['name']} обновлён!")
                    st.rerun()
    elif action == "❌ Удалить":
        portfolio = load_portfolio()
        if portfolio and portfolio["positions"]:
            pos_names = [f"{p['name']} ({p['account']})" for p in portfolio["positions"]]
            del_idx = st.selectbox("Позиция", range(len(pos_names)), format_func=lambda i: pos_names[i], key="del_sel")
            if st.button("🗑️ Удалить позицию", use_container_width=True, type="primary"):
                removed = portfolio["positions"].pop(del_idx)
                save_portfolio(portfolio)
                st.success(f"🗑️ {removed['name']} удалён!")
                st.rerun()

    st.markdown("---")
    st.markdown("#### 💰 Обновить баланс")
    with st.form("update_balance"):
        bal_account = st.selectbox("Счёт", ["IKE", "Transakcje"], key="bal_acc")
        bal_balance = st.number_input("Баланс (PLN)", min_value=0.0, step=10.0, format="%.2f")
        bal_cash = st.number_input("Свободные средства (PLN)", min_value=0.0, step=1.0, format="%.2f")
        bal_submit = st.form_submit_button("💾 Обновить", use_container_width=True)
        if bal_submit:
            portfolio = load_portfolio()
            if bal_balance > 0:
                portfolio["accounts"][bal_account]["balance"] = bal_balance
            portfolio["accounts"][bal_account]["cash"] = bal_cash
            save_portfolio(portfolio)
            st.success(f"💰 {bal_account} обновлён!")
            st.rerun()
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
            st.image(s, width=300)
            s.seek(0)
            images.append({"data": base64.b64encode(s.read()).decode(), "type": s.type})
        st.session_state.screenshots = images
        try:
            vc = Groq(api_key=GROQ_API_KEY)
            ic = []
            for img in images:
                mt = img["type"] if "/" in img["type"] else "image/" + img["type"]
                ic.append({"type": "image_url", "image_url": {"url": "data:" + mt + ";base64," + img["data"]}})
            ic.append({"type": "text", "text": "Analyze screenshot. If broker - extract all positions, prices, P&L. If chart - describe trend, support/resistance levels. Answer in Russian."})
            vr = vc.chat.completions.create(model="meta-llama/llama-4-scout-17b-16e-instruct", messages=[{"role": "user", "content": ic}], max_tokens=1500)
            st.session_state.screenshot_analysis = vr.choices[0].message.content
            st.session_state.messages.append({"role": "user", "content": "Анализ скриншота", "time": now_str()})
            st.session_state.messages.append({"role": "assistant", "content": vr.choices[0].message.content, "time": now_str()})
            save_history(st.session_state.messages)
            st.rerun()
        except Exception as e:
            st.error("Vision error: " + str(e))
    st.markdown("---")
    commands = {"📊 Портфель": "/портфель", "🔍 Скрининг": "/сигналы скрининга", "🎯 Сигналы": "/сигналы", "🌍 Рынок": "/рынок", "⚠️ Риски": "/риски", "🔄 Ребаланс": "/ребаланс", "🎯 Стратегия": "/стратегия", "₿ Крипто": "/крипто"}
    for label, command in commands.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_command = command
    if st.button("🗑️ Очистить чат", use_container_width=True):
        st.session_state.messages = []
        save_history([])
        st.rerun()

with col2:
    st.markdown("### 💬 Чат с помощником")
    if "quick_command" in st.session_state:
        prompt = st.session_state.pop("quick_command")
    else:
        prompt = st.chat_input("Введите сообщение или команду...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt, "time": now_str()})
        with st.spinner("Анализирую..."):
            system = get_system_prompt()
            if "xtb_data" in st.session_state:
                system += f"\n\nДАННЫЕ ПОРТФЕЛЯ XTB:\n{st.session_state.xtb_data}"
            if "screenshot_analysis" in st.session_state:
                system += f"\n\nАНАЛИЗ СКРИНШОТОВ:\n{st.session_state.screenshot_analysis}"
            messages_api = [{"role": "system", "content": system}]
            for m in st.session_state.messages[-6:]:
                if isinstance(m["content"], str):
                    messages_api.append({"role": m["role"], "content": m["content"]})
            response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages_api, max_tokens=2048)
            reply = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": reply, "time": now_str()})
        save_history(st.session_state.messages)
        st.rerun()
    for message in st.session_state.messages[-20:]:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for block in message["content"]:
                    if block["type"] == "text":
                        st.markdown(block["text"])
            else:
                st.markdown(message["content"])
            ts = message.get("time", "")
            if ts:
                st.caption(ts)
