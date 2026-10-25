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
from pytubefix import YouTube

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

# ==========================================
# স্পেশাল ইঞ্জিন ১: শুধুমাত্র YouTube-এর জন্য (pytubefix)
# ==========================================
def download_youtube_pytubefix(url, base_name):
    output_file = f"{base_name}.mp4"
    # WEB এবং MWEB ক্লায়েন্ট দিয়ে চেষ্টা করবে যাতে ফরম্যাট মিস না হয়
    for client_type in ['WEB', 'MWEB', 'ANDROID_VR', 'IOS']:
        try:
            yt = YouTube(url, client=client_type)
            # অডিওসহ MP4 স্ট্রিম খোঁজা (Progressive)
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if not stream:
                stream = yt.streams.filter(file_extension='mp4').first()
            if stream:
                stream.download(filename=output_file)
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                    return output_file
        except Exception as e:
            print(f"Pytubefix ({client_type}) failed:", e)
            continue
    return None

# ==========================================
# স্পেশাল ইঞ্জিন ২: এক্সটার্নাল YouTube Downloader API
# ==========================================
def download_youtube_external_api(url, base_name):
    output_file = f"{base_name}.mp4"
    
    # ইঞ্জিন ২.১: Cobalt API (v7 ও v10 উভয় ফরম্যাট)
    cobalt_nodes = [
        "https://cobalt-api.kwiatekmiki.com",
        "https://cobalt.api.timelessnesses.me",
        "https://api.cobalt.tools"
    ]
    for api in cobalt_nodes:
        try:
            # New API Format
            headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            res = requests.post(api, json={"url": url, "videoQuality": "720"}, headers=headers, timeout=12)
            dl_url = res.json().get("url")
            
            # Old API Format fallback
            if not dl_url:
                res = requests.post(f"{api}/api/json", json={"url": url, "vQuality": "720"}, headers=headers, timeout=12)
                dl_url = res.json().get("url")

            if dl_url:
                r = requests.get(dl_url, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(output_file, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                        return output_file
        except Exception:
            continue
    return None

# ==========================================
# ইঞ্জিন ৩: yt-dlp (TikTok, FB, Insta ও ব্যাকআপের জন্য)
# ==========================================
def download_with_ytdlp(url, base_name, use_cookies=True):
    ydl_opts = {
        # কোনো বাধ্যবাধকতা ছাড়া যেকোনো সচল ফরম্যাট নেবে
        'format': 'b/bv*+ba/w',
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_PATH,
        'outtmpl': f"{base_name}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
    }
    
    if use_cookies:
        cookie_path = get_cookie_file()
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path
    else:
        # কুকিজ ছাড়া চালালে মোবাইল ক্লায়েন্ট ব্যবহার করবে
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['ios', 'android', 'mweb']}}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    for f in glob.glob(f"{base_name}.*"):
        if not f.endswith('.part') and not f.endswith('.ytdl'):
            return f
    return None

# ==========================================
# মাস্টার কন্ট্রোলার (ধাপে ধাপে সব ইঞ্জিন চেক করবে)
# ==========================================
def download_video(url, base_name):
    real_url = resolve_url(url)
    is_youtube = "youtube.com" in real_url or "youtu.be" in real_url

    # যদি YouTube লিংক হয়, তবে আগে স্পেশাল ইউটিউব ইঞ্জিনগুলো ট্রাই করবে
    if is_youtube:
        # ১. Pytubefix দিয়ে চেষ্টা
        res = download_youtube_pytubefix(real_url, base_name)
        if res:
            return res

        # ২. External API দিয়ে চেষ্টা
        res = download_youtube_external_api(real_url, base_name)
        if res:
            return res

        # ৩. কুকিজ ছাড়া yt-dlp দিয়ে চেষ্টা (যাতে IP Mismatch না হয়)
        try:
            res = download_with_ytdlp(real_url, base_name, use_cookies=False)
            if res:
                return res
        except Exception:
            pass

    # ৪. কুকিজসহ yt-dlp দিয়ে চেষ্টা (TikTok, FB, Insta ও শেষ ইউটিউব চেষ্টা)
    res = download_with_ytdlp(real_url, base_name, use_cookies=True)
    if res:
        return res

    raise Exception("সার্ভার থেকে এই ভিডিওর ফরম্যাট ডাউনলোড করা সম্ভব হয়নি।")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 **স্বাগতম MediaGrab Video Downloader বটে!**\n\n"
        "আমাকে যেকোনো **TikTok, Instagram Reel, Facebook বা YouTube Shorts**-এর লিংক পাঠান, "
        "আমি ওয়াটারমার্ক ছাড়া HD ভিডিও ডাউনলোড করে দেবো! 🚀"
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
        for f in glob.glob(f"{base_name}*"):
            try:
                os.remove(f)
            except Exception:
                pass

if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(2)
    print("✅ বট মাল্টি-ইঞ্জিনসহ চালু হয়েছে!")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            time.sleep(5)
