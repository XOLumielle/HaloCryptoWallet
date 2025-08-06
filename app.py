from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_SOL_THRESHOLD = 0.01
seen_signatures = set()
LABELS_FILE = "wallet_labels.json"

# Load saved labels from file
def load_labels():
    if os.path.exists(LABELS_FILE):
        with open(LABELS_FILE, "r") as f:
            return json.load(f)
    return {}

# Save label dictionary to file
def save_labels(data):
    with open(LABELS_FILE, "w") as f:
        json.dump(data, f, indent=2)

wallet_labels = load_labels()

def label_wallet(addr):
    return wallet_labels.get(addr, addr)

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
    requests.post(url, json=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    txs = request.json
    print("🚨 Webhook HIT")

    if not txs or not isinstance(txs, list):
        print("⚠️ Invalid webhook body")
        return "Invalid", 400

    sol_price = get_sol_price()

    for tx in txs:
        signature = tx.get("signature")
        if not signature or signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        native = tx.get("nativeTransfers", [])
        if not native:
            continue

        amount = native[0].get("amount", 0) / 1_000_000_000
        if amount < MIN_SOL_THRESHOLD:
            continue

        from_addr_raw = native[0].get("fromUserAccount", "Unknown")
        to_addr_raw = native[0].get("toUserAccount", "Unknown")
        from_addr = label_wallet(from_addr_raw)
        to_addr = label_wallet(to_addr_raw)
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

        send_telegram(msg)

    return "OK", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_label_command():
    data = request.json
    if "message" not in data:
        return "OK", 200

    text = data["message"].get("text", "")
    if text.startswith("/label"):
        parts = text.strip().split(" ")
        if len(parts) == 3:
            address = parts[1]
            name = parts[2]
            wallet_labels[address] = name
            save_labels(wallet_labels)
            send_telegram(f"✅ Label saved: `{address}` → *{name}*")
        else:
            send_telegram("❌ Usage: `/label <address> <name>`")

    elif text.strip() == "/labels":
        if wallet_labels:
            label_text = "\n".join([f"`{k}` → *{v}*" for k, v in wallet_labels.items()])
            send_telegram(f"📒 Wallet Labels:\n{label_text}")
        else:
            send_telegram("📭 No wallet labels set yet.")

    elif text.startswith("/clearlabel"):
        parts = text.strip().split(" ")
        if len(parts) == 2 and parts[1] in wallet_labels:
            removed = wallet_labels.pop(parts[1])
            save_labels(wallet_labels)
            send_telegram(f"🗑️ Removed label for `{parts[1]}` (*{removed}*)")
        else:
            send_telegram("❌ Usage: `/clearlabel <address>` or address not found.")

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🟢 HaloBot with Telegram wallet labels is live!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
