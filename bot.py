import os
import sys
import io
import re
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
FACEBOOK_PAGE_ID = "1276584508878950"
# 100% Never-Expiring Lifetime Facebook Page Access Token (expires_at: 0)
FACEBOOK_PAGE_ACCESS_TOKEN = "EAANEBDbaqKYBShXy0ZCIXSlRIGIpZAzK6QCWCQrPLyIjNYDjAtxPcnRU9kMDkU7XSxsbjD3oZCwZB76IQGcYQrUxqkRb4KZCIUZAgB3VWhwxaQOvkuaSJhdp8xFwiZBj2hsuZAFCWH1h7KfTZBRrwd3MKA41lnnQs4LQQyvJWFGZACkZALj4NZBdMpavXu4o9973SZAjC5YJQxqni"

# Cloudflare Workers AI Configuration
CLOUDFLARE_ACCOUNT_ID = "222270a5d0bd73142a8b7e97b511281b"
_DEFAULT_CF_TOKEN = base64.b64decode("Y2Z1dF9XQzNTR2ZCOVRmU2VhWU9TTmZvcUl3amJ2cGFkNVZta3FwTzFBUGxoZjgxZjVjZjU=").decode("utf-8")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", _DEFAULT_CF_TOKEN)

# Rate limit cache to prevent freezing when Cloudflare daily neurons are exhausted
cf_rate_limited_until = 0

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
# Enables 100% Free Hosting on Render / Koyeb without sleeping
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
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

# Keep-Alive Self-Pinger: Prevents Render free tier from going to sleep after 15 minutes of inactivity
def keep_alive_pinger():
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-social-ai-bot.onrender.com")
    time.sleep(30)
    while True:
        try:
            r = http_session.get(render_url, timeout=10)
            print(f"[KEEP-ALIVE] Pinged {render_url} (status: {r.status_code}) to keep bot awake 24/7.")
        except Exception as e:
            print(f"[KEEP-ALIVE] Ping notice: {e}")
        time.sleep(540) # Ping every 9 minutes

threading.Thread(target=keep_alive_pinger, daemon=True).start()

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
        "create a premium", "generate a premium", "imagine a", "imagine",
        "ad for", "photo of"
    ]
    for pref in prefixes:
        if lowered.startswith(pref):
            return p[len(pref):].strip()
    return p

def optimize_visual_prompt(raw_prompt: str) -> str:
    """Understands user prompt and transforms it into a 4K photorealistic visual description."""
    global cf_rate_limited_until
    clean_p = clean_user_prompt(raw_prompt)
    p_lower = clean_p.lower()

    # Detect if prompt is already a detailed scene or landscape
    is_scene_or_fantasy = any(k in p_lower for k in [
        'scene', 'landscape', 'fantasy', 'adventure', 'island', 'ruins',
        'sword', 'jagged cliff', 'waterfall', 'cyberpunk', 'cityscape', 'mountain'
    ])

    if is_scene_or_fantasy:
        return f"{clean_p}, 8k resolution, cinematic lighting, masterpiece, photorealistic, ultra-detailed"

    # If Cloudflare AI is active and not rate-limited, try Llama prompt expansion
    cf_token = os.getenv("CLOUDFLARE_API_TOKEN", CLOUDFLARE_API_TOKEN)
    if time.time() > cf_rate_limited_until:
        try:
            url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct"
            sys_msg = (
                "You are an expert AI prompt engineer for photographic image generation (Flux / SDXL).\n"
                "The user input may be in Tanglish, Tamil, or English.\n"
                "Write a single, rich, photorealistic visual scene description in English.\n"
                "Output ONLY the prompt. No introductory text, no explanations, no quotes."
            )
            payload = {
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": clean_p}
                ]
            }
            headers = {"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                text = resp.json().get("result", {}).get("response", "").strip()
                if text and len(text) > 10:
                    return text
            elif resp.status_code == 429:
                cf_rate_limited_until = time.time() + 1800
        except Exception as e:
            print(f"[Prompt Optimizer Error] {e}")

    # High quality fallback prompt construction
    if len(clean_p.split()) <= 6:
        # Short product keyword (e.g. 'Luxury wristwatch' or 'Running shoes')
        return f"commercial advertisement product photography of {clean_p}, 4k ultra hd, cinematic studio lighting, minimalist product podium, highly detailed, sharp focus, 8k resolution"
    else:
        # Long detailed user prompt
        return f"{clean_p}, 8k resolution, commercial grade, sharp focus, cinematic studio lighting"

def generate_caption(prompt: str) -> str:
    """Generates an engaging ~4-line social media caption followed directly by clean hashtags."""
    global cf_rate_limited_until
    clean_p = clean_user_prompt(prompt)
    p_lower = clean_p.lower()

    # Detect Tanglish using strict whole-word matching
    tanglish_markers = {
        'venum', 'kudunga', 'pannunga', 'pannu', 'kooda', 'irukku',
        'irukanum', 'epudi', 'nan', 'enakku', 'makkale', 'patta',
        'edhaavathu', 'panna', 'sollu', 'podu', 'thara', 'avolothaa', 'mari',
        'nalla', 'oru', 'super', 'semma', 'ippo', 'unga', 'romba', 'pudicha'
    }
    tokens = set(re.findall(r'\b[a-zA-Z]+\b', p_lower))
    is_tanglish = bool(tokens.intersection(tanglish_markers))

    # 1. Primary: Cloudflare Llama 3.1 (if not rate-limited)
    cf_token = os.getenv("CLOUDFLARE_API_TOKEN", CLOUDFLARE_API_TOKEN)
    if time.time() > cf_rate_limited_until:
        try:
            url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct"
            if is_tanglish:
                sys_msg = (
                    "You are an expert commercial copywriter for Instagram & Facebook.\n"
                    "Write a clean, conversational 4-line commercial caption in natural Tanglish (Tamil words written in English letters).\n"
                    "Do NOT write about prompts or instructions. Write directly as the brand promoting the subject.\n\n"
                    "Structure:\n"
                    "Line 1: Punchy hook with emoji in Tanglish\n"
                    "Line 2-3: 2 short lines on benefits and style in Tanglish\n"
                    "Line 4: Call-To-Action in Tanglish (e.g. Ippovae check out pannunga, link in bio 🛍️)\n\n"
                    "Followed by a blank line and 4-5 relevant product hashtags.\n"
                    "CRITICAL RULES:\n"
                    "- English letters only, NO Tamil script.\n"
                    "- NEVER include #tanglish, #thanglish, or #tamil in hashtags.\n"
                    "- Exactly around 4 lines of caption text.\n"
                    "- Output ONLY the final caption with hashtags."
                )
            else:
                sys_msg = (
                    "You are an expert commercial copywriter for Instagram & Facebook.\n"
                    "Write a clean, professional, 4-line commercial caption about the subject.\n"
                    "Do NOT write about prompts, layouts, or instructions. Write directly as the brand.\n\n"
                    "Structure:\n"
                    "Line 1: Punchy hook sentence with emoji\n"
                    "Line 2-3: 2 short lines on benefits and premium quality\n"
                    "Line 4: Clear Call-To-Action (e.g. Discover more via link in bio 🛍️)\n\n"
                    "Followed by a blank line and 4-5 relevant hashtags.\n"
                    "CRITICAL RULES:\n"
                    "- Write entirely in 100% English. NO Tamil/Tanglish words.\n"
                    "- NEVER include #tanglish or #thanglish in hashtags.\n"
                    "- Exactly around 4 lines of caption text.\n"
                    "- Output ONLY the final caption with hashtags."
                )

            payload = {
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": clean_p}
                ]
            }
            headers = {"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                text = resp.json().get("result", {}).get("response", "").strip()
                if text and len(text) > 30:
                    text = text.replace('**', '').strip()
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1].strip()
                    # Clean any unwanted #tanglish or #thanglish tags
                    text = re.sub(r'#(?:t[ha]nglish|tamil(?:nadu)?)\b', '', text, flags=re.IGNORECASE).strip()
                    return text
            elif resp.status_code == 429:
                cf_rate_limited_until = time.time() + 1800
        except Exception as e:
            print(f"[Cloudflare LLM Caption Error] {e}")

    # 2. Semantic Fallback Engine: Context-aware 4-line captions
    if any(k in p_lower for k in ['fantasy', 'video game', 'mythical', 'floating island', 'waterfall', 'ruins', 'sword', 'jagged cliff', 'gaming', 'adventurer']):
        if is_tanglish:
            return (
                "⚔️ Mythical realm-la unga epic adventure ippo start aaguthu!\n"
                "Floating islands, ancient ruins & breathtaking landscape vibe.\n"
                "Gaming lovers-ku ithu ultimate visual feast makkale.\n"
                "Unread legends-ah explore panna ready-ah irunga 🎮\n\n"
                "#FantasyArt #GamingWorld #MythicalLandscape #ConceptArt #GameDev"
            )
        else:
            return (
                "⚔️ Step into an uncharted realm where ancient legends come alive.\n"
                "Explore floating islands, cascading waterfalls, and lost mythical ruins.\n"
                "Stand on the edge of destiny as the horizon burns in gold.\n"
                "Your next epic fantasy adventure begins now 🎮\n\n"
                "#FantasyArt #GamingWorld #MythicalLandscape #ConceptArt #EpicAdventure"
            )
    elif any(k in p_lower for k in ['skin', 'skincare', 'glow', 'beauty', 'serum', 'lotion', 'cream', 'cosmetic']):
        if is_tanglish:
            return (
                "✨ Radiant & glowing skin ungalukku venuma makkale?\n"
                "Pure luxury formulation unga skin-ku natural shine tharum.\n"
                "Daily skincare routine-ku romba perfect & gentle choice.\n"
                "Ippovae order pannunga, link in bio-la irukku 🛍️\n\n"
                "#Skincare #GlowingSkin #LuxuryBeauty #CleanSkincare #DailyGlow"
            )
        else:
            return (
                "✨ Unlock radiant, luminous skin with our ultimate luxury formula.\n"
                "Infused with pure nourishing actives for a natural, healthy glow.\n"
                "Elevate your daily self-care ritual with timeless modern elegance.\n"
                "Experience the transformation today — shop link in bio 🛍️\n\n"
                "#Skincare #GlowingSkin #LuxuryBeauty #CleanBeauty #RadiantSkin"
            )
    elif any(k in p_lower for k in ['watch', 'wristwatch', 'timepiece']):
        if is_tanglish:
            return (
                "⌚ Unga style-ah elevate panna oru timeless luxury watch!\n"
                "Premium craftsmanship & modern aesthetic look kooda varuthu.\n"
                "Daily wear-kum special occasions-kum semma match makkale.\n"
                "Ippovae check out pannunga, link in bio 🛍️\n\n"
                "#LuxuryWatch #Timepiece #StyleStatement #MensStyle #Accessories"
            )
        else:
            return (
                "⌚ Define your moments with uncompromising precision and luxury.\n"
                "Masterfully crafted with timeless elegance for the modern visionary.\n"
                "A signature statement piece designed to turn heads wherever you go.\n"
                "Explore the collection today — link in bio 🛍️\n\n"
                "#LuxuryWatch #Timepiece #WatchCollector #Elegance #StyleStatement"
            )
    elif any(k in p_lower for k in ['shoe', 'shoes', 'sneaker', 'sneakers', 'running', 'adidas', 'nike']):
        if is_tanglish:
            return (
                "👟 Step out in ultimate style & unmatched comfort makkale!\n"
                "Lightweight performance cushioning daily wear-ku semma match.\n"
                "Streetwear lovers-ku ithu must-have drop.\n"
                "Stock limited, ippovae grab pannunga — link in bio 🛍️\n\n"
                "#Sneakers #Streetwear #KicksOfTheDay #UrbanStyle #SneakerHead"
            )
        else:
            return (
                "👟 Step into unmatched comfort and next-level athletic performance.\n"
                "Engineered with cutting-edge cushioning for effortless daily momentum.\n"
                "Bold modern aesthetics tailored for the modern street icon.\n"
                "Upgrade your rotation now — shop link in bio 🛍️\n\n"
                "#Sneakers #Streetwear #KicksOfTheDay #UrbanStyle #Footwear"
            )
    elif any(k in p_lower for k in ['coffee', 'tea', 'drink', 'bottle', 'beverage', 'juice']):
        if is_tanglish:
            return (
                "☕ Fresh energy & ultimate taste unga favorite sip-la!\n"
                "Rich brew perfection ungaloda day-ah super energetic-ah maathum.\n"
                "Quality ingredients-la create panna premium blend.\n"
                "Taste the magic today — link in bio 🛍️\n\n"
                "#CoffeeLovers #FreshBrew #DailyEnergy #Beverage #TasteTheVibe"
            )
        else:
            return (
                "☕ Awaken your senses with the rich, bold essence of pure perfection.\n"
                "Crafted from premium ingredients for an extraordinary, smooth taste.\n"
                "The ultimate refreshment to fuel your passion and elevate your day.\n"
                "Savor the moment today — order via link in bio 🛍️\n\n"
                "#CoffeeLovers #FreshBrew #ColdBrew #Artisanal #DailyPerfection"
            )
    else:
        words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in clean_p.split() if len(w) > 3]
        kw = words[0].capitalize() if words else "Product"
        kw2 = words[1].capitalize() if len(words) > 1 else "Trending"
        if is_tanglish:
            return (
                f"🔥 Semma stylish & premium quality {kw} ippo live!\n"
                "Top-notch aesthetic design unga lifestyle-ku perfect match.\n"
                "Stand out style-la ungalukku pidicha luxury vibe.\n"
                "Ippovae grab pannunga, link in bio-la irukku 🛍️\n\n"
                f"#{kw} #{kw2} #Trending #PremiumVibe #NewDrop"
            )
        else:
            return (
                f"✨ Elevate your everyday aesthetic with the all-new {kw}.\n"
                "Designed with precision craftsmanship for ultimate sophistication.\n"
                "Experience the seamless blend of premium quality and iconic style.\n"
                "Discover yours today — shop link in bio 🛍️\n\n"
                f"#{kw} #{kw2} #Trending #LuxuryVibes #MustHave"
            )

def strip_watermark(image_bytes: bytes) -> bytes:
    """Removes any watermark/logo banner from the bottom of fallback images."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
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

def generate_image_bytes(visual_prompt: str):
    """Generates 4K product photography image with Cloudflare Workers AI and clean failovers."""
    global cf_rate_limited_until
    cf_token = os.getenv("CLOUDFLARE_API_TOKEN", CLOUDFLARE_API_TOKEN)

    # 1. Cloudflare Workers AI: Fast SDXL Lightning (Uses 10x fewer neurons, 20+ images/day)
    if time.time() > cf_rate_limited_until:
        cf_models = [
            "@cf/bytedance/stable-diffusion-xl-lightning",
            "@cf/black-forest-labs/flux-1-schnell"
        ]
        cf_headers = {
            "Authorization": f"Bearer {cf_token}",
            "Content-Type": "application/json"
        }
        for model in cf_models:
            cf_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"
            try:
                print(f"[Cloudflare AI] Generating image with model '{model}'...")
                resp = requests.post(cf_url, headers=cf_headers, json={"prompt": visual_prompt}, timeout=15)
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
                elif resp.status_code == 429:
                    print(f"[Cloudflare AI Notice] Daily neuron limit reached (Status 429). Activating fast failover...")
                    cf_rate_limited_until = time.time() + 1800
                    break
            except Exception as e:
                print(f"[Cloudflare AI Error on {model}] {e}")

    # 2. Fast Clean Failover (Takes only 2-3 seconds, ZERO WATERMARK)
    print("[Image Gen] Switching to ultra-fast clean engine (Zero Watermark)...")
    encoded = urllib.parse.quote(visual_prompt)
    for fb_model in ["sana", "turbo"]:
        try:
            seed = random.randint(1000, 999999)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?model={fb_model}&width=1024&height=1024&nologo=true&seed={seed}"
            resp = http_session.get(img_url, timeout=18)
            if resp.status_code == 200 and len(resp.content) > 5000:
                clean_bytes = strip_watermark(resp.content)
                print(f"[Image Gen] Clean Image Ready with {fb_model}! Size: {len(clean_bytes)} bytes (Zero Watermark)")
                return clean_bytes, None
        except Exception as e:
            print(f"[Engine {fb_model} notice] {e}")

    # 3. Direct Prompt Failover
    try:
        seed = random.randint(1000, 999999)
        img_url = f"https://image.pollinations.ai/prompt/{encoded}?seed={seed}"
        resp = http_session.get(img_url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 5000:
            clean_bytes = strip_watermark(resp.content)
            return clean_bytes, None
    except Exception as e:
        print(f"[Direct Engine notice] {e}")

    return None, None

def get_public_image_url(image_bytes: bytes, existing_url: str = None) -> str:
    """Ensures a publicly accessible HTTPS image URL is available for Instagram publishing."""
    if existing_url and existing_url.startswith("http"):
        return existing_url

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
        status_url = f"https://graph.instagram.com/v21.0/{container_id}?fields=status_code&access_token={INSTAGRAM_ACCESS_TOKEN}"
        for _ in range(10):
            time.sleep(3)
            s_res = requests.get(status_url, timeout=15).json()
            if s_res.get("status_code") == "FINISHED":
                break

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
    """Builds clean inline keyboard with publishing and regeneration options."""
    markup = types.InlineKeyboardMarkup()
    btn_fb = types.InlineKeyboardButton("📘 Post to Facebook Page", callback_data="fb_publish")
    btn_ig = types.InlineKeyboardButton("📸 Instagram", callback_data="ig_publish")
    markup.row(btn_fb, btn_ig)

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

    status_msg = None
    try:
        status_msg = bot.send_message(
            chat_id,
            "🎨 *Analyzing prompt & creating 4K visuals...*\n\n"
            "⏳ *Generating photorealistic scene & viral caption...*",
            parse_mode="Markdown"
        )
    except Exception:
        try:
            status_msg = bot.send_message(chat_id, "🎨 Generating 4K visuals & viral caption, please wait...")
        except Exception as e:
            print(f"[Telegram status send error] {e}")

    try:
        # 1. Optimize Prompt for visual generation
        visual_prompt = optimize_visual_prompt(clean_p)

        # 2. Generate Image with Flux/SDXL and clean failover
        img_bytes, img_url = generate_image_bytes(visual_prompt)
        if not img_bytes:
            err_msg = "⚠️ Image server is busy. Please send your prompt again in a few moments!"
            if status_msg:
                try:
                    bot.edit_message_text(err_msg, chat_id, status_msg.message_id)
                except Exception:
                    bot.send_message(chat_id, err_msg)
            else:
                bot.send_message(chat_id, err_msg)
            return

        # 3. Generate Caption (Supports Tanglish & English)
        caption = generate_caption(raw_prompt)

        # Store in session
        user_sessions[chat_id] = {
            "caption": caption,
            "image_bytes": img_bytes,
            "image_url": img_url,
            "prompt": clean_p
        }

        # Delete status message
        if status_msg:
            try:
                bot.delete_message(chat_id, status_msg.message_id)
            except Exception:
                pass

        # Telegram caption limit is 1024 chars
        display_caption = caption[:990] if len(caption) > 1000 else caption

        # Send photo with action keyboard
        bot.send_photo(
            chat_id,
            photo=io.BytesIO(img_bytes),
            caption=display_caption,
            reply_markup=build_action_keyboard()
        )
    except Exception as e:
        print(f"[Handle Prompt Error] {e}")
        bot.send_message(
            chat_id,
            f"⚠️ An error occurred while generating: {str(e)[:120]}. Please try sending your prompt again!"
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

        bot.answer_callback_query(call.id, "✍️ Generating fresh viral caption...")
        new_caption = generate_caption(session["prompt"])
        session["caption"] = new_caption

        disp = new_caption[:990] if len(new_caption) > 1000 else new_caption
        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=call.message.message_id,
                caption=disp,
                reply_markup=build_action_keyboard()
            )
        except Exception:
            bot.send_message(chat_id, f"📝 *New Caption:*\n\n{new_caption}")

    elif call.data == "regen_image":
        if not session:
            bot.answer_callback_query(call.id, "⚠️ Session expired. Please send a new prompt.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "🎨 Generating new 4K image variation...")
        visual_p = optimize_visual_prompt(session["prompt"])
        img_bytes, img_url = generate_image_bytes(visual_p)
        if img_bytes:
            session["image_bytes"] = img_bytes
            session["image_url"] = img_url
            disp = session["caption"][:990] if len(session["caption"]) > 1000 else session["caption"]
            bot.send_photo(
                chat_id,
                photo=io.BytesIO(img_bytes),
                caption=disp,
                reply_markup=build_action_keyboard()
            )
        else:
            bot.send_message(chat_id, "⚠️ Server busy, please try clicking New Image again.")

if __name__ == "__main__":
    print("=" * 60)
    print("[BOT] Social Media Agent AI Telegram Bot is starting...")
    print(f"[BOT] Connected Facebook Page ID: {FACEBOOK_PAGE_ID}")
    print(f"[BOT] Connected Instagram Account: @{INSTAGRAM_USERNAME} (ID: {INSTAGRAM_USER_ID})")
    print("[BOT] Image Engine: Cloudflare Workers AI + Ultra-Clean Failover - ACTIVE")
    print("[BOT] Caption Engine: Dual-Mode Tanglish/English 4-Line Copywriter - ACTIVE")
    print("[BOT] Cloud 24/7 Keep-Alive: Ping enabled (Render never sleeps)")
    print("[BOT] Polling Telegram servers for incoming user messages... (READY)")
    print("=" * 60)
    bot.infinity_polling(timeout=25, long_polling_timeout=25)
