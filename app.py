import streamlit as st
import anthropic
import base64
import json
import os
from datetime import datetime
from xtb_parser import parse_xtb_file

ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
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

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
st.set_page_config(page_title="Инвестиционный помощник", page_icon="💼", layout="wide")

with st.sidebar:
    st.title("Портфельный ассистент")
    st.markdown("---")
    uploaded_file = st.file_uploader("Загрузить файл XTB", type=["csv","xlsx","xls","zip"], key="xtb_file")
    if uploaded_file:
        parsed_text, count = parse_xtb_file(uploaded_file)
        if count > 0:
            st.success(f"Загружено {count} сделок")
            st.session_state.xtb_data = parsed_text
        else:
            st.error(parsed_text)
    st.markdown("---")
    screenshot = st.file_uploader("Загрузить скриншот", type=["png","jpg","jpeg"], key="screenshot_file")
    if screenshot:
        st.image(screenshot, use_column_width=True)
        screenshot.seek(0)
        st.session_state.screenshot = base64.b64encode(screenshot.read()).decode()
        st.session_state.screenshot_type = screenshot.type
        st.success("Скриншот готов!")
    st.markdown("---")
    st.markdown("Команды:")
    commands = {
        "Портфель": "/портфель",
        "Обзор недели": "/обзор",
        "Месячный отчёт": "/отчёт",
        "Риски": "/риски",
        "Ребалансировка": "/ребаланс",
        "Крипто": "/крипто",
        "Дивиденды": "/дивиденды",
        "Профиль": "/профиль",
        "Рынок": "/рынок",
        "Сигналы": "/сигналы",
        "Новости": "/новости",
        "Журнал": "/журнал",
    }
    for label, command in commands.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_command = command
    st.markdown("---")
    if st.button("Очистить чат", use_container_width=True):
        st.session_state.messages = []
        save_history([])
        st.rerun()

st.title("Инвестиционный помощник")

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
    user_content = prompt
    if "screenshot" in st.session_state:
        user_content = [
            {"type": "image", "source": {"type": "base64", "media_type": st.session_state.screenshot_type, "data": st.session_state.screenshot}},
            {"type": "text", "text": prompt}
        ]
        del st.session_state.screenshot
        del st.session_state.screenshot_type
    st.session_state.messages.append({"role": "user", "content": user_content})
    with st.chat_message("assistant"):
        with st.spinner("Анализирую..."):
            today = datetime.now().strftime("%A, %d %B %Y, %H:%M")
            system = get_system_prompt() + f"\n\nСегодня: {today}"
            if "xtb_data" in st.session_state:
                system += f"\n\nДАННЫЕ ПОРТФЕЛЯ XTB:\n{st.session_state.xtb_data}"
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=system,
                messages=st.session_state.messages
            )
            reply = response.content[0].text
            st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    save_history(st.session_state.messages)
