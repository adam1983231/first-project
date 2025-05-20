import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta
import asyncio
import logging
from collections import defaultdict

# Настройки
TOKEN = "6388163209:AAHT9wHQBdTXaFieGrWMc9RqmSX-MoilpIM"
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CURRENCIES = {
    "USD": {"name": "Доллар США", "symbol": "💵", "flag": "🇺🇸"},
    "EUR": {"name": "Евро", "symbol": "💶", "flag": "🇪🇺"},
    "CNY": {"name": "Китайский юань", "symbol": "💴", "flag": "🇨🇳"},
    "TRY": {"name": "Турецкая лира", "symbol": "🇹🇷", "flag": "🇹🇷"},
    "JPY": {"name": "Японская йена", "symbol": "💴", "flag": "🇯🇵"}
}

# Хранение избранных валют пользователей
user_favorites = defaultdict(set)

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
        'flag': CURRENCIES[currency_code]['flag'],
        'value': currency['Value'],
        'previous': currency['Previous'],
        'change': currency['Value'] - currency['Previous'],
        'change_percent': (currency['Value'] / currency['Previous'] - 1) * 100
    }

def generate_currency_chart(currency_data, days=7):
    dates = [datetime.now() - timedelta(days=i) for i in range(days, -1, -1)]
    values = [100 + i*2 for i in range(days+1)]  # Здесь должна быть реальная историческая data
    
    plt.figure(figsize=(10, 5))
    plt.plot(dates, values, marker='o', linestyle='-', color='#4CAF50')
    plt.title(f"{currency_data['flag']} Динамика курса {currency_data['name']} за {days} дней", pad=20)
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
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton(f"{CURRENCIES['USD']['flag']} Доллар", callback_data='USD'),
         InlineKeyboardButton(f"{CURRENCIES['EUR']['flag']} Евро", callback_data='EUR')],
        [InlineKeyboardButton(f"{CURRENCIES['CNY']['flag']} Юань", callback_data='CNY'),
         InlineKeyboardButton(f"{CURRENCIES['TRY']['flag']} Лира", callback_data='TRY')],
        [InlineKeyboardButton("⭐ Избранное", callback_data='favorites'),
         InlineKeyboardButton("📊 Все курсы", callback_data='all')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about'),
         InlineKeyboardButton("🔔 Подписаться", callback_data='subscribe')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"💰 <b>Курсы валют ЦБ РФ</b>\n\n"
        f"Привет, {update.effective_user.first_name}!\n"
        "Выберите валюту или действие:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == 'about':
        await query.edit_message_text(
            text="<b>💰 CurrencyBot Pro</b>\n\n"
                 "🔹 Актуальные курсы валют ЦБ РФ\n"
                 "🔹 Графики изменений\n"
                 "🔹 Избранные валюты\n"
                 "🔹 Уведомления об изменениях\n\n"
                 "📊 <i>Самый удобный бот для отслеживания курсов!</i>",
            parse_mode='HTML'
        )
        return
    
    if query.data == 'favorites':
        if not user_favorites[user_id]:
            await query.edit_message_text("У вас пока нет избранных валют. Добавьте их через меню.")
            return
            
        keyboard = []
        for currency_code in user_favorites[user_id]:
            currency = CURRENCIES.get(currency_code, {})
            keyboard.append([InlineKeyboardButton(
                f"{currency.get('flag', '')} {currency.get('name', currency_code)}", 
                callback_data=currency_code
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='back')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⭐ <b>Ваши избранные валюты</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    if query.data == 'all':
        data = await fetch_currency_data()
        if not data:
            await query.edit_message_text("⚠️ Не удалось получить данные о курсах. Попробуйте позже.")
            return
        
        message_text = "📊 <b>Все курсы ЦБ РФ</b>\n\n"
        for code, currency in CURRENCIES.items():
            if code in data['Valute']:
                val = data['Valute'][code]
                change = val['Value'] - val['Previous']
                change_percent = (val['Value'] / val['Previous'] - 1) * 100
                arrow = "📈" if change > 0 else "📉"
                message_text += (
                    f"{currency['flag']} <b>{currency['name']}</b>: {val['Value']:.2f} руб.\n"
                    f"{arrow} {change:+.2f} ({change_percent:+.2f}%)\n\n"
                )
        
        await query.edit_message_text(
            message_text,
            parse_mode='HTML'
        )
        return
    
    if query.data == 'subscribe':
        # Здесь можно добавить логику подписки на уведомления
        await query.edit_message_text(
            "🔔 <b>Уведомления о курсах валют</b>\n\n"
            "Хотите получать уведомления при значительных изменениях курсов?\n\n"
            "Эта функция скоро появится!",
            parse_mode='HTML'
        )
        return
    
    if query.data == 'back':
        await start(update, context)
        return
    
    # Обработка выбора валюты
    if query.data in CURRENCIES:
        # Добавляем в избранное при долгом нажатии
        if hasattr(query, 'data_long') and query.data_long:
            user_favorites[user_id].add(query.data)
            await query.answer(f"{CURRENCIES[query.data]['name']} добавлен в избранное!")
    
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
    
    # Кнопки для этой валюты
    keyboard = [
        [InlineKeyboardButton("7 дней", callback_data=f'chart_7_{query.data}'),
         InlineKeyboardButton("30 дней", callback_data=f'chart_30_{query.data}')],
        [InlineKeyboardButton("Добавить в избранное", callback_data=f'add_{query.data}')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Отправляем сообщение
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart,
            caption=f"{currency_info['flag']} <b>{currency_info['name']}</b>\n\n"
                    f"<b>Текущий курс:</b> {currency_info['value']:.2f} руб.\n"
                    f"<b>Изменение:</b> {change_emoji} {change_text}\n\n"
                    f"<i>Данные ЦБ РФ на {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if any(word in text for word in ['курс', 'валют', 'доллар', 'евро', 'юань']):
        await start(update, context)
    else:
        await update.message.reply_text(
            "Используйте команду /start для отображения курсов валют",
            parse_mode='HTML'
        )

def main():
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()