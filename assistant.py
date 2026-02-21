import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def load_system_prompt():
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def run_assistant():
    system_prompt = load_system_prompt()
    conversation_history = []

    print("\n" + "=" * 55)
    print("   Инвестиционный помощник готов к работе")
    print("   Попробуйте: /профиль  /портфель  /анализ AAPL")
    print("   Для выхода введите: выход")
    print("=" * 55 + "\n")

    while True:
        user_input = input("Вы: ").strip()

        if user_input.lower() in ["выход", "exit", "quit"]:
            print("\nДо свидания!")
            break

        if not user_input:
            continue

        conversation_history.append({"role": "user", "content": user_input})
        print("\nАнализирую...\n")

        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=conversation_history
            )
            reply = response.content[0].text
            conversation_history.append({"role": "assistant", "content": reply})
            print(f"Помощник:\n{reply}\n")
            print("-" * 55 + "\n")

        except anthropic.AuthenticationError:
            print("Ошибка: неверный API-ключ. Проверьте файл .env\n")
        except Exception as e:
            print(f"Ошибка: {e}\n")

if __name__ == "__main__":
    run_assistant()
