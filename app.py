from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MIN_SOL_THRESHOLD = 0.01  # skip txs under this value
seen_signatures = set()   # to avoid duplicates

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
            print(f"⚠️ Skipped: No Solscan data for {signature}")
            continue

        seen_signatures.add(signature)

        # Fee (amount spent in lamports)
        fee = solscan_data.get("fee", 0) / 1_000_000_000
        if fee < MIN_SOL_THRESHOLD:
            print(f"⏩ Skipped low-value tx {signature} ({fee:.6f} SOL)")
            continue

        # From/To
        try:
            instr = solscan_data["parsedInstruction"][0]
            from_addr = instr.get("params", {}).get("source", "Unknown")
            to_addr = instr.get("params", {}).get("destination", "Unknown")
        except:
            from_addr = tx.get("source", "Unknown")
            to_addr = "Unknown"

        usd_value = f"${fee * sol_price:,.2f}" if sol_price else "?"

        # Token info if any
        token_transfers = solscan_data.get("tokenTransfers", [])
        token_address = token_transfers[0].get("tokenAddress") if token_transfers else None
        if token_address:
            token_name, symbol, token_price, liquidity = get_token_info(token_address)
        else:
            token_name = symbol = token_price = liquidity = None

        # ✅ Decide if we have enough to send full alert
        if symbol and token_name and token_price:
            token_display = f"${symbol} ({token_name})"
            token_address_display = f"`{token_address}`"
            price_display = f"${token_price:,.4f}"
            liquidity_display = f"${liquidity:,.0f}" if liquidity else "N/A"

            msg = (
                "*Smart Wallet Alert!*\n"
                f"*From:* `{from_addr}`\n"
                f"*To:* `{to_addr}`\n"
                f"*Spent:* {fee:.4f} SOL ({usd_value})\n"
                f"*Token:* {token_display}\n"
                f"*Token Address:* {token_address_display}\n"
                f"*Price:* {price_display} | Liquidity: {liquidity_display}\n"
                f"[View Tx](https://solscan.io/tx/{signature})"
            )
        else:
            # 🪙 Fallback alert — minimal transfer
            msg = (
                "*Transfer Detected!*\n"
                f"*From:* `{from_addr}`\n"
                f"*To:* `{to_addr}`\n"
                f"*Amount:* {fee:.4f} SOL ({usd_value})\n"
                f"[View on Solscan](https://solscan.io/tx/{signature})"
            )

        print(f"📤 Sending Telegram alert for tx {signature}")
        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🟢 HaloBot Hybrid (Solscan + Dexscreener) active!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
