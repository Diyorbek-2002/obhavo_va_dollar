import asyncio
import aiohttp
import json
import os
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import schedule
import time

# ===== SOZLAMALAR =====
BOT_TOKEN = "8594736554:AAEkMGbvNP2m3dAu0-OHVaHen3RQkGfx5mU"  # Bu yerni o'zgartiring!
WEATHER_API_KEY = "3b436612e49b2c7690ceb8dd66034f30"  # https://openweathermap.org/api dan oling

# Admin chat ID - sizning shaxsiy Telegram ID
ADMIN_CHAT_ID = 1440624298

# Foydalanuvchilar ma'lumotlari fayli
USERS_FILE = "bot_users.json"

# ===== FOYDALANUVCHILARNI BOSHQARISH =====
def load_users():
    """Foydalanuvchilar ro'yxatini yuklash"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_users(users):
    """Foydalanuvchilar ro'yxatini saqlash"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def add_user(chat_id):
    """Yangi foydalanuvchini qo'shish"""
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        save_users(users)
        return True
    return False

def remove_user(chat_id):
    """Foydalanuvchini o'chirish"""
    users = load_users()
    if chat_id in users:
        users.remove(chat_id)
        save_users(users)
        return True
    return False

# ===== VALYUTA KURSI =====
async def get_currency_rates():
    """Dollar kursini olish (UZS va GBP)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.exchangerate-api.com/v4/latest/USD') as resp:
                data = await resp.json()
                usd_to_uzs = data['rates'].get('UZS', 'Ma\'lumot topilmadi')
                usd_to_gbp = data['rates'].get('GBP', 'Ma\'lumot topilmadi')
        
        return {
            'uzs': round(usd_to_uzs, 2) if isinstance(usd_to_uzs, (int, float)) else usd_to_uzs,
            'gbp': round(usd_to_gbp, 4) if isinstance(usd_to_gbp, (int, float)) else usd_to_gbp
        }
    except Exception as e:
        return {'uzs': f'Xato: {e}', 'gbp': f'Xato: {e}'}

# ===== OB-HAVO =====
async def get_weather(city):
    """Ob-havo ma'lumotini olish"""
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=uz"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                
                if data.get('cod') == 200:
                    temp = round(data['main']['temp'])
                    feels_like = round(data['main']['feels_like'])
                    description = data['weather'][0]['description']
                    humidity = data['main']['humidity']
                    
                    return {
                        'temp': temp,
                        'feels_like': feels_like,
                        'description': description,
                        'humidity': humidity
                    }
                else:
                    return {'error': 'Ma\'lumot topilmadi'}
    except Exception as e:
        return {'error': f'Xato: {e}'}

# ===== XABAR TAYYORLASH =====
async def create_daily_message():
    """Kundalik xabarni tayyorlash"""
    currency = await get_currency_rates()
    tashkent_weather = await get_weather('Tashkent')
    london_weather = await get_weather('London')
    
    today = datetime.now().strftime('%d.%m.%Y')
    
    message = f"🌅 <b>Kunlik ma'lumotlar - {today}</b>\n\n"
    
    # Valyuta
    message += "💵 <b>VALYUTA KURSLARI</b>\n"
    message += f"1 USD = {currency['uzs']} UZS\n"
    message += f"1 USD = {currency['gbp']} GBP\n\n"
    
    # Toshkent ob-havosi
    message += "🌍 <b>TOSHKENT</b>\n"
    if 'error' not in tashkent_weather:
        message += f"🌡 Harorat: {tashkent_weather['temp']}°C (his etiladi: {tashkent_weather['feels_like']}°C)\n"
        message += f"☁️ Holat: {tashkent_weather['description']}\n"
        message += f"💧 Namlik: {tashkent_weather['humidity']}%\n\n"
    else:
        message += f"❌ {tashkent_weather['error']}\n\n"
    
    # London ob-havosi
    message += "🇬🇧 <b>LONDON</b>\n"
    if 'error' not in london_weather:
        message += f"🌡 Harorat: {london_weather['temp']}°C (his etiladi: {london_weather['feels_like']}°C)\n"
        message += f"☁️ Holat: {london_weather['description']}\n"
        message += f"💧 Namlik: {london_weather['humidity']}%\n"
    else:
        message += f"❌ {london_weather['error']}\n"
    
    message += "\n✨ Yaxshi kun tilayman!"
    
    return message

# ===== KUNDALIK XABAR YUBORISH =====
async def send_daily_messages():
    """Barcha foydalanuvchilarga xabar yuborish"""
    bot = Bot(token=BOT_TOKEN)
    users = load_users()
    
    if not users:
        print("⚠️ Hech qanday foydalanuvchi yo'q")
        return
    
    message = await create_daily_message()
    
    success_count = 0
    fail_count = 0
    
    for chat_id in users:
        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
            success_count += 1
            print(f"✅ Xabar yuborildi: {chat_id}")
        except Exception as e:
            fail_count += 1
            print(f"❌ Xato ({chat_id}): {e}")
    
    print(f"📊 Jami: {success_count} muvaffaqiyatli, {fail_count} xato - {datetime.now()}")

# ===== /START KOMANDASI =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchini ro'yxatdan o'tkazish"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Foydalanuvchi ma'lumotlarini to'plash
    username = user.username if user.username else "Yo'q"
    first_name = user.first_name if user.first_name else "Yo'q"
    last_name = user.last_name if user.last_name else "Yo'q"
    language = user.language_code if user.language_code else "Yo'q"
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    
    is_new = add_user(chat_id)
    
    # Adminга xabar yuborish
    if is_new:
        bot = Bot(token=BOT_TOKEN)
        admin_message = (
            f"🆕 <b>YANGI FOYDALANUVCHI!</b>\n\n"
            f"👤 <b>Ism:</b> {first_name}\n"
            f"👥 <b>Familiya:</b> {last_name}\n"
            f"🆔 <b>Username:</b> @{username}\n"
            f"🔢 <b>User ID:</b> <code>{chat_id}</code>\n"
            f"🌍 <b>Til:</b> {language}\n"
            f"⏰ <b>Sana/Vaqt:</b> {current_time}\n\n"
            f"📊 <b>Jami foydalanuvchilar:</b> {len(load_users())}"
        )
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode='HTML')
        except Exception as e:
            print(f"Adminga xabar yuborishda xato: {e}")
    
    if is_new:
        await update.message.reply_text(
            "👋 <b>Xush kelibsiz!</b>\n\n"
            "✅ Siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
            "📅 Endi har kuni ertalab soat <b>7:00</b> da sizga quyidagi ma'lumotlar yuboriladi:\n"
            "• 💵 Dollar kursi (UZS va GBP)\n"
            "• 🌍 Toshkent ob-havosi\n"
            "• 🇬🇧 London ob-havosi\n\n"
            "🔹 <b>Komandalar:</b>\n"
            "/test - Hozir test xabari olish\n"
            "/stop - Xabarlarni to'xtatish\n"
            "/start - Qayta boshlash",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "👋 Siz allaqachon ro'yxatdansiz!\n\n"
            "Har kuni soat 7:00 da ma'lumotlar olasiz.\n\n"
            "/test - Test xabari\n"
            "/stop - To'xtatish",
            parse_mode='HTML'
        )

# ===== /STOP KOMANDASI =====
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni to'xtatish"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if remove_user(chat_id):
        # Adminга xabar
        bot = Bot(token=BOT_TOKEN)
        username = user.username if user.username else "Yo'q"
        first_name = user.first_name if user.first_name else "Yo'q"
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        
        admin_message = (
            f"❌ <b>FOYDALANUVCHI CHIQDI</b>\n\n"
            f"👤 <b>Ism:</b> {first_name}\n"
            f"🆔 <b>Username:</b> @{username}\n"
            f"🔢 <b>User ID:</b> <code>{chat_id}</code>\n"
            f"⏰ <b>Sana/Vaqt:</b> {current_time}\n\n"
            f"📊 <b>Qolgan foydalanuvchilar:</b> {len(load_users())}"
        )
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode='HTML')
        except Exception as e:
            print(f"Adminga xabar yuborishda xato: {e}")
        
        await update.message.reply_text(
            "👋 Siz ro'yxatdan chiqdingiz.\n\n"
            "Endi sizga kundalik xabarlar kelmaydi.\n\n"
            "Qayta boshlash uchun /start yuboring.",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "Siz ro'yxatda emassiz.\n\n"
            "Ro'yxatdan o'tish uchun /start yuboring."
        )

# ===== /TEST KOMANDASI =====
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test xabari yuborish"""
    chat_id = update.effective_chat.id
    users = load_users()
    
    if chat_id not in users:
        await update.message.reply_text(
            "⚠️ Avval /start yuboring!"
        )
        return
    
    message = await create_daily_message()
    await update.message.reply_text(message, parse_mode='HTML')

# ===== /STATS KOMANDASI =====
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika ko'rsatish"""
    users = load_users()
    await update.message.reply_text(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Jami foydalanuvchilar: {len(users)}",
        parse_mode='HTML'
    )

# ===== SCHEDULER =====
def schedule_jobs():
    """Har kuni soat 7:00 da ishga tushirish"""
    schedule.every().day.at("07:00").do(lambda: asyncio.run(send_daily_messages()))
    
    print("⏰ Scheduler ishga tushdi - har kuni soat 7:00 da xabar yuboriladi")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ===== ASOSIY DASTUR =====
async def main():
    """Botni ishga tushirish"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Komandalarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("stats", stats))
    
    print("🤖 Bot ishga tushdi!")
    print("⏰ Har kuni ertalab 7:00 da barcha foydalanuvchilarga xabar yuboriladi")
    print(f"👥 Hozirda {len(load_users())} foydalanuvchi")
    
    # Botni ishga tushirish
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Scheduler ni alohida threadda ishga tushirish
    import threading
    scheduler_thread = threading.Thread(target=schedule_jobs, daemon=True)
    scheduler_thread.start()
    
    # Botni to'xtatmaslik uchun
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
