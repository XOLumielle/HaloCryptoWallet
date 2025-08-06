from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Load your Telegram bot credentials from Railway environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Function to send messages to Telegram
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=data)
    print("Telegram response:", response.text)

# Main webhook route to receive POST requests from Helius
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("🔔 Webhook received:", data)

    if not data or "transactions" not in data:
        return "No transaction data", 400

    for txn in data["transactions"]:
        description = txn.get("description", "Unknown activity")
        signature = txn.get("signature", "Unknown signature")
        solscan_link = f"https://solscan.io/tx/{signature}"

        message = f"📡 *Wallet Activity Detected!*\n\n🔁 `{description}`\n🔗 [View on Solscan]({solscan_link})"
        send_telegram(message)

    return "OK", 200

# Optional home route to show that the server is alive
@app.route("/", methods=["GET"])
def home():
    return "HaloCryptoWallet Webhook is live! 🌙", 200

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
