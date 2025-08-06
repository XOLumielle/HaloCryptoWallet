from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Known wallet labels
known_wallets = {
    "4EtAJ1p8RjqccEVhEhaYnEgQ6kA4JHR8oYqyLFwARUj6": "TRUMP Whale #1",
    "HWdeCUjBvPP1HJ5oCJt7aNsvMWpWoDgiejUWvfFX6T7R": "Gaming Giant",
    "fwHknyxZTgFGytVz9VPrvWqipW2V4L4D99gEb831t81": "AI Memecoin Sniper",
    "9HCTuTPEiQvkUtLmTZvK6uch4E3pDynwJTbNw6jLhp9z": "TRUMP Mega Whale",
    "6kbwsSY4hL6WVadLRLnWV2irkMN2AvFZVAS8McKJmAtJ": "RIF Winner",
    "5fWkLJfoDsRAaXhPJcJY19qNtDDQ5h6q1SPzsAPRrUNG": "Multi-Win Whale"
}

def get_token_info(token_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{token_address}"
        res = requests.get(url)
        data = res.json()
        if data["pairs"]:
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
    return get_token_info("So11111111111111111111111111111111111111112")[2]

def get_wallet_balance(address):
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        res = requests.post("https://api.mainnet-beta.solana.com", json=payload)
        lamports = res.json()["result"]["value"]
        return lamports / 1_000_000_000
    except:
        return None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=data)
    print("Telegram response:", response.status_code, response.text)

@app.route("/webhook", methods=["POST"])
def webhook():
    txs = request.json
    print("Webhook HIT")
    print(json.dumps(txs, indent=2))

    if not txs or not isinstance(txs, list):
        return "Invalid data", 400

    sol_price = get_sol_price()

    for tx in txs:
        wallet = tx.get("source", "Unknown")
        label = known_wallets.get(wallet, wallet[:6] + "..." + wallet[-4:])
        signature = tx.get("signature", "")
        sol_spent = float(tx.get("fee", 0)) / 1_000_000_000

        token_transfers = tx.get("tokenTransfers", [])
        token_address = token_transfers[0].get("mint", "Unknown") if token_transfers else "Unknown"
        tx_type = tx.get("type", "Transfer")

        # Wallet balance
        balance_sol = get_wallet_balance(wallet)
        balance_usd = f"${balance_sol * sol_price:,.2f}" if balance_sol and sol_price else "N/A"
        spent_usd = f"${sol_spent * sol_price:,.2f}" if sol_price else "?"

        # Token info via Dexscreener
        token_name, symbol, token_price, liquidity = get_token_info(token_address)
        price_info = f"${token_price:,.4f}" if token_price else "?"
        liquidity_info = f"${liquidity:,.0f}" if liquidity else "?"

        msg = (
            "*Smart Whale Alert!*\n"
            f"*Wallet:* {label}\n"
            f"*Tx Type:* {tx_type}\n"
            f"*Spent:* {sol_spent:.4f} SOL ({spent_usd})\n"
            f"*Wallet Balance:* {balance_sol:.2f} SOL ({balance_usd})\n"
            f"*Token:* ${symbol or '?'} ({token_name or 'Unknown'})\n"
            f"*Token Address:* `{token_address}`\n"
            f"*Price:* {price_info} | Liquidity: {liquidity_info}\n"
            f"[View Tx](https://solscan.io/tx/{signature})"
        )

        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "HaloWebhook powered fully by Dexscreener is live!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
