import streamlit as st
import anthropic
import os
from dotenv import load_dotenv

# Загружаем API-ключ из файла .env
load_dotenv()

# Настройки страницы — заголовок и иконка во вкладке браузера
st.set_page_config(
    page_title="Инвестиционный помощник",
    page_icon="💼",
    layout="wide"
)

# Загружаем инструкцию из файла один раз при запуске
@st.cache_resource
def get_system_prompt():
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

# Инициализируем историю сообщений в памяти Streamlit.
# st.session_state — это специальное хранилище, которое живёт
# пока открыта вкладка браузера. Именно здесь хранится "память" чата.
if "messages" not in st.session_state:
    st.session_state.messages = []

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Боковая панель с командами ──────────────────────────────────
with st.sidebar:
    st.title("💼 Портфельный ассистент")
    st.markdown("---")
    st.markdown("**Быстрые команды:**")

    # Кнопки для быстрого ввода команд — нажал и команда появилась в чате
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
    # Кнопка очистки истории чата
    if st.button("🗑️ Очистить чат", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Основная область чата ───────────────────────────────────────
st.title("Инвестиционный помощник 💼")

# Отображаем все предыдущие сообщения из истории
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Проверяем, была ли нажата кнопка быстрой команды в боковой панели
if "quick_command" in st.session_state:
    prompt = st.session_state.pop("quick_command")
else:
    # Поле ввода внизу экрана — стандартный чат-интерфейс
    prompt = st.chat_input("Введите сообщение или команду...")

# Обрабатываем новое сообщение
if prompt:
    # Показываем сообщение пользователя
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Получаем ответ от Claude и показываем его с эффектом печатания
    with st.chat_message("assistant"):
        with st.spinner("Анализирую..."):
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=get_system_prompt(),
                messages=st.session_state.messages
            )
            reply = response.content[0].text
            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
