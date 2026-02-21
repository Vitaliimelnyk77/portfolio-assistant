import streamlit as st
import anthropic
import pandas as pd

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

    uploaded_file = st.file_uploader("📂 Загрузить файл из XTB", type=["csv", "xlsx", "xls"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.success(f"Загружено {len(df)} записей")
            st.session_state.xtb_data = df.to_string()
        except Exception as e:
            st.error(f"Ошибка загрузки: {e}")

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
    prompt = st.chat_input("Введите сообщение и
                           
