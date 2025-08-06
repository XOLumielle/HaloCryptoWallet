from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HELIUS_API_KEY = "c8903a79-6e7a-458a-ad88-0a821d92d16d"
HELIUS_WEBHOOK_URL = "https://halocryptowallet-production.up.railway.app/webhook"

MIN_SOL_THRESHOLD = 0.01
LABELS_FILE = "wallet_labels.json"
WALLETS_FILE = "tracked_wallets.json"
seen_signatures = set()

# ---------------------------
# Load/save JSON files
# ---------------------------
def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

wallet_labels = load_json(LABELS_FILE)
tracked_wallets = load_json(WALLETS_FILE)

def label_wallet(addr):
    return wallet_labels.get(addr, addr)

# ---------------------------
# Dexscreener Utilities
# ---------------------------
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

# ---------------------------
# Helius Sync
# ---------------------------
def update_helius_webhook():
    try:
        webhook_id_url = f"https://api.helius.xyz/v0/webhooks?api-key={HELIUS_API_KEY}"
        res = requests.get(webhook_id_url)
        webhooks = res.json()
        my_webhook = next((w for w in webhooks if w["webhookURL"] == HELIUS_WEBHOOK_URL), None)

        if not my_webhook:
            print("❌ Could not find Helius webhook ID.")
            return

        webhook_id = my_webhook["webhookID"]
        update_url = f"https://api.helius.xyz/v0/webhooks/{webhook_id}?api-key={HELIUS_API_KEY}"
        payload = {
            "webhookURL": HELIUS_WEBHOOK_URL,
            "transactionTypes": ["ALL"],
            "accountAddresses": list(tracked_wallets.keys())
        }
        res = requests.put(update_url, json=payload)
        print(f"🔄 Synced webhook with Helius: {res.status_code}")
    except Exception as e:
        print(f"❌ Error updating Helius: {e}")

# ---------------------------
# TELEGRAM ROUTE
# ---------------------------
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_commands():
    data = request.json
    if "message" not in data:
        return "OK", 200

    text = data["message"].get("text", "").strip()
    if not text:
        return "OK", 200

    if text.startswith("/label "):
        parts = text.split(" ", 2)
        if len(parts) == 3:
            addr, name = parts[1], parts[2]
            wallet_labels[addr] = name
            save_json(LABELS_FILE, wallet_labels)
            send_telegram(f"✅ Label saved: `{addr}` → *{name}*")
        else:
            send_telegram("❌ Usage: `/label <address> <name>`")

    elif text == "/labels":
        if wallet_labels:
            msg = "\n".join([f"`{k}` → *{v}*" for k, v in wallet_labels.items()])
            send_telegram(f"📒 Wallet Labels:\n{msg}")
        else:
            send_telegram("📭 No wallet labels yet.")

    elif text.startswith("/clearlabel "):
        parts = text.split(" ", 1)
        addr = parts[1]
        if addr in wallet_labels:
            name = wallet_labels.pop(addr)
            save_json(LABELS_FILE, wallet_labels)
            send_telegram(f"🗑️ Removed label: `{addr}` (*{name}*)")
        else:
            send_telegram("❌ Label not found.")

    elif text.startswith("/track "):
        addr = text.split(" ")[1]
        if addr in tracked_wallets:
            send_telegram("⚠️ Already tracking that address.")
        else:
            tracked_wallets[addr] = True
            save_json(WALLETS_FILE, tracked_wallets)
            update_helius_webhook()
            send_telegram(f"✅ Now tracking wallet:\n`{addr}`")

    elif text.startswith("/untrack "):
        addr = text.split(" ")[1]
        if addr in tracked_wallets:
            tracked_wallets.pop(addr)
            save_json(WALLETS_FILE, tracked_wallets)
            update_helius_webhook()
            send_telegram(f"🗑️ No longer tracking:\n`{addr}`")
        else:
            send_telegram("❌ That wallet wasn't being tracked.")

    elif text == "/tracking":
        if tracked_wallets:
            msg = "\n".join([f"- `{k}`" for k in tracked_wallets])
            send_telegram(f"📍 Currently tracking:\n{msg}")
        else:
            send_telegram("📭 No wallets being tracked yet.")

    return "OK", 200

# ---------------------------
# WEBHOOK ENDPOINT
# ---------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    txs = request.json
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

        from_raw = native[0].get("fromUserAccount", "Unknown")
        to_raw = native[0].get("toUserAccount", "Unknown")
        from_addr = label_wallet(from_raw)
        to_addr = label_wallet(to_raw)
        usd = f"${amount * sol_price:,.2f}" if sol_price else "?"

        token_transfers = tx.get("tokenTransfers", [])
        token_address = token_transfers[0].get("tokenAddress") if token_transfers else None
        token_name = symbol = token_price = liquidity = None
        if token_address:
            token_name, symbol, token_price, liquidity = get_token_info(token_address)

        if symbol and token_price:
            msg = (
                "*Smart Wallet Alert!*\n"
                f"*From:* `{from_addr}`\n"
                f"*To:* `{to_addr}`\n"
                f"*Sent:* {amount:.4f} SOL ({usd})\n"
                f"*Token:* ${symbol} ({token_name})\n"
                f"*Token Address:* `{token_address}`\n"
                f"*Price:* ${token_price:,.4f} | Liquidity: ${liquidity:,.0f}\n"
                f"[View Tx](https://solscan.io/tx/{signature})"
            )
        else:
            msg = (
                "*Transfer Detected!*\n"
                f"*From:* `{from_addr}`\n"
                f"*To:* `{to_addr}`\n"
                f"*Amount:* {amount:.4f} SOL ({usd})\n"
                f"[View on Solscan](https://solscan.io/tx/{signature})"
            )

        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🟢 HaloBot with Helius syncing + Telegram wallet tracking is live!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
