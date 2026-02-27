import streamlit as st
import base64
import json
import os
from datetime import datetime
from groq import Groq
from xtb_parser import parse_xtb_file

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

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

client = Groq(api_key=GROQ_API_KEY)
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
    screenshots = st.file_uploader("Загрузить скриншоты (до 5)", type=["png","jpg","jpeg"], key="screenshot_file", accept_multiple_files=True)
    if screenshots:
        images = []
        for s in screenshots[:5]:
            st.image(s, use_column_width=True)
            s.seek(0)
            images.append({"data": base64.b64encode(s.read()).decode(), "type": s.type})
        st.session_state.screenshots = images
        st.success(f"Загружено {len(images)} скриншотов!")
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
        "Обновить портфель": "/обновить",
    }
    for label, command in commands.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_command = command
    st.markdown("---")
    if st.button("Очистить чат", use_container_width=True):
        st.session_state.messages = []
        save_history([])
        st.rerun()

st.title("Инвестиционный помощник 💼")

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
            for m in st.session_state.messages[-100:]:
                if isinstance(m["content"], str):
                    messages.append({"role": m["role"], "content": m["content"]})
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=4096
            )
            reply = response.choices[0].message.content
            st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    save_history(st.session_state.messages)
