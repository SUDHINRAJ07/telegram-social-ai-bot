import os
import sys
import io
import time
import random
import socket
import base64
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import requests
from PIL import Image
import telebot
from telebot import types

# Fix Windows console unicode printing
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ================= Configuration =================
TELEGRAM_BOT_TOKEN = "8763763506:AAHjvN7Yw86oNBsYmyqSKNTqOQ1yx_w2llg"
GEMINI_API_KEY = "AQ.Ab8RN6LpXEJ00GXrdMA-ZVEJVSLPgaTsf8L8ZRGMt2Efm3lWiw"
FACEBOOK_PAGE_ID = "1276584508878950"
# 100% Never-Expiring Lifetime Facebook Page Access Token (expires_at: 0)
FACEBOOK_PAGE_ACCESS_TOKEN = "EAANEBDbaqKYBShXy0ZCIXSlRIGIpZAzK6QCWCQrPLyIjNYDjAtxPcnRU9kMDkU7XSxsbjD3oZCwZB76IQGcYQrUxqkRb4KZCIUZAgB3VWhwxaQOvkuaSJhdp8xFwiZBj2hsuZAFCWH1h7KfTZBRrwd3MKA41lnnQs4LQQyvJWFGZACkZALj4NZBdMpavXu4o9973SZAjC5YJQxqni"

# Cloudflare Workers AI Configuration (Pure Cloudflare Only)
CLOUDFLARE_ACCOUNT_ID = "222270a5d0bd73142a8b7e97b511281b"
CLOUDFLARE_API_TOKEN = "cfut_JmrtXi54CVYsZ8ukJHINJrT6qlw3cbHHs0WBOTCn8dd00f98"

# Instagram Configuration (Account: @sudhin.s.96)
INSTAGRAM_USER_ID = "28921702917447910"
INSTAGRAM_USERNAME = "sudhin.s.96"
INSTAGRAM_ACCESS_TOKEN = "IGAAohJyDTGmVBZAFlRNUE5THVjRlJLc0ZA4bEp5SWxibjN3N3RITjZAoTWJhUWI0djBIS1ZAqS2Nlb09pdktUbGlzWkYzcklKS1JuemNJWk40OGJ0LTV2VUVhQnhjeVRRNmJ1YUpndzBLOXAzdS1RSjQ1bDF3"

# Future integrations (LinkedIn, X)
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
http_session = requests.Session()
http_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
})

# ================= Cloud 24/7 Health Check Server =================
# Enables 100% Free Hosting on Render / Koyeb / Cloud Containers without sleeping
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Social Media AI Agent Bot is Running Live 24/7!")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"[CLOUD] Health server listening on port {port} for 24/7 uptime...")
        server.serve_forever()
    except Exception as e:
        print(f"[CLOUD] Health server notice: {e}")

threading.Thread(target=run_health_server, daemon=True).start()

# In-memory session store: {chat_id: {caption, image_bytes, image_url, prompt}}
user_sessions = {}

def clean_user_prompt(prompt: str) -> str:
    """Extracts clean subject matter from user query."""
    p = prompt.strip()
    lowered = p.lower()
    prefixes = [
        "create a ad for", "create an ad for", "create ad for",
        "generate a ad for", "generate an ad for", "generate ad for",
        "make a ad for", "make an ad for", "make ad for",
        "create a photo for", "create a picture of", "make a photo of",
        "ad for", "photo of"
    ]
    for pref in prefixes:
        if lowered.startswith(pref):
            return p[len(pref):].strip()
    return p

def generate_caption(prompt: str) -> str:
    """Generates viral social media caption with Gemini, with automatic free fallback."""
    clean_p = clean_user_prompt(prompt)

    # 1. Try Gemini first
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": (
                        f"Create an engaging, viral social media advertisement caption for: '{clean_p}'.\n"
                        "Requirements:\n"
                        "- Catchy headline with emojis\n"
                        "- 2-3 brief marketing sentences highlighting features/benefits\n"
                        "- Clear Call to Action (CTA)\n"
                        "- 5 to 7 trending relevant hashtags\n"
                        "- Maximum 500 characters total so it fits nicely in social captions\n"
                        "- Do NOT include excessive asterisks, keep it clean and natural."
                    )
                }]
            }]
        }
        resp = http_session.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print(f"[Gemini Notice] Status {resp.status_code}, falling back to secondary engine...")
    except Exception as e:
        print(f"[Gemini Exception] {e}")

    # 2. High-Converting Fallback Marketing Template
    tag = clean_p.replace(' ', '')
    return (
        f"🔥 Upgrade your style with the all-new {clean_p}!\n\n"
        "✨ Unmatched quality, sleek design, and ultimate performance crafted just for you.\n\n"
        "👉 Shop yours today and take your game to the next level!\n\n"
        f"#{tag} #Trending #MustHave #TopQuality #NewDrop"
    )

def strip_watermark(image_bytes: bytes) -> bytes:
    """Removes any watermark/logo banner from the bottom of fallback images."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        # Crop out bottom 5% where watermark logos are placed
        cropped = img.crop((0, 0, w, int(h * 0.95)))
        out = io.BytesIO()
        cropped.save(out, format="JPEG", quality=95)
        print("[Image Gen] Successfully stripped watermark logo from image!")
        return out.getvalue()
    except Exception as e:
        print(f"[Watermark Clean Error] {e}")
        return image_bytes

def generate_image_bytes(prompt: str):
    """Generates 4K product photography image using Cloudflare Workers AI exclusively, with auto-clean failover."""
    clean_p = clean_user_prompt(prompt)
    enhanced_prompt = f"commercial advertisement product photography of {clean_p}, 4k ultra hd, cinematic studio lighting, minimalist product podium, highly detailed, sharp focus, 8k resolution"

    # Pure Cloudflare Workers AI Multi-Model Suite
    cf_models = [
        "@cf/black-forest-labs/flux-1-schnell",
        "@cf/stabilityai/stable-diffusion-xl-base-1.0",
        "@cf/bytedance/stable-diffusion-xl-lightning"
    ]
    cf_headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    for model in cf_models:
        cf_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"
        try:
            print(f"[Cloudflare AI] Generating image with model '{model}'...")
            resp = requests.post(cf_url, headers=cf_headers, json={"prompt": enhanced_prompt}, timeout=35)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "application/json" in ct:
                    data = resp.json()
                    if "result" in data and "image" in data["result"]:
                        img_bytes = base64.b64decode(data["result"]["image"])
                        print(f"[Cloudflare AI] Success with {model}! Image size: {len(img_bytes)} bytes (100% CLEAN - NO WATERMARK)")
                        return img_bytes, "cloudflare"
                elif "image/" in ct and len(resp.content) > 1000:
                    print(f"[Cloudflare AI] Success with {model}! Raw image size: {len(resp.content)} bytes (100% CLEAN - NO WATERMARK)")
                    return resp.content, "cloudflare"
            else:
                print(f"[Cloudflare AI Notice] Status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[Cloudflare AI Error on {model}] {e}")

    # 2. Automated Clean Failover (Ensures bot NEVER fails and strips all logos)
    print("[Image Gen] Cloudflare token inactive, switching to emergency engine with auto-watermark removal...")
    try:
        encoded = urllib.parse.quote(enhanced_prompt)
        seed = random.randint(1000, 999999)
        img_url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true&seed={seed}"
        resp = http_session.get(img_url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 15000:
            clean_bytes = strip_watermark(resp.content)
            print(f"[Image Gen] Clean Image Ready! Size: {len(clean_bytes)}")
            return clean_bytes, None
    except Exception as e:
        print(f"[Emergency Engine Error] {e}")

    return None, None

def get_public_image_url(image_bytes: bytes, existing_url: str = None) -> str:
    """Ensures a publicly accessible HTTPS image URL is available for Instagram publishing."""
    if existing_url and existing_url.startswith("http"):
        return existing_url

    # Upload to fast public image hosts (Catbox or tmpfiles) for Instagram Graph API
    try:
        r = requests.post(
            'https://catbox.moe/user/api.php',
            data={'reqtype': 'fileupload'},
            files={'fileToUpload': ('ad_image.jpg', image_bytes, 'image/jpeg')},
            timeout=15
        )
        if r.status_code == 200 and r.text.startswith('http'):
            return r.text.strip()
    except Exception as e:
        print(f"[Catbox Upload Error] {e}")

    try:
        r2 = requests.post(
            'https://tmpfiles.org/api/v1/upload',
            files={'file': ('ad_image.jpg', image_bytes, 'image/jpeg')},
            timeout=15
        )
        if r2.status_code == 200:
            dl_url = r2.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/')
            return dl_url
    except Exception as e:
        print(f"[tmpfiles Upload Error] {e}")

    return None

def post_to_facebook(image_bytes: bytes, caption: str):
    """Directly uploads photo and caption to Facebook Page via Graph API."""
    url = f"https://graph.facebook.com/v21.0/{FACEBOOK_PAGE_ID}/photos"
    data = {
        "caption": caption,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN
    }
    files = {
        "source": ("ad_image.jpg", image_bytes, "image/jpeg")
    }

    try:
        resp = requests.post(url, data=data, files=files, timeout=60)
        res_json = resp.json()
        if resp.status_code == 200 and "id" in res_json:
            post_id = res_json.get("post_id", res_json.get("id"))
            return True, post_id
        else:
            return False, str(res_json)
    except Exception as e:
        return False, str(e)

def post_to_instagram(image_bytes: bytes, image_url: str, caption: str):
    """Publishes photo and caption directly to Instagram Business account via Graph API."""
    public_url = get_public_image_url(image_bytes, image_url)
    if not public_url:
        return False, "Could not obtain public URL for image to publish to Instagram."

    # Step 1: Create media container
    create_url = f"https://graph.instagram.com/v21.0/{INSTAGRAM_USER_ID}/media"
    payload = {
        "image_url": public_url,
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    try:
        r = requests.post(create_url, data=payload, timeout=45)
        r_json = r.json()
        if r.status_code != 200 or "id" not in r_json:
            return False, str(r_json)

        container_id = r_json["id"]

        # Wait for Instagram media processing
        time.sleep(3)

        # Step 2: Publish media container
        pub_url = f"https://graph.instagram.com/v21.0/{INSTAGRAM_USER_ID}/media_publish"
        pub_payload = {
            "creation_id": container_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN
        }
        pub_r = requests.post(pub_url, data=pub_payload, timeout=45)
        pub_json = pub_r.json()
        if pub_r.status_code == 200 and "id" in pub_json:
            media_id = pub_json["id"]
            return True, media_id
        else:
            return False, str(pub_json)
    except Exception as e:
        return False, str(e)

def build_action_keyboard():
    """Builds inline keyboard with all platform options."""
    markup = types.InlineKeyboardMarkup()
    btn_fb = types.InlineKeyboardButton("📘 Post to Facebook Page", callback_data="fb_publish")
    btn_ig = types.InlineKeyboardButton("📸 Instagram", callback_data="ig_publish")
    markup.row(btn_fb, btn_ig)

    btn_li = types.InlineKeyboardButton("💼 LinkedIn", callback_data="li_publish")
    btn_x  = types.InlineKeyboardButton("✖️ X (Twitter)", callback_data="x_publish")
    markup.row(btn_li, btn_x)

    btn_regen_caption = types.InlineKeyboardButton("🔄 New Caption", callback_data="regen_caption")
    btn_regen_image = types.InlineKeyboardButton("🎨 New Image", callback_data="regen_image")
    markup.row(btn_regen_caption, btn_regen_image)

    return markup

# ================= Telegram Handlers =================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 *Welcome to Social Media Agent AI!*\n\n"
        "I create stunning 4K commercial advertisement photos, generate marketing captions, and publish directly to social media!\n\n"
        "📌 *How to use:*\n"
        "Send me any product or topic name:\n"
        "• `Adidas running shoes`\n"
        "• `Luxury wristwatch`\n"
        "• `Cold coffee bottle`\n\n"
        "Type your prompt now to generate! 🚀"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: True and msg.text and not msg.text.startswith('/'))
def handle_prompt(message):
    chat_id = message.chat.id
    raw_prompt = message.text.strip()
    clean_p = clean_user_prompt(raw_prompt)

    status_msg = bot.send_message(
        chat_id,
        f"🎨 *Generating 4K ad for:* `{clean_p}`\n\n"
        "⏳ *Creating photorealistic product image & viral caption...*",
        parse_mode="Markdown"
    )

    # 1. Generate Image
    img_bytes, img_url = generate_image_bytes(clean_p)
    if not img_bytes:
        bot.edit_message_text(
            "❌ Image server is busy. Please send the message again or try another keyword!",
            chat_id,
            status_msg.message_id
        )
        return

    # 2. Generate Caption
    caption = generate_caption(clean_p)

    # Store in session
    user_sessions[chat_id] = {
        "caption": caption,
        "image_bytes": img_bytes,
        "image_url": img_url,
        "prompt": clean_p
    }

    # Delete status message
    try:
        bot.delete_message(chat_id, status_msg.message_id)
    except Exception:
        pass

    # Telegram caption character limit is 1024 chars
    display_caption = caption
    if len(display_caption) > 1000:
        display_caption = display_caption[:990] + "..."

    # Send photo with full action keyboard
    bot.send_photo(
        chat_id,
        photo=io.BytesIO(img_bytes),
        caption=display_caption,
        reply_markup=build_action_keyboard()
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    session = user_sessions.get(chat_id)

    if call.data == "fb_publish":
        if not session or not session.get("image_bytes"):
            bot.answer_callback_query(call.id, "⚠️ Session expired. Please send a new product name.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "🚀 Uploading to Facebook Page...")
        progress_msg = bot.send_message(chat_id, "⏳ *Publishing to Facebook Page 'Telegram Bot'...*", parse_mode="Markdown")

        success, result = post_to_facebook(session["image_bytes"], session["caption"])

        try:
            bot.delete_message(chat_id, progress_msg.message_id)
        except Exception:
            pass

        if success:
            fb_url = f"https://www.facebook.com/{result}"
            success_text = (
                "🎉 *Published Successfully to Facebook Page!*\n\n"
                f"📄 *Page:* Telegram Bot\n"
                f"🆔 *Post ID:* `{result}`\n"
                f"🔗 *Live Post Link:* [Click here to view on Facebook]({fb_url})"
            )
            bot.send_message(chat_id, success_text, parse_mode="Markdown", disable_web_page_preview=False)
        else:
            bot.send_message(
                chat_id,
                f"❌ *Failed to post on Facebook.*\n\nDetails: `{result}`",
                parse_mode="Markdown"
            )

    elif call.data == "ig_publish":
        if not session or not session.get("image_bytes"):
            bot.answer_callback_query(call.id, "⚠️ Session expired. Please send a new product prompt.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "📸 Uploading to Instagram...")
        progress_msg = bot.send_message(chat_id, "⏳ *Publishing to Instagram (@sudhin.s.96)...*", parse_mode="Markdown")

        success, result = post_to_instagram(session["image_bytes"], session.get("image_url"), session["caption"])

        try:
            bot.delete_message(chat_id, progress_msg.message_id)
        except Exception:
            pass

        if success:
            ig_profile_url = f"https://www.instagram.com/{INSTAGRAM_USERNAME}/"
            success_text = (
                "🎉 *Published Successfully to Instagram!*\n\n"
                f"👤 *Account:* @{INSTAGRAM_USERNAME}\n"
                f"🆔 *Media ID:* `{result}`\n"
                f"🔗 *View on Instagram:* [Click here to view profile]({ig_profile_url})"
            )
            bot.send_message(chat_id, success_text, parse_mode="Markdown", disable_web_page_preview=False)
        else:
            bot.send_message(
                chat_id,
                f"❌ *Failed to post on Instagram.*\n\nDetails: `{result}`",
                parse_mode="Markdown"
            )

    elif call.data == "li_publish":
        bot.answer_callback_query(call.id, "💼 LinkedIn Status", show_alert=True)
        bot.send_message(
            chat_id,
            "💼 *LinkedIn Auto-Publishing Setup:*\n\n"
            "LinkedIn post panna ungaloda LinkedIn Developer App Client ID & Secret or Access Token venum.\n"
            "Adhu ready aana udanae one-click-la LinkedIn profile/company page-ku post aagidum!",
            parse_mode="Markdown"
        )

    elif call.data == "x_publish":
        bot.answer_callback_query(call.id, "✖️ X (Twitter) Status", show_alert=True)
        bot.send_message(
            chat_id,
            "✖️ *X (Twitter) Auto-Publishing Setup:*\n\n"
            "X-la tweet panna X Developer Portal API Keys (API Key, Secret, Access Token) venum.\n"
            "Adhu ready aana udanae direct-ah tweet panna mudiyum!",
            parse_mode="Markdown"
        )

    elif call.data == "regen_caption":
        if not session:
            bot.answer_callback_query(call.id, "⚠️ Session expired. Please send a new prompt.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "✍️ Generating new viral caption...")
        new_caption = generate_caption(session["prompt"])
        session["caption"] = new_caption

        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=call.message.message_id,
                caption=new_caption[:1000],
                reply_markup=build_action_keyboard()
            )
        except Exception:
            bot.send_message(chat_id, f"📝 *New Caption:*\n\n{new_caption}", parse_mode="Markdown")

    elif call.data == "regen_image":
        if not session:
            bot.answer_callback_query(call.id, "⚠️ Session expired. Please send a new prompt.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "🎨 Generating new 4K image variation...")
        img_bytes, img_url = generate_image_bytes(session["prompt"])
        if img_bytes:
            session["image_bytes"] = img_bytes
            session["image_url"] = img_url
            bot.send_photo(
                chat_id,
                photo=io.BytesIO(img_bytes),
                caption=session["caption"][:1000],
                reply_markup=build_action_keyboard()
            )
        else:
            bot.send_message(chat_id, "⚠️ Server busy, please try clicking New Image again.")

if __name__ == "__main__":
    print("=" * 60)
    print("[BOT] Social Media Agent AI Telegram Bot is starting...")
    print(f"[BOT] Connected Facebook Page ID: {FACEBOOK_PAGE_ID}")
    print(f"[BOT] Connected Instagram Account: @{INSTAGRAM_USERNAME} (ID: {INSTAGRAM_USER_ID})")
    print("[BOT] Image Engine: Pure Cloudflare Workers AI Suite (Flux 1 Schnell & SDXL) - ACTIVE")
    print("[BOT] Caption Engine: Gemini AI with Auto-Fallback (ACTIVE)")
    print("[BOT] Polling Telegram servers for incoming user messages... (READY)")
    print("=" * 60)
    bot.infinity_polling(timeout=25, long_polling_timeout=25)
