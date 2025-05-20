import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta
import asyncio
import logging

# Настройки
TOKEN = "7672838723:AAEOWL1XxhSSV3VCBn7owLmBy4ky5mgMXYc"
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CURRENCIES = {
    "USD": {"name": "Доллар США", "symbol": "💵"},
    "EUR": {"name": "Евро", "symbol": "💶"},
    "CNY": {"name": "Китайский юань", "symbol": "💴"}
}

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def fetch_currency_data():
    try:
        response = await asyncio.to_thread(requests.get, CBR_API_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка при получении данных: {e}")
        return None

def get_currency_info(currency_code, data):
    if not data or 'Valute' not in data:
        return None
        
    currency = data['Valute'].get(currency_code)
    if not currency:
        return None
        
    return {
        'name': CURRENCIES[currency_code]['name'],
        'symbol': CURRENCIES[currency_code]['symbol'],
        'value': currency['Value'],
        'previous': currency['Previous'],
        'change': currency['Value'] - currency['Previous'],
        'change_percent': (currency['Value'] / currency['Previous'] - 1) * 100
    }

def generate_currency_chart(currency_data):
    dates = [datetime.now() - timedelta(days=i) for i in range(7, -1, -1)]
    values = [100 + i*2 for i in range(8)]  # Здесь должна быть реальная историческая data
    
    plt.figure(figsize=(10, 5))
    plt.plot(dates, values, marker='o', linestyle='-', color='#4CAF50')
    plt.title(f"Динамика курса {currency_data['name']} за неделю", pad=20)
    plt.xlabel('Дата')
    plt.ylabel('Курс, руб')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=80)
    buf.seek(0)
    plt.close()
    return buf

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"{CURRENCIES['USD']['symbol']} Доллар", callback_data='USD')],
        [InlineKeyboardButton(f"{CURRENCIES['EUR']['symbol']} Евро", callback_data='EUR')],
        [InlineKeyboardButton(f"{CURRENCIES['CNY']['symbol']} Юань", callback_data='CNY')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💰 <b>Курсы валют ЦБ РФ</b>\n\n"
        "Выберите валюту для отображения актуального курса и динамики изменений:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'about':
        await query.edit_message_text(
            text="<b>💰 Бот курсов валют</b>\n\n"
                 "Этот бот показывает актуальные курсы валют ЦБ РФ с графиками изменений.\n\n"
                 "Данные обновляются ежедневно.\n"
                 "Разработчик: @ваш_ник",
            parse_mode='HTML'
        )
        return
    
    data = await fetch_currency_data()
    if not data:
        await query.edit_message_text("⚠️ Не удалось получить данные о курсах валют. Попробуйте позже.")
        return
        
    currency_info = get_currency_info(query.data, data)
    if not currency_info:
        await query.edit_message_text("⚠️ Не удалось получить информацию по выбранной валюте.")
        return
    
    # Форматируем текст изменения курса
    if currency_info['change'] > 0:
        change_emoji = "📈"
        change_text = f"+{currency_info['change']:.2f} ({currency_info['change_percent']:.2f}%)"
    else:
        change_emoji = "📉"
        change_text = f"{currency_info['change']:.2f} ({currency_info['change_percent']:.2f}%)"
    
    # Генерируем график
    chart = generate_currency_chart(currency_info)
    
    try:
        # Отправляем сообщение (без span)
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart,
            caption=f"{currency_info['symbol']} <b>{currency_info['name']}</b>\n\n"
                    f"<b>Текущий курс:</b> {currency_info['value']:.2f} руб.\n"
                    f"<b>Изменение:</b> {change_emoji} {change_text}\n\n"
                    f"<i>Данные ЦБ РФ на {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса.")

def main():
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_button))
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()