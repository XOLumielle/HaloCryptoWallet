from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_SOL_THRESHOLD = 0.01
seen_signatures = set()

def get_token_info(token_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{token_address}"
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("pairs"):
            pair = data["pairs"][0]
            name = pair["baseToken"]["name"]
            symbol = pair["baseToken"]["symbol"]
            price = float(pair["priceUsd"])
            liquidity = float(pair["liquidity"]["usd"])
            return name, symbol, price, liquidity
    except Exception as e:
        print(f"❌ Dexscreener error: {e}")
    return None, None, None, None

def get_sol_price():
    _, _, price, _ = get_token_info("So11111111111111111111111111111111111111112")
    return price

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    print(f"📤 Telegram status: {response.status_code} {response.text}")

@app.route("/webhook", methods=["POST"])
def webhook():
    txs = request.json
    print("🚨 Webhook HIT")
    print(json.dumps(txs, indent=2))

    if not txs or not isinstance(txs, list):
        print("⚠️ Invalid webhook body")
        return "Invalid", 400

    sol_price = get_sol_price()
    print(f"💰 SOL price: {sol_price if sol_price else 'Unavailable'}")

    for tx in txs:
        signature = tx.get("signature")
        if not signature or signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        native = tx.get("nativeTransfers", [])
        if not native:
            print(f"⏩ No nativeTransfers for {signature}")
            continue

        amount = native[0].get("amount", 0) / 1_000_000_000
        if amount < MIN_SOL_THRESHOLD:
            print(f"⏩ Skipped tx {signature} — {amount:.6f} SOL below threshold")
            continue

        from_addr = native[0].get("fromUserAccount", "Unknown")
        to_addr = native[0].get("toUserAccount", "Unknown")
        usd_value = f"${amount * sol_price:,.2f}" if sol_price else "?"

        token_transfers = tx.get("tokenTransfers", [])
        token_address = token_transfers[0].get("tokenAddress") if token_transfers else None
        if token_address:
            token_name, symbol, token_price, liquidity = get_token_info(token_address)
        else:
            token_name = symbol = token_price = liquidity = None

        if symbol and token_price:
            token_display = f"${symbol} ({token_name})"
            token_address_display = f"`{token_address}`"
            price_display = f"${token_price:,.4f}"
            liquidity_display = f"${liquidity:,.0f}" if liquidity else "N/A"
            msg = (
                "*Smart Wallet Alert!*\n"
                f"*From:* `{from_addr}`\n"
                f"*To:* `{to_addr}`\n"
                f"*Sent:* {amount:.4f} SOL ({usd_value})\n"
                f"*Token:* {token_display}\n"
                f"*Token Address:* {token_address_display}\n"
                f"*Price:* {price_display} | Liquidity: {liquidity_display}\n"
                f"[View Tx](https://solscan.io/tx/{signature})"
            )
        else:
            msg = (
                "*Transfer Detected!*\n"
                f"*From:* `{from_addr}`\n"
                f"*To:* `{to_addr}`\n"
                f"*Amount:* {amount:.4f} SOL ({usd_value})\n"
                f"[View on Solscan](https://solscan.io/tx/{signature})"
            )

        print(f"📬 Sending alert for {signature} | {amount:.4f} SOL")
        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🟢 HaloBot is live without Solscan! Relying on Helius + Dexscreener", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
