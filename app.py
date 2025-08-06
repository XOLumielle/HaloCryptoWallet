from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_SOL_THRESHOLD = 0.01
seen_signatures = set()

def get_solscan_tx(signature):
    try:
        url = f"https://public-api.solscan.io/transaction/{signature}"
        headers = {"accept": "application/json"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def get_token_info(token_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{token_address}"
        res = requests.get(url)
        data = res.json()
        if data.get("pairs"):
            pair = data["pairs"][0]
            name = pair["baseToken"]["name"]
            symbol = pair["baseToken"]["symbol"]
            price = float(pair["priceUsd"])
            liquidity = float(pair["liquidity"]["usd"])
            return name, symbol, price, liquidity
    except:
        pass
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
    if not txs or not isinstance(txs, list):
        return "Invalid data", 400

    sol_price = get_sol_price()

    for tx in txs:
        signature = tx.get("signature")
        if not signature or signature in seen_signatures:
            continue

        solscan_data = get_solscan_tx(signature)
        if not solscan_data:
            continue

        seen_signatures.add(signature)

        # Native SOL amount transferred
        native_transfer = solscan_data.get("nativeTransfers", [])
        if not native_transfer:
            continue

        amount = native_transfer[0].get("amount", 0) / 1_000_000_000
        if amount < MIN_SOL_THRESHOLD:
            continue

        from_addr = native_transfer[0].get("fromUserAccount", "Unknown")
        to_addr = native_transfer[0].get("toUserAccount", "Unknown")
        usd_value = f"${amount * sol_price:,.2f}" if sol_price else "?"

        # Token info
        token_transfers = solscan_data.get("tokenTransfers", [])
        token_address = token_transfers[0].get("tokenAddress") if token_transfers else None
        if token_address:
            token_name, symbol, token_price, liquidity = get_token_info(token_address)
        else:
            token_name = symbol = token_price = liquidity = None

        # Build message
        if symbol and token_name and token_price:
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

        print(f"📤 Telegram ping for {signature} | Amount: {amount:.4f} SOL")
        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🟢 HaloBot v2 — based on SOL transferred, live and glowing!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
