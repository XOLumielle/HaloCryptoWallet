from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Load environment variables from Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Function to send messages to your Telegram
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    print(f"📤 Sending to Telegram:\n{data}")
    response = requests.post(url, json=data)
    print(f"📬 Telegram response: {response.status_code} {response.text}")

# Webhook endpoint Helius calls
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("🚨 Webhook HIT")
    print("📦 Incoming JSON:", data)

    if not data or "transactions" not in data:
        print("⚠️ Missing 'transactions' in payload.")
        return "No transaction data", 400

    for txn in data["transactions"]:
        description = txn.get("description", "Unknown activity")
        signature = txn.get("signature", "No signature")
        solscan_link = f"https://solscan.io/tx/{signature}"

        message = f"📡 *Wallet Activity Detected!*\n\n🔁 `{description}`\n🔗 [View on Solscan]({solscan_link})"
        send_telegram(message)

    return "OK", 200

# Default route for testing
@app.route("/", methods=["GET"])
def home():
    return "🟢 HaloCryptoWallet Webhook is live and listening!", 200

# Run the app on Railway's expected port (8080)
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
