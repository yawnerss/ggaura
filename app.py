from flask import Flask, request
import requests
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 🔐 Telegram Bot Token - Get from environment variable for security
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# 🔒 Global chat ID will be remembered after /start
chat_id_memory = {}

# ✅ Fetch Gamersberg Seed Stock
def get_stock_data():
    url = "https://www.gamersberg.com/api/grow-a-garden/stock"
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "cookie": "cumulative_time=s%3A0.xH%2BL%2Fg3BfTPO7XPfm8KfozrEogbraa49lNoWkQLmNUg; last_session_day=s%3A2025-06-19.y05Vg54Vmw6JXBmmoiSeZwamXN%2BU857bjMpX3Gw8yto; session_start=s%3A1750344784703.TkZ87AdtR7gb9IoNy9HoMtNDPYlkhlreJVYt5pnEkCM"
    }

    try:
        logger.info(f"Making request to: {url}")
        res = requests.get(url, headers=headers, timeout=10)
        
        logger.info(f"Status Code: {res.status_code}")
        res.raise_for_status()
        
        response_data = res.json()
        logger.info("Successfully parsed JSON response")
        
        if "data" not in response_data or not response_data["data"]:
            return "❌ No stock data available"
        
        # Get all data from the API response
        game_data = response_data["data"][0]
        result = "🎮 *Gamersberg Full Inventory:*\n\n"
        
        # Display all categories and their items
        for category, items in game_data.items():
            if isinstance(items, dict) and items:
                category_emoji = {
                    "seeds": "🌱",
                    "tools": "🔧", 
                    "equipment": "⚙️",
                    "weapons": "⚔️",
                    "armor": "🛡️",
                    "items": "📦",
                    "materials": "🧱",
                    "consumables": "🧪",
                    "gear": "⚙️"
                }
                
                emoji = category_emoji.get(category.lower(), "📋")
                result += f"{emoji} *{category.upper()}:*\n"
                
                for name, count in items.items():
                    if count == "0" or count == 0:
                        result += f"  ❌ {name}: OUT OF STOCK\n"
                    else:
                        result += f"  ✅ {name}: {count}\n"
                
                result += "\n"
        
        return result.strip()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return f"❌ Network error: Unable to fetch stock data"
    except (KeyError, IndexError) as e:
        logger.error(f"Data parsing error: {e}")
        return "❌ Error parsing stock data"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"❌ Failed to fetch stock: {str(e)}"

# ✅ Send message via Telegram
def send_message(chat_id, text):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage", 
            json=payload,
            timeout=10
        )
        
        logger.info(f"Sending message to {chat_id}")
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")

# ✅ Process incoming message
def process_message(message):
    try:
        chat_id = message["chat"]["id"]
        user = message["chat"].get("first_name", "User")
        msg = message.get("text", "").strip()

        logger.info(f"User: {user} (ID: {chat_id}) - Message: '{msg}'")

        # Remember this chat ID
        chat_id_memory["id"] = chat_id
        chat_id_memory["user"] = user

        if msg == "/start":
            welcome_msg = f"👋 Hello *{user}* a.k.a *R1C4RD0*!\n🌱 Welcome to the Gamersberg Stock Bot!"
            send_message(chat_id, welcome_msg)
            # Auto-trigger stock data after greeting
            stock_data = get_stock_data()
            send_message(chat_id, stock_data)
            
        elif msg.lower() in ["stock", "/stock"]:
            send_message(chat_id, get_stock_data())
            
        else:
            help_msg = "❓ Available commands:\n• `/start` - Start the bot and get stock\n• `stock` - Check current stock"
            send_message(chat_id, help_msg)
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")

# ✅ Webhook route (for production)
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info("Webhook received")

        if not data:
            logger.error("No data received")
            return "no data", 400

        if "message" in data:
            process_message(data["message"])
        elif "callback_query" in data:
            logger.info("Callback query received")
        else:
            logger.info("Unknown update type")
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "error", 500
    
    return "ok", 200

# ✅ Trigger route for auto-update
@app.route("/trigger", methods=["GET"])
def trigger():
    try:
        if "id" not in chat_id_memory:
            return "❌ No chat ID stored. Open bot and type /start first.", 400
        
        stock_data = get_stock_data()
        send_message(chat_id_memory["id"], f"🔄 *Auto Update*\n\n{stock_data}")
        return "✅ Stock update sent.", 200
        
    except Exception as e:
        logger.error(f"Trigger error: {e}")
        return f"❌ Error: {str(e)}", 500

# ✅ Health check route
@app.route("/", methods=["GET"])
def home():
    return "🚀 Bot is up and running on Render!"

# ✅ Set webhook route
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    try:
        # Get the render URL from environment or construct it
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if not render_url:
            # Fallback to manual URL construction
            service_name = os.getenv("RENDER_SERVICE_NAME", "telegram-stock-bot")
            render_url = f"https://{service_name}.onrender.com"
        
        webhook_url = f"{render_url}/webhook/{BOT_TOKEN}"
        
        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url}
        )
        
        result = response.json()
        logger.info(f"Webhook setup result: {result}")
        
        if result.get("ok"):
            return f"✅ Webhook set successfully to: {webhook_url}"
        else:
            return f"❌ Failed to set webhook: {result.get('description', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return f"❌ Error setting webhook: {e}", 500

# ✅ Clear webhook manually
@app.route("/clear_webhook", methods=["GET"])
def clear_webhook():
    try:
        response = requests.post(f"{TELEGRAM_API}/deleteWebhook")
        result = response.json()
        logger.info(f"Webhook clear result: {result}")
        return f"Webhook cleared: {result}"
    except Exception as e:
        return f"❌ Error clearing webhook: {e}", 500

# ✅ Get bot info
@app.route("/bot_info", methods=["GET"])
def bot_info():
    try:
        response = requests.get(f"{TELEGRAM_API}/getMe")
        return response.json()
    except Exception as e:
        return f"❌ Error getting bot info: {e}", 500

# ✅ Check webhook status
@app.route("/webhook_info", methods=["GET"])
def webhook_info():
    try:
        response = requests.get(f"{TELEGRAM_API}/getWebhookInfo")
        return response.json()
    except Exception as e:
        return f"❌ Error getting webhook info: {e}", 500

# ✅ Flask App Runner
if __name__ == "__main__":
    logger.info("🚀 Starting Telegram Bot for Render...")
    logger.info(f"📡 Bot Token: {BOT_TOKEN[:10] if BOT_TOKEN else 'NOT SET'}...")
    
    # Test bot connectivity
    try:
        response = requests.get(f"{TELEGRAM_API}/getMe")
        if response.status_code == 200:
            bot_info = response.json()["result"]
            logger.info(f"✅ Bot connected: @{bot_info['username']}")
        else:
            logger.error("❌ Bot token may be invalid")
    except Exception as e:
        logger.error(f"❌ Error connecting to bot: {e}")
    
    # Get port from environment (Render provides this)
    port = int(os.getenv("PORT", 10000))
    
    logger.info(f"📡 Running in WEBHOOK mode on port {port}")
    logger.info(f"📡 Webhook endpoint: /webhook/{BOT_TOKEN}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
