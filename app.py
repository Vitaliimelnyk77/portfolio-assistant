import streamlit as st
import base64
import json
import os
from datetime import datetime
from groq import Groq
from xtb_parser import parse_xtb_file
import yfinance as yf

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
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def get_price(ticker):
    try:
        return yf.Ticker(ticker).fast_info.last_price
    except:
        return None

def load_portfolio():
    try:
        return json.load(open("portfolio.json"))
    except:
        return None

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

client = Groq(api_key=GROQ_API_KEY)
st.set_page_config(page_title="Инвестиционный помощник", page_icon="💼", layout="wide")

# Дашборд сверху
portfolio = load_portfolio()
if portfolio:
    prices = {}
    for p in portfolio["positions"]:
        if p["volume"] > 0:
            price = get_price(p["ticker"])
            if price:
                prices[p["name"]] = price

    ike_balance = portfolio["accounts"].get("IKE", {}).get("balance", 0)
    trade_balance = portfolio["accounts"].get("Transakcje", {}).get("balance", 0)
    total = ike_balance + trade_balance

    st.markdown(f"""
    <div style='background:#1a1a2e;padding:20px;border-radius:12px;margin-bottom:20px;'>
        <div style='display:flex;justify-content:space-between;align-items:center;'>
            <div>
                <div style='color:#888;font-size:14px;'>Общий баланс</div>
                <div style='color:white;font-size:36px;font-weight:bold;'>{total:,.2f} PLN</div>
            </div>
            <div style='text-align:right;'>
                <div style='color:#888;font-size:12px;'>IKE: {ike_balance:,.2f} PLN</div>
                <div style='color:#888;font-size:12px;'>Transakcje: {trade_balance:,.2f} PLN</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(len([p for p in portfolio["positions"] if p["volume"] > 0]))
    col_idx = 0
    for p in portfolio["positions"]:
        if p["volume"] == 0:
            continue
        price = prices.get(p["name"])
        if price:
            pct = (price - p["open_price"]) / p["open_price"] * 100
            color = "#00c853" if pct >= 0 else "#ff1744"
            arrow = "▲" if pct >= 0 else "▼"
            with cols[col_idx]:
                st.markdown(f"""
                <div style='background:#16213e;padding:15px;border-radius:10px;border-left:4px solid {color};'>
                    <div style='color:#aaa;font-size:12px;'>{p["name"]}</div>
                    <div style='color:white;font-size:20px;font-weight:bold;'>{price:.2f}</div>
                    <div style='color:{color};font-size:14px;'>{arrow} {pct:+.2f}%</div>
                </div>
                """, unsafe_allow_html=True)
        col_idx += 1

st.markdown("---")

# Основной интерфейс
col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("### 💼 Помощник")
    uploaded_file = st.file_uploader("Файл XTB", type=["csv","xlsx","xls","zip"], key="xtb_file")
    if uploaded_file:
        parsed_text, count = parse_xtb_file(uploaded_file)
        if count > 0:
            st.success(f"Загружено {count} сделок")
            st.session_state.xtb_data = parsed_text
        else:
            st.error(parsed_text)
    screenshots = st.file_uploader("Скриншоты (до 5)", type=["png","jpg","jpeg"], key="screenshot_file", accept_multiple_files=True)
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
        "🌍 Рынок": "/рынок",
        "🎯 Сигналы": "/сигналы",
        "📰 Обзор": "/обзор",
        "⚠️ Риски": "/риски",
        "🔄 Ребаланс": "/ребаланс",
        "₿ Крипто": "/крипто",
        "💰 Дивиденды": "/дивиденды",
        "📓 Журнал": "/журнал",
        "🔄 Обновить": "/обновить",
    }
    for label, command in commands.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_command = command
    if st.button("🗑️ Очистить", use_container_width=True):
        st.session_state.messages = []
        save_history([])
        st.rerun()

with col2:
    st.markdown("### 💬 Чат")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for block in message["content"]:
                    if block["type"] == "text":
                        st.markdown(block["text"])
            else:
                st.markdown(message["content"])

    if "quick_command" in st.session_state:
        prompt = st.session_state.pop("quick_command")
    else:
        prompt = st.chat_input("Введите сообщение или команду...")

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            with st.spinner("Анализирую..."):
                today = datetime.now().strftime("%A, %d %B %Y, %H:%M")
                system = get_system_prompt() + f"\n\nСегодня: {today}"
                if "xtb_data" in st.session_state:
                    system += f"\n\nДАННЫЕ ПОРТФЕЛЯ XTB:\n{st.session_state.xtb_data}"
                messages = [{"role": "system", "content": system}]
                for m in st.session_state.messages[-5:]:
                    if isinstance(m["content"], str):
                        messages.append({"role": m["role"], "content": m["content"]})
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=2048
                )
                reply = response.choices[0].message.content
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        save_history(st.session_state.messages)
