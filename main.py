import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    CallbackContext
)
from dotenv import load_dotenv
import sqlite3
import json

# تحميل متغيرات البيئة
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_text TEXT NOT NULL,
        question_type TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        options TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# أوامر البوت
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("👨‍🏫 معلم", callback_data='teacher')],
        [InlineKeyboardButton("👨‍🎓 طالب", callback_data='student')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "مرحباً! اختر هويتك:",
        reply_markup=reply_markup
    )

def handle_role(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.data == 'teacher':
        context.user_data['role'] = 'teacher'
        query.edit_message_text(
            "مرحباً أيها المعلم!\n\n"
            "يمكنك إضافة أسئلة باستخدام:\n"
            "/add_question\n\n"
            "لمشاهدة الأسئلة:\n"
            "/view_questions"
        )
    else:
        context.user_data['role'] = 'student'
        query.edit_message_text(
            "مرحباً أيها الطالب!\n\n"
            "لبدء الاختبار:\n"
            "/take_test\n\n"
            "لرصيدك:\n"
            "/score"
        )

# المعلم: إضافة سؤال
def add_question(update: Update, context: CallbackContext):
    user_data = context.user_data
    
    if user_data.get('role') != 'teacher':
        update.message.reply_text("❌ هذا الأمر للمعلمين فقط!")
        return
    
    if not context.args:
        update.message.reply_text(
            "📝 لإضافة سؤال:\n\n"
            "1. صح/خطأ:\n"
            "   /add_question true_false \"السؤال هنا\" \"الإجابة (true/false)\"\n\n"
            "2. اختيار متعدد:\n"
            "   /add_question mcq \"السؤال هنا\" \"الخيار1,الخيار2,الخيار3,الخيار4\" \"رقم_الإجابة_الصحيحة\""
        )
        return
    
    try:
        q_type = context.args[0]
        question_text = context.args[1]
        
        if q_type == 'true_false':
            correct_answer = context.args[2].lower()
            if correct_answer not in ['true', 'false']:
                update.message.reply_text("❌ الإجابة يجب أن تكون 'true' أو 'false'")
                return
            
            # حفظ في قاعدة البيانات
            conn = sqlite3.connect('questions.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO questions (question_text, question_type, correct_answer) VALUES (?, ?, ?)",
                (question_text, q_type, correct_answer)
            )
            conn.commit()
            conn.close()
            
            update.message.reply_text("✅ تم إضافة السؤال بنجاح!")
            
        elif q_type == 'mcq':
            options = context.args[2]
            correct_index = int(context.args[3])
            
            # تحقق من صحة الفهرس
            options_list = options.split(',')
            if len(options_list) < 2 or correct_index < 0 or correct_index >= len(options_list):
                update.message.reply_text("❌ تأكد من صحة الخيارات ورقم الإجابة الصحيحة")
                return
            
            # حفظ في قاعدة البيانات
            conn = sqlite3.connect('questions.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO questions (question_text, question_type, correct_answer, options) VALUES (?, ?, ?, ?)",
                (question_text, q_type, str(correct_index), options)
            )
            conn.commit()
            conn.close()
            
            update.message.reply_text("✅ تم إضافة السؤال بنجاح!")
            
        else:
            update.message.reply_text("❌ نوع السؤال غير معروف. استخدم 'true_false' أو 'mcq'")
            
    except Exception as e:
        update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

# عرض الأسئلة للمعلم
def view_questions(update: Update, context: CallbackContext):
    if context.user_data.get('role') != 'teacher':
        update.message.reply_text("❌ هذا الأمر للمعلمين فقط!")
        return
    
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_text, question_type FROM questions ORDER BY id")
    questions = cursor.fetchall()
    conn.close()
    
    if not questions:
        update.message.reply_text("📭 لا توجد أسئلة بعد.")
        return
    
    response = "📚 الأسئلة المتاحة:\n\n"
    for q_id, text, q_type in questions:
        response += f"🔹 {q_id}. {text[:50]}... ({q_type})\n"
    
    update.message.reply_text(response)

# الطالب: بدء الاختبار
def take_test(update: Update, context: CallbackContext):
    if context.user_data.get('role') != 'student':
        update.message.reply_text("❌ هذا الأمر للطلاب فقط!")
        return
    
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
    question = cursor.fetchone()
    conn.close()
    
    if not question:
        update.message.reply_text("📭 لا توجد أسئلة متاحة حالياً.")
        return
    
    # استخراج بيانات السؤال
    q_id, text, q_type, correct_answer, options, created_at = question
    
    # حفظ السؤال الحالي في سياق المستخدم
    context.user_data['current_question'] = {
        'id': q_id,
        'type': q_type,
        'correct': correct_answer
    }
    
    if q_type == 'true_false':
        keyboard = [
            [InlineKeyboardButton("✅ صح", callback_data=f'answer_true_{q_id}')],
            [InlineKeyboardButton("❌ خطأ", callback_data=f'answer_false_{q_id}')]
        ]
        question_text = f"📝 السؤال:\n{text}\n\nاختر الإجابة:"
        
    else:  # mcq
        options_list = options.split(',') if options else []
        keyboard = []
        for i, option in enumerate(options_list):
            keyboard.append([InlineKeyboardButton(f"{i+1}. {option}", callback_data=f'answer_{i}_{q_id}')])
        
        question_text = f"📝 السؤال:\n{text}\n\nالخيارات:\n"
        for i, option in enumerate(options_list):
            question_text += f"{i+1}. {option}\n"
        question_text += "\nاختر الإجابة:"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(question_text, reply_markup=reply_markup)

# معالجة الإجابات
def handle_answer(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    # استخراج البيانات من callback_data
    parts = query.data.split('_')
    answer_type = parts[1] if len(parts) > 2 else parts[0]
    q_id = int(parts[-1])
    
    # الحصول على السؤال الحالي
    current_q = context.user_data.get('current_question', {})
    
    if current_q.get('id') != q_id:
        query.edit_message_text("⚠️ انتهى وقت هذا السؤال.")
        return
    
    # حساب الإجابة
    user_answer = parts[1] if len(parts) > 2 else None
    if current_q['type'] == 'true_false':
        correct = current_q['correct']
        is_correct = (user_answer == correct)
        
        # تخزين النتيجة
        if 'score' not in context.user_data:
            context.user_data['score'] = {'total': 0, 'correct': 0}
        
        context.user_data['score']['total'] += 1
        if is_correct:
            context.user_data['score']['correct'] += 1
            result_text = "✅ إجابة صحيحة! أحسنت!"
        else:
            result_text = f"❌ إجابة خاطئة. الإجابة الصحيحة: {'صح' if correct == 'true' else 'خطأ'}"
    
    else:  # mcq
        user_choice = int(user_answer) if user_answer else None
        correct_choice = int(current_q['correct'])
        
        # تخزين النتيجة
        if 'score' not in context.user_data:
            context.user_data['score'] = {'total': 0, 'correct': 0}
        
        context.user_data['score']['total'] += 1
        if user_choice == correct_choice:
            context.user_data['score']['correct'] += 1
            result_text = "✅ إجابة صحيحة! أحسنت!"
        else:
            result_text = f"❌ إجابة خاطئة. الإجابة الصحيحة: {correct_choice + 1}"
    
    # إضافة زر للسؤال التالي
    keyboard = [[InlineKeyboardButton("السؤال التالي ➡️", callback_data='next_question')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(f"{result_text}\n\nاضغط للسؤال التالي:", reply_markup=reply_markup)

# السؤال التالي
def next_question(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    # حذف رسالة السابق
    query.delete_message()
    
    # عرض سؤال جديد
    take_test_callback = Update(update.update_id)
    take_test_callback.message = query.message
    take_test(take_test_callback, context)

# عرض النتيجة
def show_score(update: Update, context: CallbackContext):
    score = context.user_data.get('score', {'total': 0, 'correct': 0})
    
    if score['total'] == 0:
        update.message.reply_text("📊 لم تجب على أي أسئلة بعد.\nابدأ الاختبار باستخدام /take_test")
        return
    
    percentage = (score['correct'] / score['total']) * 100
    
    update.message.reply_text(
        f"📊 نتيجتك:\n\n"
        f"✅ الإجابات الصحيحة: {score['correct']}\n"
        f"❌ الإجابات الخاطئة: {score['total'] - score['correct']}\n"
        f"📈 النسبة المئوية: {percentage:.1f}%\n\n"
        f"تابع التدرب باستخدام /take_test"
    )

# دالة الخطأ
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"حدث خطأ: {context.error}")

# الدالة الرئيسية
def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ لم يتم تعيين TELEGRAM_BOT_TOKEN")
        return
    
    # إنشاء الـ Updater
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # إضافة المعالجات
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('add_question', add_question, pass_args=True))
    dispatcher.add_handler(CommandHandler('view_questions', view_questions))
    dispatcher.add_handler(CommandHandler('take_test', take_test))
    dispatcher.add_handler(CommandHandler('score', show_score))
    
    # معالجات Callback Query
    dispatcher.add_handler(CallbackQueryHandler(handle_role, pattern='^(teacher|student)$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_answer, pattern='^answer_'))
    dispatcher.add_handler(CallbackQueryHandler(next_question, pattern='^next_question$'))
    
    # معالج الخطأ
    dispatcher.add_error_handler(error_handler)
    
    # بدء البوت
    logger.info("🤖 بدء تشغيل البوت...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
