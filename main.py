import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

reminders = []
def save_reminders():
    with open("reminders.json",  "w") as f:
        json.dump(reminders, f)


def load_reminders():
    global reminders
    try:
        with open("reminders.json", "r") as f:
            reminders = json.load(f)
    except FileNotFoundError:
        reminders = []


async def Start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hej! Jag är din bot.")

async def add_remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(context.args) == 0:
        await update.message.reply_text("Använd: /remind  <din påminnelse> ")
        return
    reminder_text = "".join(context.args)
    reminders.append(reminder_text)
    save_reminders()

    await update.message.reply_text(f"Påminnelse tillagd: {reminder_text}")

async def display_reminds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(reminders) == 0:
        await update.message.reply_text("Inga påminnelser")
        return
    await update.message.reply_text(f"{reminders}")

async def delete_reminds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reminders.clear()
    await update.message.reply_text("påminnelser raderade ")

#gpt key#
# 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 #







    


def main():
    load_reminders()

    app = ApplicationBuilder().token("7589907637:AAFN5ZuDZ5PoRdzJLsBhvKF1BBZoJLd4mgw").build()
    
    app.add_handler(CommandHandler("deletelist", delete_reminds))
    app.add_handler(CommandHandler("start", Start))
    app.add_handler(CommandHandler("remind", add_remind))
    app.add_handler(CommandHandler("list", display_reminds))
    
    
    app.run_polling()

if __name__ == "__main__":

    main()

