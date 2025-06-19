from flask import Flask, request
import requests
import json
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 🔐 Telegram Bot Token - Get from environment variable for security
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# 🔒 Global storage for multiple users
user_storage = {}

# ✅ Fetch Gamersberg Seed Stock
def get_stock_data():
    url = "https://www.gamersberg.com/api/grow-a-garden/stock"
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "cookie": "cumulative_time=s%3A0.xH%2BL%2Fg3BfTPO7XPfm8KfozrEogbraa49lNoWkQLmNUg; last_session_day=s%3A2025-06-19.y05Vg54Vmw6JXBmmoiSeZwamXN%2BU857bjMpX3Gw8yto; session_start=s%3A1750344784703.TkZ87AdtR7gb9IoNy9HoMtNDPYlkhlreJVYt5pnEkCM"
    }

    try:
        logger.info(f"🌐 Making request to: {url}")
        res = requests.get(url, headers=headers, timeout=15)
        
        logger.info(f"📊 Status Code: {res.status_code}")
        res.raise_for_status()
        
        response_data = res.json()
        logger.info("✅ Successfully parsed JSON response")
        
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
        logger.error(f"❌ Request error: {e}")
        return f"❌ Network error: Unable to fetch stock data\nError: {str(e)}"
    except (KeyError, IndexError) as e:
        logger.error(f"❌ Data parsing error: {e}")
        return "❌ Error parsing stock data"
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return f"❌ Failed to fetch stock: {str(e)}"

# ✅ Send message via Telegram with better error handling
def send_message(chat_id, text, parse_mode="Markdown"):
    try:
        # Split long messages if needed
        max_length = 4096
        if len(text) > max_length:
            parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            for part in parts:
                send_single_message(chat_id, part, parse_mode)
        else:
            send_single_message(chat_id, text, parse_mode)
            
    except Exception as e:
        logger.error(f"❌ Error in send_message: {e}")

def send_single_message(chat_id, text, parse_mode="Markdown"):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage", 
            json=payload,
            timeout=15
        )
        
        logger.info(f"📤 Sending message to {chat_id}: {text[:50]}...")
        logger.info(f"📤 Telegram API response: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to send message: {response.text}")
            # Try without markdown if it fails
            if parse_mode == "Markdown":
                payload["parse_mode"] = None
                response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)
                logger.info(f"📤 Retry without markdown: {response.status_code}")
        else:
            logger.info("✅ Message sent successfully")
            
    except Exception as e:
        logger.error(f"❌ Error sending single message: {e}")

# ✅ Create personalized greeting
def create_greeting(user_info):
    first_name = user_info.get("first_name", "Friend")
    username = user_info.get("username", "")
    
    current_time = datetime.now()
    hour = current_time.hour
    
    # Time-based greeting
    if 5 <= hour < 12:
        time_greeting = "Good morning"
    elif 12 <= hour < 17:
        time_greeting = "Good afternoon"
    elif 17 <= hour < 21:
        time_greeting = "Good evening"
    else:
        time_greeting = "Good night"
    
    greeting = f"🌟 {time_greeting}, *{first_name}*"
    if username:
        greeting += f" (@{username})"
    
    greeting += "!\n\n"
    greeting += "🎮 Welcome to the *Gamersberg Stock Bot*!\n"
    greeting += "🌱 I'll help you track seed inventory and stock levels.\n\n"
    greeting += "📋 *Available Commands:*\n"
    greeting += "• `/start` - Show this welcome message\n"
    greeting += "• `/stock` - Get current stock levels\n"
    greeting += "• `/help` - Show help information\n"
    greeting += "• `/status` - Check bot status\n\n"
    greeting += "🔄 *Auto Updates:* I'll send you stock updates every 5 minutes!\n"
    greeting += "⏰ *Current Time:* " + current_time.strftime("%Y-%m-%d %H:%M:%S UTC") + "\n\n"
    greeting += "🚀 Let's get started! Fetching your first stock update..."
    
    return greeting

# ✅ Process incoming message with improved handling
def process_message(message):
    try:
        chat_id = message["chat"]["id"]
        user_info = message["chat"]
        msg = message.get("text", "").strip()

        logger.info(f"👤 Processing message from {user_info.get('first_name', 'Unknown')} (ID: {chat_id})")
        logger.info(f"💬 Message: '{msg}'")

        # Store user information
        user_storage[chat_id] = {
            "user_info": user_info,
            "last_seen": datetime.now().isoformat(),
            "message_count": user_storage.get(chat_id, {}).get("message_count", 0) + 1
        }

        if msg == "/start":
            # Send personalized greeting
            greeting = create_greeting(user_info)
            send_message(chat_id, greeting)
            
            # Wait a moment then send stock data
            import time
            time.sleep(2)
            
            stock_data = get_stock_data()
            send_message(chat_id, f"📊 *Initial Stock Report:*\n\n{stock_data}")
            
        elif msg.lower() in ["stock", "/stock"]:
            send_message(chat_id, "🔄 Fetching latest stock data...")
            stock_data = get_stock_data()
            send_message(chat_id, stock_data)
            
        elif msg.lower() in ["help", "/help"]:
            help_msg = "🆘 *Help & Commands:*\n\n"
            help_msg += "📋 *Available Commands:*\n"
            help_msg += "• `/start` - Welcome message and initial stock\n"
            help_msg += "• `/stock` - Get current stock levels\n"
            help_msg += "• `/help` - Show this help message\n"
            help_msg += "• `/status` - Check bot and API status\n\n"
            help_msg += "🔄 *Auto Updates:*\n"
            help_msg += "The bot automatically sends stock updates every 5 minutes.\n\n"
            help_msg += "❓ *Need Support?*\n"
            help_msg += "Contact the bot administrator if you experience issues."
            send_message(chat_id, help_msg)
            
        elif msg.lower() in ["status", "/status"]:
            status_msg = "🔍 *Bot Status Check:*\n\n"
            status_msg += f"✅ Bot is online and running\n"
            status_msg += f"📊 Total registered users: {len(user_storage)}\n"
            status_msg += f"💬 Your message count: {user_storage[chat_id]['message_count']}\n"
            status_msg += f"⏰ Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            
            # Test API connection
            try:
                test_stock = get_stock_data()
                if "❌" not in test_stock:
                    status_msg += "🌐 Gamersberg API: ✅ Connected\n"
                else:
                    status_msg += "🌐 Gamersberg API: ❌ Error\n"
            except:
                status_msg += "🌐 Gamersberg API: ❌ Connection failed\n"
                
            send_message(chat_id, status_msg)
            
        else:
            # Unknown command
            unknown_msg = f"❓ I don't understand '{msg}'\n\n"
            unknown_msg += "📋 *Available Commands:*\n"
            unknown_msg += "• `/start` - Welcome message\n"
            unknown_msg += "• `/stock` - Get stock levels\n"
            unknown_msg += "• `/help` - Show help\n"
            unknown_msg += "• `/status` - Bot status"
            send_message(chat_id, unknown_msg)
            
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        try:
            send_message(chat_id, "❌ Sorry, I encountered an error processing your message. Please try again.")
        except:
            pass

# ✅ Webhook route with better logging
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info("📥 Webhook received")
        logger.info(f"📥 Webhook data: {json.dumps(data, indent=2)}")

        if not data:
            logger.error("❌ No data received in webhook")
            return "no data", 400

        if "message" in data:
            process_message(data["message"])
        elif "callback_query" in data:
            logger.info("📞 Callback query received")
        else:
            logger.info("❓ Unknown update type received")
    
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return "error", 500
    
    return "ok", 200

# ✅ Trigger route for auto-updates
@app.route("/trigger", methods=["GET"])
def trigger():
    try:
        if not user_storage:
            return "❌ No users registered. Send /start to the bot first.", 400
        
        stock_data = get_stock_data()
        success_count = 0
        
        # Send to all registered users
        for chat_id in user_storage.keys():
            try:
                send_message(chat_id, f"🔄 *Auto Update - {datetime.now().strftime('%H:%M')}*\n\n{stock_data}")
                success_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to send auto-update to {chat_id}: {e}")
        
        return f"✅ Auto-update sent to {success_count}/{len(user_storage)} users.", 200
        
    except Exception as e:
        logger.error(f"❌ Trigger error: {e}")
        return f"❌ Error: {str(e)}", 500

# ✅ Health check route
@app.route("/", methods=["GET"])
def home():
    return f"🚀 Gamersberg Stock Bot is running! Users: {len(user_storage)}"

# ✅ Set webhook route with better error handling
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    try:
        # Get the render URL from environment or construct it
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if not render_url:
            service_name = os.getenv("RENDER_SERVICE_NAME", "telegram-stock-bot")
            render_url = f"https://{service_name}.onrender.com"
        
        webhook_url = f"{render_url}/webhook/{BOT_TOKEN}"
        
        logger.info(f"🔗 Setting webhook to: {webhook_url}")
        
        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url},
            timeout=15
        )
        
        result = response.json()
        logger.info(f"📡 Webhook setup result: {result}")
        
        if result.get("ok"):
            return f"✅ Webhook set successfully to: {webhook_url}"
        else:
            return f"❌ Failed to set webhook: {result.get('description', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        return f"❌ Error setting webhook: {e}", 500

# ✅ Test bot connection
@app.route("/test_bot", methods=["GET"])
def test_bot():
    try:
        response = requests.get(f"{TELEGRAM_API}/getMe", timeout=10)
        if response.status_code == 200:
            bot_info = response.json()["result"]
            return f"✅ Bot connected: @{bot_info['username']} ({bot_info['first_name']})"
        else:
            return f"❌ Bot connection failed: {response.text}"
    except Exception as e:
        return f"❌ Error testing bot: {e}"

# ✅ Clear webhook manually
@app.route("/clear_webhook", methods=["GET"])
def clear_webhook():
    try:
        response = requests.post(f"{TELEGRAM_API}/deleteWebhook", timeout=10)
        result = response.json()
        logger.info(f"📡 Webhook clear result: {result}")
        return f"Webhook cleared: {result}"
    except Exception as e:
        return f"❌ Error clearing webhook: {e}", 500

# ✅ Check webhook status
@app.route("/webhook_info", methods=["GET"])
def webhook_info():
    try:
        response = requests.get(f"{TELEGRAM_API}/getWebhookInfo", timeout=10)
        return response.json()
    except Exception as e:
        return f"❌ Error getting webhook info: {e}", 500

# ✅ Get user statistics
@app.route("/stats", methods=["GET"])
def stats():
    try:
        stats_data = {
            "total_users": len(user_storage),
            "users": []
        }
        
        for chat_id, user_data in user_storage.items():
            user_info = user_data.get("user_info", {})
            stats_data["users"].append({
                "chat_id": chat_id,
                "name": user_info.get("first_name", "Unknown"),
                "username": user_info.get("username"),
                "last_seen": user_data.get("last_seen"),
                "message_count": user_data.get("message_count", 0)
            })
        
        return stats_data
    except Exception as e:
        return f"❌ Error getting stats: {e}", 500

# ✅ Flask App Runner
if __name__ == "__main__":
    logger.info("🚀 Starting Telegram Bot for Render...")
    logger.info(f"📡 Bot Token: {BOT_TOKEN[:10] if BOT_TOKEN else 'NOT SET'}...")
    
    # Test bot connectivity on startup
    try:
        response = requests.get(f"{TELEGRAM_API}/getMe", timeout=10)
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
    logger.info("📡 After deployment, visit /set_webhook to configure the webhook")
    
    app.run(host="0.0.0.0", port=port, debug=False)
