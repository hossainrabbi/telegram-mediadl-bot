import os
import time
import threading
import requests
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# ========================================================
# ⚠️ নিচের ২টি জায়গায় অবশ্যই তোমার আসল তথ্য বসাও ⚠️
# ========================================================
BOT_TOKEN = "8940269151:AAFkeX5BbAKx0mrWmAwkIKrAo21AQT_cCu4" 
CHANNEL_LINK = "https://t.me/techtricks360"
# ========================================================

bot = telebot.TeleBot(BOT_TOKEN)
user_downloads = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "MediaGrab Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

def get_channel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 আমাদের চ্যানেলে জয়েন করুন", url=CHANNEL_LINK))
    return markup

def resolve_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
        r = requests.head(url, allow_redirects=True, headers=headers, timeout=10)
        return r.url
    except Exception:
        return url

# ইঞ্জিন ১: cookies.txt সহ প্রাইমারি ডাউনলোডার
def download_with_ytdlp(url, filename):
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<48M]/best[ext=mp4]/best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
    }
    
    # যদি cookies.txt ফাইল থাকে তবে সেটি অটোমেটিক ব্যবহার করবে
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# ইঞ্জিন ২: ব্যাকআপ এপিআই
def download_with_fallback_api(url, filename):
    api_endpoints = [
        "https://cobalt-api.kwiatekmiki.com",
        "https://cobalt.api.timelessnesses.me",
        "https://api.cobalt.tools"
    ]
    for api in api_endpoints:
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            payload = {"url": url, "vQuality": "720"}
            res = requests.post(api, json=payload, headers=headers, timeout=15)
            video_url = res.json().get("url")
            if video_url:
                vid_data = requests.get(video_url, stream=True, timeout=30)
                if vid_data.status_code == 200:
                    with open(filename, 'wb') as f:
                        for chunk in vid_data.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                    return True
        except Exception:
            continue
    return False

def download_video(url, filename):
    real_url = resolve_url(url)
    try:
        download_with_ytdlp(real_url, filename)
        if os.path.exists(filename) and os.path.getsize(filename) > 1000:
            return
    except Exception as ytdl_error:
        success = download_with_fallback_api(real_url, filename)
        if success and os.path.exists(filename) and os.path.getsize(filename) > 1000:
            return
        raise ytdl_error

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 **স্বাগতম MediaGrab Video Downloader বটে!**\n\n"
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
        error_text = str(e).replace('`', '').replace('*', '').replace('_', '')
        bot.edit_message_text(
            f"❌ দুঃখিত! এই ভিডিওটি ডাউনলোড করা যাচ্ছে না।\n\n🔍 কারণ: {error_text[:150]}", 
            chat_id, 
            wait_msg.message_id
        )
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(2)
    print("✅ বট কুকিজসহ সফলভাবে চালু হয়েছে!")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            time.sleep(5)
