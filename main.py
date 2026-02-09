import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قاموس بسيط لتخزين الأسئلة (بدون قاعدة بيانات)
questions = {}
user_scores = {}

# أوامر البوت - إصدار مبسط جداً
def start(update: Update, context: CallbackContext):
    """عرض قائمة الاختيار"""
    keyboard = [
        [InlineKeyboardButton("👨‍🏫 أنا معلم", callback_data='teacher')],
        [InlineKeyboardButton("👨‍🎓 أنا طالب", callback_data='student')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('مرحباً! اختر هويتك:', reply_markup=reply_markup)

def handle_role(update: Update, context: CallbackContext):
    """معالجة اختيار الدور"""
    query = update.callback_query
    query.answer()
    
    if query.data == 'teacher':
        query.edit_message_text(
            '👨‍🏫 أهلاً أيها المعلم!\n\n'
            'لإضافة سؤال صح/خطأ:\n'
            '1. /add_true_false "نص السؤال" صح\n'
            '2. /add_true_false "نص السؤال" خطأ\n\n'
            'لإضافة سؤال اختيار:\n'
            '1. /add_mcq "نص السؤال" "الخيار1,الخيار2,الخيار3,الخيار4" رقم_الإجابة\n\n'
            'لعرض الأسئلة: /show_questions'
        )
        context.user_data['role'] = 'teacher'
    else:
        query.edit_message_text(
            '👨‍🎓 أهلاً أيها الطالب!\n\n'
            'لبدء الاختبار:\n/take_test\n\n'
            'لمعرفة نتيجتك:\n/score\n\n'
            'لإعادة الاختبار من جديد:\n/reset'
        )
        context.user_data['role'] = 'student'

# أوامر المعلم البسيطة
def add_true_false(update: Update, context: CallbackContext):
    """إضافة سؤال صح/خطأ"""
    if len(context.args) < 2:
        update.message.reply_text('❌ صيغة الأمر خطأ!\nاستخدم: /add_true_false "السؤال" صح_أو_خطأ')
        return
    
    question_text = context.args[0]
    answer = context.args[1].lower()
    
    if answer not in ['صح', 'خطأ']:
        update.message.reply_text('❌ الإجابة يجب تكون "صح" أو "خطأ"')
        return
    
    # حفظ السؤال
    q_id = len(questions) + 1
    questions[q_id] = {
        'text': question_text,
        'type': 'true_false',
        'answer': answer,
        'options': ['صح', 'خطأ']
    }
    
    update.message.reply_text(f'✅ تم إضافة السؤال رقم {q_id}')

def add_mcq(update: Update, context: CallbackContext):
    """إضافة سؤال اختيار متعدد"""
    if len(context.args) < 3:
        update.message.reply_text('❌ صيغة الأمر خطأ!\nاستخدم: /add_mcq "السؤال" "خيار1,خيار2,خيار3,خيار4" رقم_الإجابة')
        return
    
    question_text = context.args[0]
    options_str = context.args[1]
    answer_index = int(context.args[2])
    
    options = options_str.split(',')
    if len(options) < 2:
        update.message.reply_text('❌ يجب أن يكون هناك على الأقل خيارين')
        return
    
    if answer_index < 1 or answer_index > len(options):
        update.message.reply_text(f'❌ رقم الإجابة يجب أن يكون بين 1 و {len(options)}')
        return
    
    # حفظ السؤال
    q_id = len(questions) + 1
    questions[q_id] = {
        'text': question_text,
        'type': 'mcq',
        'answer': str(answer_index - 1),  # حفظ كمؤشر (0-based)
        'options': options
    }
    
    update.message.reply_text(f'✅ تم إضافة السؤال رقم {q_id}')

def show_questions(update: Update, context: CallbackContext):
    """عرض جميع الأسئلة"""
    if not questions:
        update.message.reply_text('📭 لا توجد أسئلة بعد.')
        return
    
    text = '📚 الأسئلة المتاحة:\n\n'
    for q_id, q in questions.items():
        text += f'🔹 {q_id}. {q["text"][:30]}... ({q["type"]})\n'
    
    update.message.reply_text(text)

# أوامر الطالب البسيطة
def take_test(update: Update, context: CallbackContext):
    """بدء اختبار للطالب"""
    if not questions:
        update.message.reply_text('📭 لا توجد أسئلة بعد. اطلب من المعلم إضافة أسئلة.')
        return
    
    # اختيار سؤال عشوائي
    import random
    q_id = random.choice(list(questions.keys()))
    question = questions[q_id]
    
    # حفظ السؤال الحالي للمستخدم
    context.user_data['current_question'] = q_id
    
    if question['type'] == 'true_false':
        keyboard = [
            [InlineKeyboardButton("✅ صح", callback_data=f'answer_true_{q_id}')],
            [InlineKeyboardButton("❌ خطأ", callback_data=f'answer_false_{q_id}')]
        ]
        reply_text = f'📝 السؤال {q_id}:\n{question["text"]}\n\nاختر الإجابة:'
    else:
        keyboard = []
        for i, option in enumerate(question['options']):
            keyboard.append([InlineKeyboardButton(f"{i+1}. {option}", callback_data=f'answer_{i}_{q_id}')])
        reply_text = f'📝 السؤال {q_id}:\n{question["text"]}\n\nاختر الإجابة:'
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(reply_text, reply_markup=reply_markup)

def handle_answer(update: Update, context: CallbackContext):
    """معالجة إجابة الطالب"""
    query = update.callback_query
    query.answer()
    
    # استخراج البيانات
    parts = query.data.split('_')
    user_answer = parts[1]
    q_id = int(parts[2])
    
    # الحصول على السؤال
    question = questions.get(q_id)
    if not question:
        query.edit_message_text('❌ السؤال غير موجود!')
        return
    
    # تهيئة النتيجة إذا لم تكن موجودة
    user_id = query.from_user.id
    if user_id not in user_scores:
        user_scores[user_id] = {'total': 0, 'correct': 0}
    
    # التحقق من الإجابة
    user_scores[user_id]['total'] += 1
    
    if question['type'] == 'true_false':
        is_correct = (user_answer == question['answer'])
        correct_text = f"✅ الإجابة الصحيحة: {question['answer']}"
    else:
        is_correct = (user_answer == question['answer'])
        correct_index = int(question['answer'])
        correct_text = f"✅ الإجابة الصحيحة: {question['options'][correct_index]}"
    
    if is_correct:
        user_scores[user_id]['correct'] += 1
        result = "🎉 إجابة صحيحة! أحسنت!"
    else:
        result = f"❌ إجابة خاطئة. {correct_text}"
    
    # إضافة زر للسؤال التالي
    keyboard = [[InlineKeyboardButton("السؤال التالي ➡️", callback_data='next')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(f"{result}\n\n{correct_text}\n\nاضغط للسؤال التالي:", reply_markup=reply_markup)

def next_question(update: Update, context: CallbackContext):
    """عرض السؤال التالي"""
    query = update.callback_query
    query.answer()
    
    # محاكاة تحديث الرسالة
    query.delete_message()
    
    # إنشاء تحديث جديد
    new_update = Update(update.update_id + 1)
    new_update.message = query.message
    
    take_test(new_update, context)

def show_score(update: Update, context: CallbackContext):
    """عرض نتيجة الطالب"""
    user_id = update.message.from_user.id
    
    if user_id not in user_scores or user_scores[user_id]['total'] == 0:
        update.message.reply_text('📊 لم تجب على أي أسئلة بعد!\nابدأ باستخدام /take_test')
        return
    
    score = user_scores[user_id]
    percentage = (score['correct'] / score['total']) * 100
    
    update.message.reply_text(
        f'📊 نتيجتك:\n\n'
        f'✅ صحيحة: {score["correct"]}\n'
        f'❌ خاطئة: {score["total"] - score["correct"]}\n'
        f'📈 النسبة: {percentage:.1f}%\n\n'
        f'تابع التدرب: /take_test'
    )

def reset_score(update: Update, context: CallbackContext):
    """إعادة تعيين النتيجة"""
    user_id = update.message.from_user.id
    user_scores[user_id] = {'total': 0, 'correct': 0}
    update.message.reply_text('🔄 تم إعادة تعيين نتيجتك. ابدأ من جديد!')

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    
    # الحصول على التوكن من متغير البيئة في Replit
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        # إذا لم يكن موجوداً، اطلبه من المستخدم
        print("=" * 50)
        print("⚠️  لم يتم تعيين توكن البوت!")
        print("=" * 50)
        print("\n1. اذهب إلى @BotFather على تيليجرام")
        print("2. أرسل /newbot")
        print("3. اختر اسم للبوت")
        print("4. احفظ التوكن الذي ستحصل عليه")
        print("5. في Replit، انقر على 🔧 Secrets (الأيقونة على اليمين)")
        print("6. أضف متغير جديد:")
        print("   المفتاح: TELEGRAM_BOT_TOKEN")
        print("   القيمة: التوكن الذي حصلت عليه")
        print("7. أعد تشغيل البوت")
        print("\n" + "=" * 50)
        return
    
    # إنشاء البوت
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # إضافة الأوامر
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('add_true_false', add_true_false, pass_args=True))
    dispatcher.add_handler(CommandHandler('add_mcq', add_mcq, pass_args=True))
    dispatcher.add_handler(CommandHandler('show_questions', show_questions))
    dispatcher.add_handler(CommandHandler('take_test', take_test))
    dispatcher.add_handler(CommandHandler('score', show_score))
    dispatcher.add_handler(CommandHandler('reset', reset_score))
    
    # معالجات Callback
    dispatcher.add_handler(CallbackQueryHandler(handle_role, pattern='^(teacher|student)$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_answer, pattern='^answer_'))
    dispatcher.add_handler(CallbackQueryHandler(next_question, pattern='^next$'))
    
    # بدء البوت
    print("🤖 البوت يعمل بنجاح!")
    print("🔗 اذهب إلى تيليجرام وأرسل /start للبوت")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
