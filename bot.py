import os
import re
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

# কুকিজ ফাইল খুঁজে বের করা
def get_cookie_file():
    for name in ['cookies.txt', 'Cookies.txt', 'COOKIES.TXT', 'cookies.txt.txt']:
        if os.path.exists(name) and os.path.getsize(name) > 100:
            shutil.copy(name, '/tmp/yt_cookies.txt')
            return '/tmp/yt_cookies.txt'
    return None

# ইঞ্জিন ১: yt-dlp (কুকিজ এবং টিভি/ক্রিয়েটর বাইপাস মোড)
def download_with_ytdlp(url, filename):
    ydl_opts = {
        'format': 'bestvideo[filesize<40M]+bestaudio/best[filesize<48M]/best',
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web_creator', 'tv_embedded', 'mweb']
            }
        }
    }
    
    cookie_path = get_cookie_file()
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# ইঞ্জিন ২: স্পেশাল YouTube Proxy API (কুকিজ ছাড়াও ইউটিউব নামাবে)
def download_youtube_direct_api(url, filename):
    # লিংক থেকে ইউটিউব ভিডিওর ১১ অক্ষরের ID বের করা
    match = re.search(r"(?:v=|\/shorts\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url)
    if not match:
        return False
    video_id = match.group(1)

    # ৪টি আলাদা ফ্রি ইউটিউব প্রক্সি সার্ভার
    piped_apis = [
        f"https://pipedapi.kavin.rocks/streams/{video_id}",
        f"https://pipedapi.tokhmi.xyz/streams/{video_id}",
        f"https://pipedapi.syncpundit.io/streams/{video_id}",
        f"https://api.piped.private.coffee/streams/{video_id}"
    ]

    for api in piped_apis:
        try:
            res = requests.get(api, timeout=12)
            if res.status_code == 200:
                data = res.json()
                streams = data.get("videoStreams", [])
                # অডিওসহ ভিডিও স্ট্রিম খোঁজা (videoOnly == False)
                for s in streams:
                    if not s.get("videoOnly", True) and s.get("format") == "MPEG-4":
                        dl_url = s.get("url")
                        if dl_url:
                            vid = requests.get(dl_url, stream=True, timeout=30)
                            if vid.status_code == 200:
                                with open(filename, 'wb') as f:
                                    for chunk in vid.iter_content(chunk_size=1024*1024):
                                        if chunk:
                                            f.write(chunk)
                                return True
        except Exception:
            continue
    return False

# ইঞ্জিন ৩: অল-ইন-ওয়ান ব্যাকআপ API (Cobalt)
def download_with_cobalt_api(url, filename):
    api_endpoints = [
        "https://cobalt-api.kwiatekmiki.com",
        "https://cobalt.api.timelessnesses.me"
    ]
    for api in api_endpoints:
        try:
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            res = requests.post(api, json={"url": url, "vQuality": "720"}, headers=headers, timeout=15)
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

# মাস্টার ডাউনলোড কন্ট্রোলার (১টি ফেল করলে পরেরটি চেষ্টা করবে)
def download_video(url, filename):
    real_url = resolve_url(url)
    
    # ১ম চেষ্টা: yt-dlp + Cookies
    try:
        download_with_ytdlp(real_url, filename)
        if os.path.exists(filename) and os.path.getsize(filename) > 1000:
            return
    except Exception as ytdl_error:
        # ২য় চেষ্টা: যদি ইউটিউব লিংক হয় তবে Piped Proxy API দিয়ে নামাবে
        if "youtube.com" in real_url or "youtu.be" in real_url:
            if download_youtube_direct_api(real_url, filename):
                if os.path.exists(filename) and os.path.getsize(filename) > 1000:
                    return
        
        # ৩য় চেষ্টা: Cobalt API দিয়ে নামাবে
        if download_with_cobalt_api(real_url, filename):
            if os.path.exists(filename) and os.path.getsize(filename) > 1000:
                return
                
        raise ytdl_error

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
    print("✅ বট ৩টি ইঞ্জিনসহ সফলভাবে চালু হয়েছে!")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            time.sleep(5)
