import streamlit as st
import anthropic
import os

ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]

@st.cache_resource
def get_system_prompt():
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

if "messages" not in st.session_state:
    st.session_state.messages = []

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

st.set_page_config(page_title="Инвестиционный помощник", page_icon="💼", layout="wide")

with st.sidebar:
    st.title("💼 Портфельный ассистент")
    st.markdown("---")
    
    uploaded_file = st.file_uploader("📂 Загрузить CSV из XTB", type="csv")
    if uploaded_file:
        import pandas as pd
        df = pd.read_csv(uploaded_file)
        st.success(f"Загружено {len(df)} записей")
        st.session_state.xtb_data = df.to_string()

    st.markdown("---")
    st.markdown("**Быстрые команды:**")
    commands = {
        "📊 Портфель": "/портфель",
        "📰 Обзор недели": "/обзор",
        "📈 Месячный отчёт": "/отчёт",
        "⚠️ Риски": "/риски",
        "🔄 Ребалансировка": "/ребаланс",
        "₿ Крипто": "/крипто",
        "💰 Дивиденды": "/дивиденды",
        "👤 Профиль": "/профиль",
    }
    for label, command in commands.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_command = command

    st.markdown("---")
    if st.button("🗑️ Очистить чат", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("Инвестиционный помощник 💼")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
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
            system = get_system_prompt()
            if "xtb_data" in st.session_state:
                system += f"\n\nДАННЫЕ ПОРТФЕЛЯ ИЗ XTB:\n{st.session_state.xtb_data}"
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=system,
                messages=st.session_state.messages
            )
            reply = response.content[0].text
            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    
