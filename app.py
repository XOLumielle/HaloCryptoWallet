from flask import Flask, request
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=data)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return "No data received", 400

    for txn in data.get("transactions", []):
        signer = txn.get("description", "Unknown Activity")
        signature = txn.get("signature", "")
        link = f"https://solscan.io/tx/{signature}"
        msg = f"📡 *Wallet Activity Detected!*\n\n🔁 {signer}\n🔗 [View on Solscan]({link})"
        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Halo webhook bot is running!", 200

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))