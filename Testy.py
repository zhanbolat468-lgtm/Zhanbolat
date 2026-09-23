import os
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8865818486:AAECEJQmjmJudZ2MtYyTjx2tA5W5WHJ2uRg"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Салем! 👋")

print("Bot is running - tek Salem deydi")
bot.infinity_polling()
