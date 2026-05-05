import logging
import requests
import asyncio
import warnings
import html
import re
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler


# DeprecationWarning বা পাইথনের ইন্টারনাল এররগুলো সিএমডিতে আসা বন্ধ করবে
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- 💠 ১. কনফিগারেশন 💠 ---
BOT_TOKEN = "7871155522:AAFT3Szh7w5pn9MG3-8L5d_P4LbHyDdWP4Q"
BASE_URL = "https://x.mnitnetwork.com/mapi/v1"
USER_EMAIL = "mdrobiulshaek556@gmail.com"
USER_PASS = "Robiul@159358"
OTP_GROUP_ID = -1003853823094  # সংশোধিত আইডি
OTP_GROUP_LINK = "https://t.me/stexsmsotp"

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR)

# --- 🔐 ২. সেশন ও লগইন লজিক ---
session = requests.Session()
auth_token = None

def perform_login():
    global auth_token
    url = f"{BASE_URL}/mauth/login"
    payload = {"email": USER_EMAIL, "password": USER_PASS}
    try:
        response = session.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            auth_token = response.json().get('data', {}).get('token')
            session.headers.update({
                'Authorization': f'Bearer {auth_token}',
                'mauthtoken': auth_token,
                'user-agent': 'Mozilla/5.0'
            })
            return True
    except: pass
    return False

# --- 🗄 ডাটাবেস লজিক ---
def init_db():
    conn = sqlite3.connect('otp_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_numbers 
                      (number TEXT PRIMARY KEY, chat_id INTEGER, expiry_time DATETIME)''')
    conn.commit()
    conn.close()

def save_number_owner(number, chat_id):
    expiry = datetime.now() + timedelta(minutes=10)
    conn = sqlite3.connect('otp_bot.db')
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO active_numbers (number, chat_id, expiry_time) VALUES (?, ?, ?)", 
                   (number, chat_id, expiry))
    conn.commit()
    conn.close()

def get_owner_and_clean(number):
    conn = sqlite3.connect('otp_bot.db')
    cursor = conn.cursor()
    # ১০ মিনিট পার হওয়া ডাটা ডিলিট
    cursor.execute("DELETE FROM active_numbers WHERE expiry_time < ?", (datetime.now(),))
    conn.commit()
    # মালিক খোঁজা
    cursor.execute("SELECT chat_id FROM active_numbers WHERE number = ?", (number,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# --- 🛠 ৩. ইউটিলিটি ফাংশন ---
def extract_otp(text):
    if not text: return "N/A"
    clean_text = text.replace("<#>", "").strip()
    match = re.search(r'(\d[\s-]?){3,8}\d', clean_text)
    if match:
        otp = match.group(0).replace(" ", "").replace("-", "")
        return otp
    return "N/A"

# --- ⌨️ ৪. কিবোর্ড ও মেনু সেটআপ ---
def get_main_menu():
    keyboard = [[KeyboardButton("📱 Get Number"), KeyboardButton("🚀 Live Console")], 
                [KeyboardButton("⚙️ Set Range")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_console_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search App", callback_data="btn_search_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="console_refresh")]
    ])

def get_search_shortcuts():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 Facebook", callback_data="srch_FACEBOOK"),
         InlineKeyboardButton("🟢 WhatsApp", callback_data="srch_WHATSAPP")],
        [InlineKeyboardButton("📸 Instagram", callback_data="srch_INSTAGRAM"),
         InlineKeyboardButton("⌨️ Custom Input", callback_data="srch_CUSTOM")],
        [InlineKeyboardButton("🔙 Back to Console", callback_data="console_refresh")]
    ])

# --- 🖥 ৫. কনসোল ডাটা লজিক ---
async def get_console_data(search_query=None):
    if not auth_token: perform_login()
    url = f"{BASE_URL}/mdashboard/console/info"
    try:
        resp = session.get(url, timeout=12)
        if resp.status_code == 200:
            logs = resp.json().get('data', {}).get('logs', [])
            if not logs: return "📭 Console empty 🚫"

            filtered_logs = []
            if search_query:
                query = search_query.lower()
                for i in logs:
                    app_name = str(i.get('app_name', '')).lower()
                    sms_body = str(i.get('sms', '') or i.get('otp', '') or '').lower()
                    if query in app_name or query in sms_body:
                        filtered_logs.append(i)
            else:
                filtered_logs = logs

            if not filtered_logs:
                return f"📭 '{html.escape(search_query)}' Not Maching Result 🤷‍♂️"

            title = f"🔍 <b>SEARCH RESULT: {html.escape(search_query.upper())}</b>" if search_query else "🚀 <b>LIVE CONSOLE</b>"
            console_text = f"{title}\n━━━━━━━━━━━━━━━━━━\n"
            
            for i in filtered_logs[:15]:
                app_name = html.escape(str(i.get('app_name', 'N/A')))
                time_val = html.escape(str(i.get('time', 'N/A')))
                number = html.escape(str(i.get('number', 'N/A')))
                srv_range = html.escape(str(i.get('range', 'N/A')))
                safe_sms = html.escape(str(i.get('sms') or i.get('otp') or 'Waiting...'))

                console_text += (
                    f"🌐 App: <b>{app_name}</b>\n"
                    f"🕒 Time: {time_val}\n"
                    f"📱 Num: <code>{number}</code>\n"
                    f"🎯 Range: <code>{srv_range}</code>\n"
                    f"➜ SMS: <code>{safe_sms}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
            return console_text
        return "❌ API Response Error"
    except Exception as e: 
        return f"⚠️ Error: {str(e)}"

# --- 🛰 ৬. ওটিপি মনিটরিং লজিক (Updated with Buttons & Better Scanning) ---
async def monitor_otp_task(chat_id, number, context, reply_to_id, user_range):
    today = datetime.now().strftime('%Y-%m-%d')
    check_url = f"{BASE_URL}/mdashboard/getnum/info"
    params = {'date': today, 'page': 1, 'search': number, 'status': ''}

    for _ in range(120): # ৫ সেকেন্ড অন্তর চেক করলে ১০ মিনিট পর্যন্ত চলবে
        try:
            resp = session.get(check_url, params=params, timeout=10)
            if resp.status_code == 200:
                data_list = resp.json().get('data', {}).get('numbers', [])
                if data_list:
                    target = data_list[0]
                    # ওটিপি বা মেসেজ বডি সংগ্রহ
                    full_sms = target.get('otp') or target.get('sms') or target.get('message')
                    
                    if full_sms and full_sms.strip():
                        # ওটিপি এক্সট্রাকশন (Regex ব্যবহার করে)
                        extracted_otp = extract_otp(full_sms)
                        app_name = html.escape(str(target.get('app_name', 'Service')))
                        country = html.escape(str(target.get('country', 'N/A')))
                        safe_sms = html.escape(full_sms)

                        # ১. ইউজারকে পার্সোনাল মেসেজ পাঠানো
                        user_text = (
                            f"✅ <b>OTP RECEIVED!</b>\n━━━━━━━━━━━━━━\n"
                            f"📱 <b>Number:</b> <code>{number}</code>\n"
                            f"🛠 <b>Service:</b> <code>{app_name}</code>\n"
                            f"📩 <b>OTP:</b> <code>{extracted_otp}</code>\n━━━━━━━━━━━━━━"
                        )
                        await context.bot.send_message(chat_id=chat_id, text=user_text, parse_mode='HTML', reply_to_message_id=reply_to_id)

                        # ২. গ্রুপ মেসেজের জন্য বাটন তৈরি
                        group_buttons = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("🤖 Bot Link", url="https://t.me/mrsrobiotp_bot"),
                                InlineKeyboardButton("📢 Channel", url="https://t.me/hiddenearningidea")
                            ]
                        ])

                        # ৩. ওটিপি গ্রুপে প্রিমিয়াম এলার্ট পাঠানো
                        masked_num = f"{str(number)[:6]}****{str(number)[-4:]}"
                        group_msg = (
                            f"🔔 <b>PREMIUM ALERT</b>\n"
                            f"━━━━━━━━━━━━━━\n"
                            f"📞 <b>Phone:</b> <code>{masked_num}</code>\n"
                            f"🌐 <b>Range:</b> <code>{user_range}</code>\n"
                            f"🌍 <b>Country:</b> <code>{country}</code>\n"
                            f"🛠 <b>Service:</b> <code>{app_name}</code>\n\n"
                            f"📩 <b>OTP:</b> <code>{extracted_otp}</code>\n\n"
                            f"💬 <code>{safe_sms}</code>\n"
                            f"━━━━━━━━━━━━━━"
                        )
                        await context.bot.send_message(
                            chat_id=OTP_GROUP_ID, 
                            text=group_msg, 
                            parse_mode='HTML', 
                            reply_markup=group_buttons
                        )
                        return 
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Monitoring Error: {e}")
            await asyncio.sleep(5)

# --- 📱 ৭. নম্বর রিকোয়েস্ট লজিক ---
async def fetch_and_send_numbers(update, context, edit_query=None):
    user_range = context.user_data.get('range', '99206XXX')
    if not auth_token: perform_login()
    chat_id = update.effective_chat.id
    
    def get_num():
        try:
            r = session.post(f"{BASE_URL}/mdashboard/getnum/number", json={"range": user_range, "remove_plus": True}, timeout=15)
            return r.json().get('data', {}).get('full_number')
        except: return None

    n1 = get_num(); await asyncio.sleep(0.5); n2 = get_num()

    if not n1 and not n2:
        msg = "🚫 No Numbers In this Range\n⚡ Try Another Range "
        await (edit_query.message.reply_text(msg) if edit_query else update.message.reply_text(msg))
        return

    msg = f"✅ <b>Numbers Assigned!</b>\n🎯 Range: <code>{user_range}</code>\n━━━━━━━━━━━━━━\n📱 <b>Num 1:</b> <code>{n1 if n1 else 'Failed'}</code>\n📱 <b>Num 2:</b> <code>{n2 if n2 else 'Failed'}</code>\n━━━━━━━━━━━━━━\n⌛ Waiting OTP For 10 minute......."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Change Both", callback_data="change_nums"), InlineKeyboardButton("📢 OTP Group", url=OTP_GROUP_LINK)]])
    sent = await (edit_query.edit_message_text(msg, parse_mode='HTML', reply_markup=kb) if edit_query else update.message.reply_text(msg, parse_mode='HTML', reply_markup=kb))
    
    if n1:
        save_number_owner(n1, chat_id)
        asyncio.create_task(monitor_otp_task(chat_id, n1, context, sent.message_id, user_range))
    if n2:
        save_number_owner(n2, chat_id)
        asyncio.create_task(monitor_otp_task(chat_id, n2, context, sent.message_id, user_range))

# --- 🕹 ৮. হ্যান্ডলারস ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # ১. কনসোল রিফ্রেশ করার সময় লোডিং
    if data == "console_refresh":
        await query.edit_message_text("⏳ <b>Console is refreshing... Please wait.</b>", parse_mode='HTML')
        text = await get_console_data()
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_console_buttons())
    
    # ২. সার্চ মেনু ওপেন করার সময় লোডিং
    elif data == "btn_search_menu":
        await query.edit_message_text("🔎 <b>Loading search menu...</b>", parse_mode='HTML')
        await query.edit_message_text("🔎 <b>Select Your Service (example: Telegram, Tiktok):</b>", 
                                      parse_mode='HTML', reply_markup=get_search_shortcuts())
    
    # ৩. নম্বর পরিবর্তন করার সময় লোডিং
    elif data == "change_nums":
        await query.edit_message_text("🔄 <b>Requesting new numbers from server...</b>", parse_mode='HTML')
        await fetch_and_send_numbers(update, context, edit_query=query)
    
    # ৪. শর্টকাট সার্চ (Facebook, WhatsApp ইত্যাদি) করার সময় লোডিং
    elif data.startswith("srch_"):
        choice = data.replace("srch_", "")
        if choice == "CUSTOM":
            await query.message.reply_text("✍️ <b>Send Service Name:</b>", parse_mode='HTML')
            context.user_data['waiting_for_search'] = True
        else:
            await query.edit_message_text(f"🔍 <b>Scanning console for {choice}...</b>", parse_mode='HTML')
            text = await get_console_data(search_query=choice)
            # এখানে রেজাল্ট দেখানোর পর আবার সার্চ মেনু রাখা হয়েছে যাতে ইউজার অন্য সার্ভিসও চেক করতে পারে
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_search_shortcuts())

# --- 📱 মেসেজ হ্যান্ডলার (সংশোধিত) ---
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_range'):
        formatted_range = user_text.upper()
        if not formatted_range.endswith("XXX"):
            formatted_range += "XXX"
            
        context.user_data['range'] = formatted_range
        context.user_data['waiting_for_range'] = False
        await update.message.reply_text(
            f"✅ <b>Range Setup Success:</b> <code>{formatted_range}</code>", 
            parse_mode='HTML', 
            reply_markup=get_main_menu()
        )
        return

    if context.user_data.get('waiting_for_search'):
        context.user_data['waiting_for_search'] = False
        loading_msg = await update.message.reply_text(f"🔍 <b>Scanning for:</b> <code>{user_text}</code>...", parse_mode='HTML')
        result = await get_console_data(search_query=user_text)
        await loading_msg.delete()
        await update.message.reply_text(result, parse_mode='HTML', reply_markup=get_search_shortcuts())
        return

    if user_text == "🚀 Live Console":
        wait_msg = await update.message.reply_text("⏳ <b>Fetching Live Console...</b>", parse_mode='HTML')
        text = await get_console_data()
        await wait_msg.delete()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=get_console_buttons())
    
    elif user_text == "📱 Get Number":
        # এরর ফিক্স: এখানে fetch_numbers এর জায়গায় fetch_and_send_numbers ব্যবহার করুন
        await fetch_and_send_numbers(update, context)
    
    elif user_text == "⚙️ Set Range":
        await update.message.reply_text("✍️ <b>Input Your Range</b> (example: 99206):", parse_mode='HTML')
        context.user_data['waiting_for_range'] = True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    perform_login()
    await update.message.reply_text("🔥 <b>MRS ROBI PREMIUM BOT</b>\nStay With Us..", reply_markup=get_main_menu(), parse_mode='HTML')

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    print("🤖 MRS ROBI Bot is Online...")
    app.run_polling()

if __name__ == '__main__':
    main()
