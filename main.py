import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.transaction import Transaction
import requests
import time
import threading

# ========================= CONFIG =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")              # Set in Railway → Variables
WALLET_SECRET = os.getenv("WALLET_SECRET")      # Your 64-byte secret key as comma-separated string
TOKEN_MINT = os.getenv("TOKEN_MINT")            # Token you want to pump (e.g. Pump.fun token)
JUPITER_API = "https://quote-api.jup.ag/v6/swap"

# Solana RPC (use devnet for testing; switch to mainnet later)
client = Client("https://api.devnet.solana.com")  # Change to "https://api.mainnet-beta.solana.com" for live

# Load wallet
secret_key = [int(x) for x in WALLET_SECRET.split(",")]
keypair = Keypair.from_bytes(bytes(secret_key))

bot = telebot.TeleBot(BOT_TOKEN)

# ========================= HELPERS =========================
def get_swap_transaction(input_mint="So11111111111111111111111111111111111111112", 
                         output_mint=TOKEN_MINT, 
                         amount=0.001 * 1e9,      # amount in lamports (0.001 SOL per trade)
                         slippage=200):           # 2% slippage
    # Get quote
    quote_url = "https://quote-api.jup.ag/v6/quote"
    quote_params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": int(amount),
        "slippageBps": slippage
    }
    quote = requests.get(quote_url, params=quote_params).json()

    # Get swap tx
    swap_payload = {
        "quoteResponse": quote,
        "userPublicKey": str(keypair.public_key),
        "wrapAndUnwrapSol": True
    }
    swap_resp = requests.post(JUPITER_API, json=swap_payload).json()

    return swap_resp['swapTransaction']

# ========================= COMMANDS =========================
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Boost Volume 10x", callback_data="boost_10"))
    markup.add(InlineKeyboardButton("Boost Volume 50x", callback_data="boost_50"))
    bot.send_message(
        message.chat.id,
        "Volume Bot Ready 🚀\n"
        f"Wallet: `{keypair.public_key}`\n"
        f"Token: `{TOKEN_MINT}`\n\n"
        "Choose how hard to pump:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data.startswith("boost_"):
        times = int(call.data.split("_")[1])
        bot.answer_callback_query(call.id, f"Boosting {times}x ...")
        threading.Thread(target=do_volume, args=(call.message.chat.id, times)).start()

def do_volume(chat_id, times):
    bot.send_message(chat_id, f"Starting {times} fake volume trades... 🔥")
    success = 0
    for i in range(times):
        try:
            raw_tx = get_swap_transaction(amount=int(0.0005 * 1e9))  # Tiny 0.0005 SOL per tx to avoid fees killing you
            tx = Transaction.deserialize(bytes.fromhex(raw_tx))
            tx.sign(keypair)
            txid = client.send_raw_transaction(tx.serialize())['result']
            success += 1
            bot.send_message(chat_id, f"{i+1}/{times} ✅ https://solscan.io/tx/{txid}?cluster=devnet")  # Add ?cluster=mainnet for live
            time.sleep(3 + i % 2)  # Random-ish delay to look natural, avoid bans
        except Exception as e:
            bot.send_message(chat_id, f"Failed {i+1}: {str(e)[:100]}")
            time.sleep(5)

    bot.send_message(chat_id, f"Volume boost finished! {success}/{times} trades sent 💧")

# ========================= RUN =========================
if __name__ == "__main__":
    print("Volume bot started...")
    bot.infinity_polling()