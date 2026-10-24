import os
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# ==========================================
# নিচের ২টি জায়গায় তোমার তথ্য বসাও
# ==========================================
BOT_TOKEN = "8940269151:AAFkeX5BbAKx0mrWmAwkIKrAo21AQT_cCu4" 
CHANNEL_LINK = "https://t.me/techtricks360"
# ==========================================

bot = telebot.TeleBot(BOT_TOKEN)
user_downloads = {}

# ২৪ ঘণ্টা অনলাইনে রাখার জন্য ছোট ফ্রি সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.start()

def get_channel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 আমাদের চ্যানেলে জয়েন করুন", url=CHANNEL_LINK))
    return markup

def download_video(url, filename):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 **স্বাগতম All-in-One Video Downloader বটে!**\n\n"
        "আমাকে যেকোনো **TikTok, Instagram Reel, Facebook বা YouTube Shorts**-এর লিংক পাঠান, "
        "আমি ওয়াটারমার্ক ছাড়া HD ভিডিও ডাউনলোড করে দেবো! 🚀\n\n"
        "💡 *নতুন আপডেট পেতে আমাদের চ্যানেলে যুক্ত হতে পারেন:*"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_channel_button(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_link(message):
    chat_id = message.chat.id
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "❌ অনুগ্রহ করে একটি সঠিক ভিডিও লিংক দিন!")
        return

    wait_msg = bot.reply_to(message, "⏳ আপনার ভিডিওটি ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন...")
    filename = f"video_{chat_id}.mp4"

    if os.path.exists(filename):
        os.remove(filename)

    try:
        download_video(url, filename)

        with open(filename, 'rb') as video:
            bot.send_video(
                chat_id, 
                video, 
                caption="✅ **ডাউনলোড সম্পন্ন!**\nভালো লাগলে আমাদের চ্যানেলে জয়েন করতে ভুলবেন না যেন! 👇",
                reply_markup=get_channel_button(),
                parse_mode="Markdown"
            )

        os.remove(filename)
        bot.delete_message(chat_id, wait_msg.message_id)

        user_downloads[chat_id] = user_downloads.get(chat_id, 0) + 1
        if user_downloads[chat_id] % 3 == 0:
            promo_text = (
                "💖 **বটটি কি আপনার ভালো লাগছে?**\n\n"
                "আমাদের সাপোর্ট করতে আমাদের টেলিগ্রাম চ্যানেলে জয়েন করে রাখুন!"
            )
            bot.send_message(chat_id, promo_text, reply_markup=get_channel_button(), parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text(
            "❌ দুঃখিত! এই ভিডিওটি ডাউনলোড করা যাচ্ছে না। লিংকটি পাবলিক আছে কি না চেক করুন।", 
            chat_id, 
            wait_msg.message_id
        )
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    keep_alive()
    print("✅ বট ২৪ ঘণ্টার জন্য চালু হয়েছে!")
    bot.infinity_polling(skip_pending=True)