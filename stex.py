import logging
import requests
import asyncio
import sqlite3
import os
import platform
import warnings
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ওয়ার্নিং ফিল্টার
warnings.filterwarnings("ignore", category=UserWarning)

# --- 💠 CONFIGURATION 💠 ---
BOT_TOKEN = "8337640596:AAG1gfVqJPt-PqbpLLU7vLnGWfv1hmT3wk4"
USER_EMAIL = "mdrobiulshaek556@gmail.com"
USER_PASS = "Robiul@159358"
ADMINS = [6864515052]
OTP_GROUP_ID = -1003853823094 
OTP_GROUP_LINK = "https://t.me/stexsmsotp"

SET_RANGE = 1

def clear_console():
    if platform.system() == "Windows": os.system('cls')
    else: os.system('clear')
    print("💎 MRS ROBI PREMIUM | STATUS: ACTIVE 💎")
    print(f"⏰ LAST UPDATE: {datetime.now().strftime('%H:%M:%S')}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

logging.basicConfig(level=logging.ERROR)

# --- 📊 DATABASE ---
def setup_db():
    conn = sqlite3.connect('premium_v5.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, status TEXT DEFAULT 'active')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (date TEXT, type TEXT)''')
    conn.commit()
    conn.close()

def log_stat(stat_type):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('premium_v5.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stats (date, type) VALUES (?, ?)", (today, stat_type))
    conn.commit()
    conn.close()

# --- 🚀 StexSMS API ---
def get_session_and_token():
    session = requests.Session()
    headers = {'accept': 'application/json, text/plain, */*', 'user-agent': 'Mozilla/5.0', 'origin': 'https://stexsms.com'}
    try:
        resp = session.post("https://stexsms.com/mapi/v1/mauth/login", 
                            json={"email": USER_EMAIL, "password": USER_PASS}, headers=headers, timeout=15)
        if resp.status_code == 200:
            token = resp.json().get('data', {}).get('token')
            session.cookies.set('mauthtoken', token, domain='stexsms.com')
            return session, token, headers
    except: return None, None, None

# --- 📨 MONITORING LOOP ---
async def check_otp_loop(session, token, headers, number, context, chat_id, range_val):
    today = datetime.now().strftime('%Y-%m-%d')
    url = f'https://stexsms.com/mapi/v1/mdashboard/getnum/info?date={today}&page=1&search={number}&status='
    h = headers.copy()
    h.update({'mauthtoken': token})
    
    for _ in range(60): 
        try:
            resp = session.get(url, headers=h, timeout=10)
            if resp.status_code == 200:
                json_data = resp.json()
                numbers_list = json_data.get('data', {}).get('numbers', [])
                if numbers_list:
                    target = numbers_list[0]
                    otp_text = target.get('otp') or target.get('message')
                    service_name = target.get('app_name')
                    
                    if target.get('status') == "success" and otp_text:
                        log_stat('otp_success')
                        masked_num = f"{number[:5]}****{number[-4:]}"

                        await context.bot.send_message(
                            chat_id=chat_id, 
                            text=f"⚡️ **OTP RECEIVED!**\n━━━━━━━━━━━━━━\n\📱 Number: `{number}`\n\n🔑 Code: `{otp_text}`\n━━━━━━━━━━━━━━", 
                            parse_mode='Markdown'
                        )

                        group_msg = (
                            f"🔔 **PREMIUM SMS ALERT**\n━━━━━━━━━━━━━━\n"
                            f"📞 Phone: `{masked_num}`\n🌐 Range: `{range_val}`\n"
                            f"🛠 Service: `{service_name}`\n\n📩 OTP: `{otp_text}`\n━━━━━━━━━━━━━━"
                        )
                        try: await context.bot.send_message(chat_id=int(OTP_GROUP_ID), text=group_msg, parse_mode='Markdown')
                        except: pass
                        return
            await asyncio.sleep(5)
        except: await asyncio.sleep(5)

# --- 🛠 CORE ACTION: GET NUMBER (With Message Edit Logic) ---
async def get_number_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    range_val = context.user_data.get('service_range')
    if not range_val:
        return await context.bot.send_message(chat_id=chat_id, text="❌ Please set a Range first!")
    
    query = update.callback_query
    
    try:
        if query:
            # বাটন থেকে আসলে আগের মেসেজ এডিট হবে
            status_msg = await query.edit_message_text("🔄 Getting Number plz w8.........")
        else:
            # মেনু থেকে আসলে নতুন মেসেজ দিবে
            status_msg = await context.bot.send_message(chat_id=chat_id, text="🔄 Processing API Request...")

        session, token, headers = get_session_and_token()
        if not session: 
            return await status_msg.edit_text("❌ Connection Error (API).\nTry Again.....")

        h_api = headers.copy()
        h_api.update({'mauthtoken': token, 'content-type': 'application/json'})
        payload = {"range": range_val, "is_national": True, "remove_plus": False}
        
        nums = []
        for _ in range(2):
            try:
                r = requests.post('https://stexsms.com/mapi/v1/mdashboard/getnum/number', headers=h_api, json=payload, timeout=10)
                if r.status_code == 200:
                    num = r.json().get('data', {}).get('full_number')
                    if num: nums.append(num); log_stat('number_taken')
            except: pass

        if not nums: 
            return await status_msg.edit_text("🚫 **Out of Stock!** Try another range.")
        
        user_btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("♻️ Change Number", callback_data="req_new_num")],
            [InlineKeyboardButton("📢 OTP Group", url=OTP_GROUP_LINK)]
        ])

        res = f"✅ **Numbers Assigned**\n━━━━━━━━━━━━━━\n1️⃣ `{nums[0]}`\n"
        if len(nums)>1: res += f"2️⃣ `{nums[1]}`\n"
        res += f"\n⏳ *Monitoring for 5 minutes...*"
        
        await status_msg.edit_text(res, parse_mode='Markdown', reply_markup=user_btns)

        for num in nums:
            asyncio.create_task(check_otp_loop(session, token, headers, num, context, chat_id, range_val))
            
    except Exception as e:
        print(f"Error in get_number: {e}")

# --- 🛠 HANDLERS ---
async def start(update, context):
    clear_console()
    menu = [
        [KeyboardButton("📱 Get Number"), KeyboardButton("🚀 Console")],
        [KeyboardButton("⚙️ Range Input")]
    ]
    await update.message.reply_text(
        f"👑 MRS ROBI PREMIUM \n━━━━━━━━━━━━━━\n🎯 Active Range: `{context.user_data.get('service_range', 'None')}`\n🟢 Status: `Online`", 
        parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    if text == "📱 Get Number":
        await get_number_logic(update, context, chat_id)

    elif text == "🚀 Console":
        status_msg = await update.message.reply_text("⏳ Active Ranges Collecting.....W8")
        session, token, headers = get_session_and_token()
        if not session: return await status_msg.edit_text("❌ Server Timeout.\nTry Again...")
        
        h = headers.copy()
        h.update({'mauthtoken': token})
        try:
            resp = session.get('https://stexsms.com/mapi/v1/mdashboard/console/info', headers=h, timeout=10)
            if resp.status_code == 200:
                logs = resp.json().get('data', {}).get('logs', [])
                keyboard = []
                temp_row = []
                seen = set()
                for i in logs:
                    num = i.get('number')
                    app_name = i.get('app_name', 'Unknown')
                    # স্টার ওয়ালা বা আননোন অ্যাপ ফিল্টার
                    if not app_name or "*" in app_name or app_name == "Unknown": continue
                    if num and num not in seen:
                        btn_text = f"🔹 {app_name} | {num}XXX" # ৩টি X নিশ্চিত
                        temp_row.append(InlineKeyboardButton(btn_text, callback_data=f"set_r_{num}"))
                        seen.add(num)
                        if len(temp_row) == 2:
                            keyboard.append(temp_row)
                            temp_row = []
                        if len(seen) >= 16: break
                
                if temp_row: keyboard.append(temp_row)
                if keyboard:
                    await status_msg.edit_text("🛰 **Live Network Console:**", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await status_msg.edit_text("❌ No valid active ranges found.")
            else: await status_msg.edit_text("❌ No data in console.")
        except: await status_msg.edit_text("❌ Connection Error.")

    elif text == "⚙️ Range Input":
        await update.message.reply_text("✍️ **Enter Custom Range:**\n*(Example: 23762180)*")
        return SET_RANGE

async def save_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    # সব ধরণের X রিমুভ করে শুধু ৩টি X বসানো
    clean_val = val.upper().replace("X", "") 
    final_val = f"{clean_val}XXX"
    context.user_data['service_range'] = final_val
    await update.message.reply_text(f"✅ System Range Saved: `{final_val}`")
    return ConversationHandler.END

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    
    if query.data.startswith("set_r_"):
        val = query.data.replace("set_r_", "").upper().replace("X", "") + "XXX"
        context.user_data['service_range'] = val
        await query.edit_message_text(f"✅ System Range Set to: `{val}`")
        
    elif query.data == "req_new_num":
        await get_number_logic(update, context, chat_id)

# --- 🏁 RUN BOT ---
def main():
    setup_db()
    clear_console()
    
    # নেটওয়ার্ক স্ট্যাবিলিটির জন্য টাইমআউট বাড়ানো হয়েছে
    app = Application.builder().token(BOT_TOKEN).read_timeout(30).connect_timeout(30).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚙️ Range Input$'), handle_text)],
        states={SET_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_range)]},
        fallbacks=[CommandHandler("start", start)],
        per_message=False 
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(cb_handler))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()