import os
import re
import glob
import time
import shutil
import threading
import requests
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import imageio_ffmpeg

# ========================================================
# ⚠️ নিচের ২টি জায়গায় অবশ্যই তোমার আসল তথ্য বসাও ⚠️
# ========================================================
BOT_TOKEN = "8940269151:AAFkeX5BbAKx0mrWmAwkIKrAo21AQT_cCu4" 
CHANNEL_LINK = "https://t.me/techtricks360"
# ========================================================

bot = telebot.TeleBot(BOT_TOKEN)
user_downloads = {}
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

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

def get_cookie_file():
    for name in ['cookies.txt', 'Cookies.txt', 'COOKIES.TXT', 'cookies.txt.txt']:
        if os.path.exists(name) and os.path.getsize(name) > 100:
            shutil.copy(name, '/tmp/yt_cookies.txt')
            return '/tmp/yt_cookies.txt'
    return None

# ইঞ্জিন ১: ইউনিভার্সাল ফরম্যাট (যেকোনো ফরম্যাট ও রেজোলিউশন সাপোর্ট করবে)
def download_with_ytdlp(url, base_name):
    ydl_opts = {
        # কোনো সাইজ লিমিট বা ক্লায়েন্ট রেস্ট্রিকশন ছাড়া সরাসরি বেস্ট ফরম্যাট নেবে
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': f"{base_name}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
    }
    
    cookie_path = get_cookie_file()
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # ডাউনলোড হওয়া ফাইলটি খুঁজে বের করা
    files = glob.glob(f"{base_name}.*")
    for f in files:
        if not f.endswith('.part') and not f.endswith('.ytdl'):
            return f
    return None

# ইঞ্জিন ২: কুকিজ ছাড়া ট্রাই করা (যদি কখনো কুকির কারণে ফরম্যাট আটকে যায়)
def download_without_cookies(url, base_name):
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best',
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': f"{base_name}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android_vr', 'tv_embedded']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    files = glob.glob(f"{base_name}.*")
    for f in files:
        if not f.endswith('.part') and not f.endswith('.ytdl'):
            return f
    return None

# মাস্টার ডাউনলোড কন্ট্রোলার
def download_video(url, base_name):
    real_url = resolve_url(url)
    
    # ১ম চেষ্টা: কুকিজসহ সরাসরি ডাউনলোড
    try:
        file_path = download_with_ytdlp(real_url, base_name)
        if file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            return file_path
    except Exception as first_error:
        print("First attempt failed, trying fallback client...", first_error)
        
        # ২য় চেষ্টা: বিকল্প ক্লায়েন্ট দিয়ে ডাউনলোড
        try:
            file_path = download_without_cookies(real_url, base_name)
            if file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                return file_path
        except Exception:
            pass
            
        raise first_error

@bot.message_handler(commands=['start'])
def send_welcome(message):
    cookie_status = "✅ Active" if get_cookie_file() else "⚠️ Missing"
    welcome_text = (
        "👋 **স্বাগতম MediaGrab Video Downloader বটে!**\n\n"
        "আমাকে যেকোনো **TikTok, Instagram Reel, Facebook বা YouTube Shorts**-এর লিংক পাঠান, "
        "আমি ওয়াটারমার্ক ছাড়া HD ভিডিও ডাউনলোড করে দেবো! 🚀\n\n"
        f"🍪 *YouTube Cookie Status: {cookie_status}*"
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
    base_name = f"video_{chat_id}_{int(time.time())}"
    downloaded_file = None

    try:
        downloaded_file = download_video(url, base_name)

        with open(downloaded_file, 'rb') as video:
            bot.send_video(
                chat_id, 
                video, 
                caption="✅ **ডাউনলোড সম্পন্ন!**\nভালো লাগলে আমাদের চ্যানেলে জয়েন করতে ভুলবেন না যেন! 👇",
                reply_markup=get_channel_button(),
                parse_mode="Markdown"
            )

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
    finally:
        # ডাউনলোড শেষে সার্ভারের ফাইল মুছে ফেলা
        for f in glob.glob(f"{base_name}*"):
            try:
                os.remove(f)
            except Exception:
                pass

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(2)
    print("✅ বট ইউনিভার্সাল ফরম্যাটসহ চালু হয়েছে!")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            time.sleep(5)
