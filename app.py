import streamlit as st
import anthropic
import os
import json
import socket
import ssl

ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
XTB_ACCOUNT = st.secrets["XTB_ACCOUNT"]
XTB_PASSWORD = st.secrets["XTB_PASSWORD"]

class XTBClient:
    HOST = "xapi.xtb.com"
    PORT = 5112

    def connect(self):
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(5)  # Таймаут 5 секунд — если не ответил, идём дальше
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(raw_sock, server_hostname=self.HOST)
        self.sock.connect((self.HOST, self.PORT))

    def send(self, command):
        message = json.dumps(command) + "\n"
        self.sock.sendall(message.encode())
        response = ""
        self.sock.settimeout(5)
        while True:
            try:
                chunk = self.sock.recv(4096).decode()
                response += chunk
                return json.loads(response)
            except json.JSONDecodeError:
                continue
            except socket.timeout:
                return {}

    def login(self, account, password):
        response = self.send({
            "command": "login",
            "arguments": {"userId": account, "password": password}
        })
        return response.get("status", False)

    def get_balance(self):
        return self.send({"command": "getMarginLevel"}).get("returnData", {})

    def get_trades(self):
        return self.send({
            "command": "getTrades",
            "arguments": {"openedOnly": True}
        }).get("returnData", [])

    def disconnect(self):
        try:
            self.send({"command": "logout"})
            self.sock.close()
        except:
            pass

@st.cache_data(ttl=60)
def fetch_xtb_data(account, password):
    client = XTBClient()
    try:
        client.connect()
        if not client.login(account, password):
            return None, None, "Ошибка авторизации в XTB"
        balance = client.get_balance()
        trades = client.get_trades()
        return balance, trades, None
    except socket.timeout:
        return None, None, "XTB не отвечает — возможно сервер блокирует облачные IP"
    except Exception as e:
        return None, None, f"Ошибка: {str(e)}"
    finally:
        client.disconnect()

def format_xtb_context(balance, trades):
    lines = ["=== ДАННЫЕ ПОРТФЕЛЯ ИЗ XTB ===\n"]
    if balance:
        lines.append(f"Баланс: {balance.get('balance', 'н/д')} {balance.get('currency', '')}")
        lines.append(f"Эквити: {balance.get('equity', 'н/д')}")
        lines.append(f"Свободная маржа: {balance.get('margin_free', 'н/д')}\n")
    if trades:
        lines.append(f"Открытые позиции ({len(trades)}):")
        for t in trades:
            cmd = "Покупка" if t.get('cmd') == 0 else "Продажа"
            lines.append(f"  • {t.get('symbol')}: {cmd} {t.get('volume')} лот, P&L: {t.get('profit', 0):.2f}")
    else:
        lines.append("Открытых позиций нет.")
    lines.append("\n=== КОНЕЦ ДАННЫХ XTB ===")
    return "\n".join(lines)

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
    st.markdown("**📡 Данные XTB**")
    
    balance, trades, error = fetch_xtb_data(XTB_ACCOUNT, XTB_PASSWORD)
    
    if error:
        st.warning(f"XTB недоступен: {error}\n\nПомощник работает без данных XTB — вводите портфель вручную.")
        xtb_context = ""
    else:
        st.success(f"Эквити: {balance.get('equity', 0):.2f} {balance.get('currency', '')}")
        st.info(f"Позиций: {len(trades)}")
        xtb_context = format_xtb_context(balance, trades)
        if st.button("🔄 Обновить", use_container_width=True):
            fetch_xtb_data.clear()
            st.rerun()

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
            system_with_context = get_system_prompt()
            if xtb_context:
                system_with_context += f"\n\n{xtb_context}"
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=system_with_context,
                messages=st.session_state.messages
            )
            reply = response.content[0].text
            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
