from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
import json

TOKEN = "???"


# ---------- ПАРСЕР JSON ФАЙЛОВ ----------

def analyze_json_file(json_bytes):
    """
    Принимает содержимое JSON файла как bytes.
    Возвращает:
    {
        "users": { user_id: name },
        "mentions": set([...])
    }
    """
    data = json.loads(json_bytes.decode("utf-8"))

    users = {}
    mentions = set()

    messages = data.get("messages", [])

    for msg in messages:
        # --- Собираем авторов ---
        name = msg.get("from")
        user_id = msg.get("from_id")

        if name and user_id:
            users[user_id] = name

        # --- Собираем упоминания в text_entities ---
        for ent in msg.get("text_entities", []):
            if ent.get("type") == "mention":
                username = ent.get("text")
                if username:
                    mentions.add(username)

        # --- Если text — список, там тоже могут быть mentions ---
        text_field = msg.get("text")
        if isinstance(text_field, list):
            for part in text_field:
                if isinstance(part, dict) and part.get("type") == "mention":
                    mentions.add(part.get("text"))

    return {
        "users": users,
        "mentions": mentions
    }


# ---------- ОБРАБОТЧИКИ БОТА ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["files"] = []
    await update.message.reply_text(
        "Привет! Отправляй JSON-файлы. Когда загрузишь все — напиши /go."
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    # Проверим формат
    if not document.file_name.lower().endswith(".json"):
        await update.message.reply_text("Принимаю только JSON-файлы 📄")
        return

    # Сохраняем сам объект документа
    files = context.user_data.get("files", [])
    files.append(document)
    context.user_data["files"] = files

    await update.message.reply_text(
        f"Добавлен файл: {document.file_name}\n"
        f"Всего файлов: {len(files)}\n\n"
        "Отправляй остальные или напиши /go."
    )


async def process_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = context.user_data.get("files", [])

    if not files:
        await update.message.reply_text("Ты не загрузил ни одного файла 🤷‍♂️")
        return

    all_users = {}
    all_mentions = set()

    # Обрабатываем каждый документ
    for document in files:
        file = await document.get_file()
        content = await file.download_as_bytearray()

        result = analyze_json_file(content)

        # Добавляем пользователей
        for uid, name in result["users"].items():
            all_users[uid] = name

        # Добавляем упоминания
        all_mentions.update(result["mentions"])

    # Составляем итоговое сообщение
    response = "📊 *Результаты анализа файлов:*\n\n"

    response += "👥 *Участники чата:*\n"
    if all_users:
        for uid, name in all_users.items():
            response += f"- {name} (`{uid}`)\n"
    else:
        response += "_Не найдено_\n"

    response += "\n🔔 *Упоминания (@username):*\n"
    if all_mentions:
        for m in all_mentions:
            response += f"- {m}\n"
    else:
        response += "_Упоминаний нет_\n"

    # Отправляем результат
    await update.message.reply_text(response, parse_mode="HTML")

    # Очищаем очередь
    context.user_data["files"] = []
    await update.message.reply_text("Готово. Очередь очищена.")


# ---------- ЗАПУСК БОТА ----------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("go", process_files))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

app.run_polling()
