from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
    _, _, sol_price, _ = get_token_info("So11111111111111111111111111111111111111112")
    return sol_price

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
    requests.post(url, json=data)

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
        signature = tx.get("signature", "")
        tx_type = tx.get("type", "Transfer")
        sol_spent = float(tx.get("fee", 0)) / 1_000_000_000

        # Get token address if exists
        token_transfers = tx.get("tokenTransfers", [])
        token_address = token_transfers[0].get("mint", None) if token_transfers else None

        # Token info
        if token_address:
            token_name, token_symbol, token_price, liquidity = get_token_info(token_address)
        else:
            token_name = token_symbol = token_price = liquidity = None

        # Wallet balance
        balance_sol = get_wallet_balance(wallet)

        # Format fields
        spent_usd = f"${sol_spent * sol_price:,.2f}" if sol_price else "USD unknown"
        balance_fmt = f"{balance_sol:.2f}" if balance_sol is not None else "Unknown"
        balance_usd = f"${balance_sol * sol_price:,.2f}" if sol_price and balance_sol is not None else "?"

        token_display = f"${token_symbol} ({token_name})" if token_symbol and token_name else "Unlisted or Unknown"
        token_addr_display = f"`{token_address}`" if token_address else "None"
        price_display = f"${token_price:,.4f}" if token_price else "N/A"
        liquidity_display = f"${liquidity:,.0f}" if liquidity else "N/A"

        msg = (
            "*Smart Whale Alert!*\n"
            f"*Wallet:* `{wallet}`\n"
            f"*Tx Type:* {tx_type}\n"
            f"*Spent:* {sol_spent:.4f} SOL ({spent_usd})\n"
            f"*Wallet Balance:* {balance_fmt} SOL ({balance_usd})\n"
            f"*Token:* {token_display}\n"
            f"*Token Address:* {token_addr_display}\n"
            f"*Price:* {price_display} | Liquidity: {liquidity_display}\n"
            f"[View Tx](https://solscan.io/tx/{signature})"
        )

        send_telegram(msg)

    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "HaloWebhook cleaned and active 🌙", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
