import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
import database

# تحميل متغيرات البيئة
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# حالات المستخدم
TEACHER, STUDENT = range(2)

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("👨‍🏫 معلم", callback_data='teacher')],
        [InlineKeyboardButton("👨‍🎓 طالب", callback_data='student')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "مرحباً! اختر هويتك:",
        reply_markup=reply_markup
    )

async def handle_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'teacher':
        context.user_data['role'] = TEACHER
        await query.edit_message_text(
            "مرحباً أيها المعلم!\n\n"
            "يمكنك إضافة أسئلة باستخدام الأمر:\n"
            "/add_question\n\n"
            "لمشاهدة الأسئلة:\n"
            "/view_questions"
        )
    else:
        context.user_data['role'] = STUDENT
        await query.edit_message_text(
            "مرحباً أيها الطالب!\n\n"
            "لبدء الاختبار:\n"
            "/take_test"
        )

# أوامر المعلم
async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('role') != TEACHER:
        await update.message.reply_text("هذا الأمر للمعلمين فقط!")
        return
    
    await update.message.reply_text(
        "أرسل السؤال كصورة ثم اتبع التعليمات:\n\n"
        "1. أرسل صورة السؤال\n"
        "2. اختر نوع السؤال"
    )
    context.user_data['awaiting_question'] = True

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_question'):
        return
    
    photo = update.message.photo[-1]
    file = await photo.get_file()
    
    # حفظ معلومات الصورة
    context.user_data['question_photo'] = file.file_id
    context.user_data['awaiting_question'] = False
    context.user_data['awaiting_type'] = True
    
    keyboard = [
        [InlineKeyboardButton("صح/خطأ", callback_data='type_true_false')],
        [InlineKeyboardButton("اختيار متعدد", callback_data='type_mcq')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "اختر نوع السؤال:",
        reply_markup=reply_markup
    )

async def handle_question_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'type_true_false':
        context.user_data['question_type'] = 'true_false'
        await query.edit_message_text(
            "أرسل الإجابة:\n"
            "✅ للصح\n"
            "❌ للخطأ"
        )
        context.user_data['awaiting_answer'] = True
    else:
        context.user_data['question_type'] = 'mcq'
        await query.edit_message_text(
            "أرسل الخيارات في السطور التالية:\n"
            "1. الخيار الأول\n"
            "2. الخيار الثاني\n"
            "3. الخيار الثالث\n"
            "4. الخيار الرابع\n\n"
            "بعدها أرسل رقم الإجابة الصحيحة (1-4)"
        )
        context.user_data['awaiting_options'] = True

# أوامر الطالب
async def take_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('role') != STUDENT:
        await update.message.reply_text("هذا الأمر للطلاب فقط!")
        return
    
    # جلب سؤال عشوائي
    question = database.get_random_question()
    
    if question:
        await update.message.reply_photo(
            photo=question['photo_id'],
            caption=f"السؤال {question['id']}"
        )
        
        if question['type'] == 'true_false':
            keyboard = [
                [InlineKeyboardButton("✅ صح", callback_data=f'answer_true_{question["id"]}')],
                [InlineKeyboardButton("❌ خطأ", callback_data=f'answer_false_{question["id"]}')]
            ]
        else:
            options = question['options']
            keyboard = [
                [InlineKeyboardButton(option, callback_data=f'answer_{i}_{question["id"]}')]
                for i, option in enumerate(options)
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "اختر الإجابة:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("لا توجد أسئلة متاحة حالياً!")

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # هنا يمكنك إضافة منطق التحقق من الإجابة
    await query.edit_message_text("تم تسجيل إجابتك!")

# دالة لتشغيل البوت على Render
def run_webhook():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    PORT = int(os.environ.get('PORT', 8443))
    APP_NAME = os.environ.get('APP_NAME')
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_role, pattern='^(teacher|student)$'))
    application.add_handler(CallbackQueryHandler(handle_question_type, pattern='^type_'))
    application.add_handler(CallbackQueryHandler(handle_answer, pattern='^answer_'))
    
    application.add_handler(CommandHandler('add_question', add_question))
    application.add_handler(CommandHandler('take_test', take_test))
    
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # تشغيل Webhook على Render
    if APP_NAME:  # يعني أننا على Render
        webhook_url = f'https://{APP_NAME}.onrender.com/{TOKEN}'
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url
        )
    else:  # للتشغيل المحلي
        application.run_polling()

# دالة Polling للتشغيل المحلي
def run_polling():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_role, pattern='^(teacher|student)$'))
    application.add_handler(CallbackQueryHandler(handle_question_type, pattern='^type_'))
    application.add_handler(CallbackQueryHandler(handle_answer, pattern='^answer_'))
    
    application.add_handler(CommandHandler('add_question', add_question))
    application.add_handler(CommandHandler('take_test', take_test))
    
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    application.run_polling()

if __name__ == '__main__':
    # اختيار طريقة التشغيل حسب البيئة
    if os.environ.get('RENDER'):
        run_webhook()
    else:
        run_polling()
