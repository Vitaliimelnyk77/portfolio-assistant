import streamlit as st
import anthropic
import os
import json
import socket
import ssl
import time

# ── Загрузка секретов ────────────────────────────────────────────
# Streamlit читает секреты из защищённого хранилища автоматически
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
XTB_ACCOUNT = st.secrets["XTB_ACCOUNT"]
XTB_PASSWORD = st.secrets["XTB_PASSWORD"]

# ── Подключение к XTB API ────────────────────────────────────────
class XTBClient:
    """
    Клиент для работы с XTB xStation5 API.
    XTB использует WebSocket-подобный протокол через SSL-сокет:
    мы отправляем JSON-команды и получаем JSON-ответы.
    """
    
    HOST = "xapi.xtb.com"
    PORT = 5112  # Порт для реальных счётов (5124 для демо)
    
    def __init__(self):
        self.sock = None
        self.session_id = None
    
    def connect(self):
        """Устанавливаем зашифрованное SSL-соединение с сервером XTB."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(10)
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(raw_sock, server_hostname=self.HOST)
        self.sock.connect((self.HOST, self.PORT))
    
    def send(self, command: dict) -> dict:
        """Отправляем команду и получаем ответ от сервера."""
        message = json.dumps(command) + "\n"
        self.sock.sendall(message.encode())
        
        # Читаем ответ по частям пока не получим полный JSON
        response = ""
        while True:
            chunk = self.sock.recv(4096).decode()
            response += chunk
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                continue
    
    def login(self, account: str, password: str) -> bool:
        """Авторизуемся на сервере и получаем токен сессии."""
        response = self.send({
            "command": "login",
            "arguments": {
                "userId": account,
                "password": password
            }
        })
        if response.get("status"):
            self.session_id = response.get("streamSessionId")
            return True
        return False
    
    def get_balance(self) -> dict:
        """Получаем баланс и маржу счёта."""
        response = self.send({"command": "getMarginLevel"})
        return response.get("returnData", {})
    
    def get_trades(self) -> list:
        """Получаем все открытые позиции."""
        response = self.send({
            "command": "getTrades",
            "arguments": {"openedOnly": True}
        })
        return response.get("returnData", [])
    
    def disconnect(self):
        """Закрываем соединение."""
        if self.sock:
            try:
                self.send({"command": "logout"})
            except:
                pass
            self.sock.close()


@st.cache_data(ttl=60)  # Кэшируем данные на 60 секунд чтобы не спамить запросами
def fetch_xtb_data(account: str, password: str):
    """
    Подключаемся к XTB, забираем данные и отключаемся.
    ttl=60 означает что данные обновляются раз в минуту автоматически.
    """
    client = XTBClient()
    try:
        client.connect()
        if not client.login(account, password):
            return None, None, "Ошибка авторизации в XTB. Проверьте логин и пароль."
        
        balance = client.get_balance()
        trades = client.get_trades()
        return balance, trades, None
    except Exception as e:
        return None, None, f"Ошибка подключения к XTB: {str(e)}"
    finally:
        client.disconnect()


def format_xtb_context(balance: dict, trades: list) -> str:
    """
    Форматируем данные из XTB в текст который понимает Claude.
    Этот текст добавляется к каждому запросу — так помощник всегда
    знает актуальное состояние вашего портфеля.
    """
    lines = ["=== АКТУАЛЬНЫЕ ДАННЫЕ ПОРТФЕЛЯ ИЗ XTB ===\n"]
    
    if balance:
        lines.append(f"Баланс счёта: {balance.get('balance', 'н/д')} {balance.get('currency', '')}")
        lines.append(f"Эквити: {balance.get('equity', 'н/д')}")
        lines.append(f"Маржа использованная: {balance.get('margin', 'н/д')}")
        lines.append(f"Свободная маржа: {balance.get('margin_free', 'н/д')}\n")
    
    if trades:
        lines.append(f"Открытые позиции ({len(trades)}):")
        for t in trades:
            symbol = t.get('symbol', 'н/д')
            volume = t.get('volume', 0)
            open_price = t.get('open_price', 0)
            current_profit = t.get('profit', 0)
            trade_type = "Покупка" if t.get('cmd') == 0 else "Продажа"
            lines.append(f"  • {symbol}: {trade_type} {volume} лот, открыта по {open_price}, P&L: {current_profit:.2f}")
    else:
        lines.append("Открытых позиций нет.")
    
    lines.append("\n=== КОНЕЦ ДАННЫХ XTB ===")
    return "\n".join(lines)


# ── Загрузка системного промпта ──────────────────────────────────
@st.cache_resource
def get_system_prompt():
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

# ── Инициализация состояния ──────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Настройки страницы ───────────────────────────────────────────
st.set_page_config(
    page_title="Инвестиционный помощник",
    page_icon="💼",
    layout="wide"
)

# ── Боковая панель ───────────────────────────────────────────────
with st.sidebar:
    st.title("💼 Портфельный ассистент")
    st.markdown("---")
    
    # Блок с данными XTB
    st.markdown("**📡 Данные XTB (реальный счёт)**")
    with st.spinner("Загружаю данные..."):
        balance, trades, error = fetch_xtb_data(XTB_ACCOUNT, XTB_PASSWORD)
    
    if error:
        st.error(error)
        xtb_context = ""
    else:
        equity = balance.get('equity', 0) if balance else 0
        trades_count = len(trades) if trades else 0
        st.success(f"Эквити: {equity:.2f}")
        st.info(f"Открытых позиций: {trades_count}")
        xtb_context = format_xtb_context(balance, trades)
        
        if st.button("🔄 Обновить данные", use_container_width=True):
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

# ── Основной чат ─────────────────────────────────────────────────
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
            # Добавляем актуальные данные XTB к системному промпту.
            # Так Claude всегда видит реальное состояние вашего портфеля
            # без необходимости вводить его вручную.
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
