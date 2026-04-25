import logging
import requests
import asyncio
import sqlite3
import os
import html
import re
import platform
import warnings
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ওয়ার্নিং ফিল্টার
warnings.filterwarnings("ignore", category=UserWarning)

# --- 💠 CONFIGURATION 💠 ---
BOT_TOKEN = "8337640596:AAG1gfVqJPt-PqbpLLU7vLnGWfv1hmT3wk4"
USER_EMAIL = "mdrobiulshaek556@gmail.com"
USER_PASS = "Robiul@159358"
OTP_GROUP_ID = -1003853823094 
OTP_GROUP_LINK = "https://t.me/stexsmsotp"

# Conversation States
SET_RANGE, SEARCH_SERVICE = range(2)

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

# --- 🚀 StexSMS API SESSION ---
def get_session_and_token():
    session = requests.Session()
    headers = {
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'origin': 'https://stexsms.com'
    }
    try:
        resp = session.post("https://stexsms.com/mapi/v1/mauth/login", 
                            json={"email": USER_EMAIL, "password": USER_PASS}, headers=headers, timeout=15)
        if resp.status_code == 200:
            token = resp.json().get('data', {}).get('token')
            session.cookies.set('mauthtoken', token, domain='stexsms.com')
            return session, token, headers
    except: return None, None, None

# --- 🛰 LIVE CONSOLE VIEW (Updated with HTML Parse Mode) ---
async def get_console_view(update, context, search_query=None, loading_message=None):
    session, token, headers = get_session_and_token()
    
    if not session:
        msg = "❌ Session Error. Login failed!"
        if loading_message: await loading_message.edit_text(msg)
        elif update.callback_query: await update.callback_query.edit_message_text(msg)
        return

    h = headers.copy()
    h.update({'mauthtoken': token})
    
    try:
        resp = session.get('https://stexsms.com/mapi/v1/mdashboard/console/info', headers=h, timeout=12)
        
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            logs = data.get('logs', [])
            
            status_title = f" ({search_query})" if search_query else ""
            console_text = f"🛰 <b>LIVE NETWORK CONSOLE</b>{status_title}\n━━━━━━━━━━━━━━━━━━\n"
            
            count = 0
            for i in logs:
                app_name = html.escape(i.get('app_name') or "Unknown")
                sms_body = i.get('sms') or i.get('otp') or i.get('message') or "Waiting for SMS..."
                
                if search_query:
                    if (search_query.lower() not in app_name.lower()) and (search_query.lower() not in sms_body.lower()):
                        continue

                time_val = i.get('time') or datetime.now().strftime('%H:%M:%S')
                number = i.get('number') or "Unknown"
                srv_range = i.get('range') or "N/A"
                
                # HTML Escape for sms_body to prevent parsing errors
                safe_sms = html.escape(sms_body)

                console_text += (
                    f"🌐 App: <b>{app_name}</b>\n"
                    f"🕒 Time: {time_val}\n"
                    f"📱 Num: <code>{number}</code>\n"
                    f"🎯 Range: <code>{srv_range}</code>\n"
                    f"➜ SMS: <code>{safe_sms}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
                count += 1
                if count >= 10: break 

            if count == 0:
                console_text += "📭 No recent logs found matching your request."

            nav_btns = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Search", callback_data="open_search"),
                 InlineKeyboardButton("🔄 Refresh", callback_data="refresh_console")]
            ])

            try:
                if loading_message:
                    await loading_message.edit_text(console_text, reply_markup=nav_btns, parse_mode='HTML')
                elif update.callback_query:
                    await update.callback_query.edit_message_text(console_text, reply_markup=nav_btns, parse_mode='HTML')
                else:
                    await update.message.reply_text(console_text, reply_markup=nav_btns, parse_mode='HTML')
            except Exception as e:
                if "Message is not modified" not in str(e):
                    error_log = f"⚠️ <b>Edit Error:</b> <code>{html.escape(str(e))}</code>"
                    if update.callback_query: await update.callback_query.message.reply_text(error_log, parse_mode='HTML')
                    else: await update.message.reply_text(error_log, parse_mode='HTML')

        else:
            await update.effective_chat.send_message(f"❌ API Error: {resp.status_code}")
            
    except Exception as e:
        err_msg = f"⚠️ <b>System Error:</b> <code>{html.escape(str(e))}</code>"
        if loading_message: await loading_message.edit_text(err_msg, parse_mode='HTML')
        else: await update.effective_chat.send_message(err_msg, parse_mode='HTML')


# --- 📨 MONITORING LOOP (Full SMS Included) ---
async def check_otp_loop(session, token, headers, number, context, chat_id, range_val):
    today = datetime.now().strftime('%Y-%m-%d')
    search_num = number.replace("+", "").replace(" ", "")
    url = f'https://stexsms.com/mapi/v1/mdashboard/getnum/info?date={today}&page=1&search={search_num}&status='
    
    h = headers.copy()
    h.update({'mauthtoken': token})
    
    for _ in range(60): 
        try:
            resp = session.get(url, headers=h, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('numbers', [])
                if data:
                    target = data[0]
                    otp_text = target.get('otp') or target.get('message') or target.get('sms')
                    
                    if target.get('status') == "success" and otp_text:
                        # ১. ওটিপি এক্সট্রাকশন (৩ থেকে ১০ ডিজিট)
                        extracted_otp = "Not Found"
                        match_space = re.search(r'\d{1,8}\s\d{1,8}', otp_text)
                        match_solid = re.search(r'\d{3,10}', otp_text)
                        
                        if match_space: 
                            extracted_otp = match_space.group().replace(" ", "")
                        elif match_solid: 
                            extracted_otp = match_solid.group()

                        # ২. ডাটা ম্যাপিং
                        app_name = target.get('full_number') or "Unknown Service"
                        country = target.get('country') or "Global"
                        safe_sms = html.escape(otp_text) # ফুল এসএমএস ক্লিন করা

                        # ৩. ইউজারকে পার্সোনাল মেসেজ
                        user_text = (
                            f"⚡️ <b>OTP RECEIVED!</b>\n"
                            f"━━━━━━━━━━━━━━\n"
                            f"📱 Number: <code>{number}</code>\n"
                            f"🛠 Service: <code>{app_name}</code>\n"
                            f"🟢 OTP: <code>{extracted_otp}</code>\n"
                            f"━━━━━━━━━━━━━━"
                        )
                        await context.bot.send_message(chat_id=chat_id, text=user_text, parse_mode='HTML')

                        # ৪. ওটিপি গ্রুপে মেসেজ পাঠানো (ফুল এসএমএস সহ)
                        masked_num = f"{number[:6]}****{number[-3:]}"
                        group_msg = (
                            f"🔔 <b>PREMIUM ALERT</b>\n"
                            f"━━━━━━━━━━━━━━\n"
                            f"📞 Phone: <code>{masked_num}</code>\n"
                            f"🌐 Range: <code>{range_val}</code>\n"
                            f"🌍 Country: <code>{country}</code>\n"
                            f"🛠 Service: <code>{app_name}</code>\n\n"
                            f"📩 OTP: <code>{extracted_otp}</code>\n\n"
                            f"💬 <code>{safe_sms}</code>\n"
                            f"━━━━━━━━━━━━━━"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=int(OTP_GROUP_ID), 
                                text=group_msg, 
                                parse_mode='HTML'
                            )
                        except:
                            pass
                            
                        log_stat('otp_success')
                        return 
            
            await asyncio.sleep(5)
        except Exception as e: 
            print(f"OTP Loop Error: {e}")
            await asyncio.sleep(5)


# --- 🛠 CORE ACTION: GET NUMBER ---
async def get_number_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    range_val = context.user_data.get('service_range')
    if not range_val:
        return await context.bot.send_message(chat_id=chat_id, text="❌ Please set a Range first!")
    
    query = update.callback_query
    
    try:
        if query:
            status_msg = await query.edit_message_text("🔄 Getting Number plz w8.........")
        else:
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
            return await status_msg.edit_text("🚫 <b>Out of Stock!</b> Try another range.", parse_mode='HTML')
        
        user_btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("♻️ Change Number", callback_data="req_new_num")],
            [InlineKeyboardButton("📢 OTP Group", url=OTP_GROUP_LINK)]
        ])

        res = f"✅ <b>Numbers Assigned</b>\n━━━━━━━━━━━━━━\n1️⃣ <code>{nums[0]}</code>\n"
        if len(nums)>1: res += f"2️⃣ <code>{nums[1]}</code>\n"
        res += f"\n⏳ <i>Monitoring for 5 minutes...</i>"
        
        await status_msg.edit_text(res, parse_mode='HTML', reply_markup=user_btns)

        for num in nums:
            asyncio.create_task(check_otp_loop(session, token, headers, num, context, chat_id, range_val))
            
    except Exception as e:
        print(f"Error in get_number: {e}")

# --- 🕹 HANDLERS ---
async def start(update, context):
    clear_console()
    menu = [[KeyboardButton("📱 Get Number"), KeyboardButton("🚀 Console")], [KeyboardButton("⚙️ Range Input")]]
    current_range = context.user_data.get('service_range', 'Not Set')
    await update.message.reply_text(
        f"👑 <b>MRS ROBI PREMIUM</b>\n━━━━━━━━━━━━━━\n🎯 Active Range: <code>{current_range}</code>", 
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True), parse_mode='HTML'
    )

async def handle_text(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    if text == "📱 Get Number": 
        await get_number_logic(update, context, chat_id)
    elif text == "🚀 Console":
        loading_msg = await update.message.reply_text("⏳ <b>Connecting to Network Console...</b>", parse_mode='HTML')
        await get_console_view(update, context, loading_message=loading_msg)
    elif text == "⚙️ Range Input":
        await update.message.reply_text("✍️ Enter Custom Range (e.g. 99206):")
        return SET_RANGE

async def save_range(update, context):
    val = update.message.text.strip().upper().replace("X", "") + "XXX"
    context.user_data['service_range'] = val
    await update.message.reply_text(f"🎯 Range Updated: <code>{val}</code>", parse_mode='HTML')
    return ConversationHandler.END

async def search_handler(update, context):
    query = update.message.text.strip()
    await get_console_view(update, context, search_query=query)
    return ConversationHandler.END

async def cb_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "req_new_num":
        await get_number_logic(update, context, update.effective_chat.id)
    elif query.data == "refresh_console":
        await query.edit_message_text("🔄 <b>Refreshing Console... Please wait.</b>", parse_mode='HTML')
        await get_console_view(update, context)
    elif query.data == "open_search":
        search_menu = [
            [InlineKeyboardButton("📘 Facebook", callback_data="fast:facebook"),
             InlineKeyboardButton("🟢 WhatsApp", callback_data="fast:whatsapp")],
            [InlineKeyboardButton("✍️ Custom Input", callback_data="custom_input")]
        ]
        await query.message.reply_text("🔍 <b>Select Service or Search:</b>", reply_markup=InlineKeyboardMarkup(search_menu), parse_mode='HTML')
    elif query.data.startswith("fast:"):
        q = query.data.split(":")[1]
        await query.edit_message_text(f"🔍 <b>Searching for: {q}...</b>", parse_mode='HTML')
        await get_console_view(update, context, search_query=q)
    elif query.data == "custom_input":
        await query.message.reply_text("🔎 টাইপ করুন আপনি কী সার্চ করতে চান (যেমন: imo, google):")
        return SEARCH_SERVICE

def main():
    setup_db()
    clear_console()
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^⚙️ Range Input$'), handle_text),
            CallbackQueryHandler(cb_handler, pattern="^custom_input$")
        ],
        states={
            SET_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_range)],
            SEARCH_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler)]
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False 
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(cb_handler))
    
    print("🚀 Bot is Running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
