import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import json
import os
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ملفات التخزين
QUESTIONS_FILE = "questions.json"
RESULTS_FILE = "results.json"

# حالات المحادثة
STATE_ADD_QUESTION = 1
STATE_ADD_OPTIONS = 2
STATE_ADD_CORRECT_ANSWER = 3

# تحميل الأسئلة من الملف
def load_questions():
    if os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"multiple_choice": [], "true_false": []}

# حفظ الأسئلة في الملف
def save_questions(questions):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

# تحميل النتائج
def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# حفظ النتائج
def save_results(results):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = []
    
    if str(user.id) == context.bot_data.get("admin_id", ""):
        # واجهة المدير (المعلم)
        keyboard = [
            [InlineKeyboardButton("📝 إضافة سؤال جديد", callback_data="add_question")],
            [InlineKeyboardButton("📋 عرض الأسئلة", callback_data="view_questions")],
            [InlineKeyboardButton("🧪 بدء الاختبار", callback_data="start_test")],
            [InlineKeyboardButton("📊 عرض النتائج", callback_data="view_results")]
        ]
        message = f"مرحباً أستاذ {user.first_name}! اختر من القائمة:"
    else:
        # واجهة الطالب
        keyboard = [
            [InlineKeyboardButton("🧪 بدء الاختبار", callback_data="start_test")],
            [InlineKeyboardButton("📊 نتائجي السابقة", callback_data="my_results")]
        ]
        message = f"مرحباً {user.first_name}! اختر من القائمة:"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

# التعامل مع الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if query.data == "add_question":
        if user_id != context.bot_data.get("admin_id", ""):
            await query.edit_message_text("⛔ هذا الأمر للمعلم فقط!")
            return
        
        keyboard = [
            [InlineKeyboardButton("اختيار من متعدد", callback_data="add_multiple")],
            [InlineKeyboardButton("صح/خطأ", callback_data="add_true_false")],
            [InlineKeyboardButton("رجوع", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("اختر نوع السؤال:", reply_markup=reply_markup)
    
    elif query.data in ["add_multiple", "add_true_false"]:
        context.user_data["question_type"] = "multiple_choice" if query.data == "add_multiple" else "true_false"
        context.user_data["state"] = STATE_ADD_QUESTION
        await query.edit_message_text("أرسل نص السؤال:")
    
    elif query.data == "view_questions":
        questions = load_questions()
        if not questions["multiple_choice"] and not questions["true_false"]:
            await query.edit_message_text("لا توجد أسئلة بعد.")
        else:
            text = "📋 قائمة الأسئلة:\n\n"
            for i, q in enumerate(questions["multiple_choice"], 1):
                text += f"{i}. ❓ {q['question']} (اختيار من متعدد)\n"
            for i, q in enumerate(questions["true_false"], 1):
                text += f"{i+len(questions['multiple_choice'])}. ❓ {q['question']} (صح/خطأ)\n"
            await query.edit_message_text(text[:4000])
    
    elif query.data == "start_test":
        questions = load_questions()
        all_questions = questions["multiple_choice"] + questions["true_false"]
        
        if not all_questions:
            await query.edit_message_text("لا توجد أسئلة متاحة للاختبار.")
            return
        
        # اختيار 5 أسئلة عشوائية
        import random
        test_questions = random.sample(all_questions, min(5, len(all_questions)))
        
        context.user_data["test_questions"] = test_questions
        context.user_data["current_question"] = 0
        context.user_data["score"] = 0
        context.user_data["answers"] = []
        
        await show_question(query, context)
    
    elif query.data.startswith("answer_"):
        # معالجة إجابة الطالب
        answer_index = int(query.data.split("_")[1])
        test_questions = context.user_data.get("test_questions", [])
        current_index = context.user_data.get("current_question", 0)
        
        if current_index < len(test_questions):
            question = test_questions[current_index]
            is_correct = False
            
            if question.get("type") == "multiple_choice":
                correct_option = question.get("correct_option", 0)
                is_correct = (answer_index == correct_option)
            else:  # true/false
                correct_answer = question.get("correct_answer", True)
                is_correct = (answer_index == 1 and correct_answer) or (answer_index == 0 and not correct_answer)
            
            context.user_data["answers"].append({
                "question": question["question"],
                "user_answer": answer_index,
                "correct": is_correct
            })
            
            if is_correct:
                context.user_data["score"] += 1
            
            # الانتقال للسؤال التالي
            context.user_data["current_question"] += 1
            current_index = context.user_data["current_question"]
            
            if current_index < len(test_questions):
                await show_question(query, context)
            else:
                # نهاية الاختبار
                await finish_test(query, context)
    
    elif query.data == "view_results":
        if user_id != context.bot_data.get("admin_id", ""):
            await query.edit_message_text("⛔ هذا الأمر للمعلم فقط!")
            return
        
        results = load_results()
        if not results:
            await query.edit_message_text("لا توجد نتائج بعد.")
        else:
            text = "📊 النتائج:\n\n"
            for student_id, student_results in results.items():
                student_name = student_results.get("name", "مجهول")
                text += f"👤 {student_name}:\n"
                for result in student_results.get("tests", []):
                    date = result.get("date", "غير معروف")
                    score = result.get("score", 0)
                    total = result.get("total", 1)
                    percentage = (score / total) * 100 if total > 0 else 0
                    text += f"   - {date}: {score}/{total} ({percentage:.1f}%)\n"
                text += "\n"
            await query.edit_message_text(text[:4000])
    
    elif query.data == "my_results":
        results = load_results()
        user_results = results.get(user_id, {})
        
        if not user_results.get("tests", []):
            await query.edit_message_text("لا توجد نتائج سابقة لك.")
        else:
            text = f"📊 نتائجك السابقة يا {user_results.get('name', query.from_user.first_name)}:\n\n"
            for result in user_results.get("tests", []):
                date = result.get("date", "غير معروف")
                score = result.get("score", 0)
                total = result.get("total", 1)
                percentage = (score / total) * 100 if total > 0 else 0
                text += f"📅 {date}: {score}/{total} ({percentage:.1f}%)\n"
            await query.edit_message_text(text)
    
    elif query.data == "back_to_main":
        await start_callback(update, context)

async def show_question(query, context):
    test_questions = context.user_data.get("test_questions", [])
    current_index = context.user_data.get("current_question", 0)
    
    if current_index >= len(test_questions):
        return
    
    question = test_questions[current_index]
    keyboard = []
    
    if question.get("type") == "multiple_choice":
        # سؤال اختيار من متعدد
        options = question.get("options", [])
        for i, option in enumerate(options):
            keyboard.append([InlineKeyboardButton(f"{i+1}. {option}", callback_data=f"answer_{i}")])
    else:
        # سؤال صح/خطأ
        keyboard = [
            [InlineKeyboardButton("✅ صح", callback_data="answer_1")],
            [InlineKeyboardButton("❌ خطأ", callback_data="answer_0")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    question_text = f"السؤال {current_index + 1}/{len(test_questions)}:\n\n{question['question']}"
    await query.edit_message_text(question_text, reply_markup=reply_markup)

async def finish_test(query, context):
    score = context.user_data.get("score", 0)
    total = len(context.user_data.get("test_questions", []))
    
    # حفظ النتائج
    results = load_results()
    user_id = str(query.from_user.id)
    
    if user_id not in results:
        results[user_id] = {
            "name": query.from_user.first_name,
            "tests": []
        }
    
    results[user_id]["tests"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score,
        "total": total,
        "percentage": (score / total) * 100 if total > 0 else 0
    })
    
    save_results(results)
    
    # عرض النتيجة
    percentage = (score / total) * 100 if total > 0 else 0
    result_text = f"🎉 انتهى الاختبار!\n\nنتيجتك: {score}/{total}\nالنسبة: {percentage:.1f}%\n\n"
    
    if percentage >= 80:
        result_text += "🌟 ممتاز! أحسنت!"
    elif percentage >= 60:
        result_text += "👍 جيد جداً!"
    elif percentage >= 50:
        result_text += "😊 مقبول، يمكنك التحسين!"
    else:
        result_text += "📚 تحتاج للمزيد من المذاكرة!"
    
    keyboard = [
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")],
        [InlineKeyboardButton("📊 نتائجي السابقة", callback_data="my_results")]
    ]
    
    if str(query.from_user.id) == context.bot_data.get("admin_id", ""):
        keyboard.append([InlineKeyboardButton("📋 إدارة الأسئلة", callback_data="add_question")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(result_text, reply_markup=reply_markup)

# معالجة الرسائل النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    state = context.user_data.get("state")
    
    if user_id != context.bot_data.get("admin_id", ""):
        await update.message.reply_text("أهلاً! استخدم /start لبدء الاختبار.")
        return
    
    if state == STATE_ADD_QUESTION:
        # حفظ نص السؤال
        context.user_data["question_text"] = update.message.text
        question_type = context.user_data.get("question_type")
        
        if question_type == "multiple_choice":
            context.user_data["state"] = STATE_ADD_OPTIONS
            context.user_data["options"] = []
            await update.message.reply_text("أرسل الخيار الأول (أرسل 'تم' عند الانتهاء):")
        else:  # true/false
            keyboard = [
                [InlineKeyboardButton("✅ صح", callback_data="set_true")],
                [InlineKeyboardButton("❌ خطأ", callback_data="set_false")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("اختر الإجابة الصحيحة:", reply_markup=reply_markup)
    
    elif state == STATE_ADD_OPTIONS:
        if update.message.text.lower() == "تم":
            if len(context.user_data["options"]) < 2:
                await update.message.reply_text("يجب إضافة خيارين على الأقل. أرسل الخيار الأول:")
                return
            
            # الانتقال لتعيين الإجابة الصحيحة
            context.user_data["state"] = STATE_ADD_CORRECT_ANSWER
            
            options_text = ""
            for i, option in enumerate(context.user_data["options"]):
                options_text += f"{i+1}. {option}\n"
            
            await update.message.reply_text(f"الخيارات:\n{options_text}\nأرسل رقم الإجابة الصحيحة (1-{len(context.user_data['options'])}):")
        else:
            context.user_data["options"].append(update.message.text)
            count = len(context.user_data["options"])
            await update.message.reply_text(f"تم إضافة الخيار {count}. أرسل الخيار التالي أو 'تم' عند الانتهاء:")
    
    elif state == STATE_ADD_CORRECT_ANSWER:
        try:
            correct_option = int(update.message.text) - 1
            options = context.user_data.get("options", [])
            
            if 0 <= correct_option < len(options):
                # حفظ السؤال
                questions = load_questions()
                
                new_question = {
                    "type": "multiple_choice",
                    "question": context.user_data.get("question_text", ""),
                    "options": options,
                    "correct_option": correct_option
                }
                
                questions["multiple_choice"].append(new_question)
                save_questions(questions)
                
                # إعادة الضبط
                context.user_data.clear()
                
                await update.message.reply_text("✅ تم حفظ السؤال بنجاح!")
                
                # العودة للقائمة الرئيسية
                keyboard = [
                    [InlineKeyboardButton("📝 إضافة سؤال جديد", callback_data="add_question")],
                    [InlineKeyboardButton("📋 عرض الأسئلة", callback_data="view_questions")],
                    [InlineKeyboardButton("🧪 بدء الاختبار", callback_data="start_test")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("اختر من القائمة:", reply_markup=reply_markup)
            else:
                await update.message.reply_text(f"الرجاء إدخال رقم بين 1 و {len(options)}:")
        except ValueError:
            await update.message.reply_text("الرجاء إدخال رقم صحيح:")

# معالجة تعيين الإجابة الصحيحة لسؤال صح/خطأ
async def set_true_false_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    correct_answer = (query.data == "set_true")
    
    # حفظ سؤال صح/خطأ
    questions = load_questions()
    
    new_question = {
        "type": "true_false",
        "question": context.user_data.get("question_text", ""),
        "correct_answer": correct_answer
    }
    
    questions["true_false"].append(new_question)
    save_questions(questions)
    
    # إعادة الضبط
    context.user_data.clear()
    
    await query.edit_message_text(f"✅ تم حفظ السؤال بنجاح! الإجابة الصحيحة: {'صح' if correct_answer else 'خطأ'}")
    
    # العودة للقائمة الرئيسية
    keyboard = [
        [InlineKeyboardButton("📝 إضافة سؤال جديد", callback_data="add_question")],
        [InlineKeyboardButton("📋 عرض الأسئلة", callback_data="view_questions")],
        [InlineKeyboardButton("🧪 بدء الاختبار", callback_data="start_test")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("اختر من القائمة:", reply_markup=reply_markup)

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    keyboard = []
    
    if str(user.id) == context.bot_data.get("admin_id", ""):
        keyboard = [
            [InlineKeyboardButton("📝 إضافة سؤال جديد", callback_data="add_question")],
            [InlineKeyboardButton("📋 عرض الأسئلة", callback_data="view_questions")],
            [InlineKeyboardButton("🧪 بدء الاختبار", callback_data="start_test")],
            [InlineKeyboardButton("📊 عرض النتائج", callback_data="view_results")]
        ]
        message = f"مرحباً أستاذ {user.first_name}! اختر من القائمة:"
    else:
        keyboard = [
            [InlineKeyboardButton("🧪 بدء الاختبار", callback_data="start_test")],
            [InlineKeyboardButton("📊 نتائجي السابقة", callback_data="my_results")]
        ]
        message = f"مرحباً {user.first_name}! اختر من القائمة:"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

def main():
    # الحصول على التوكن من متغير البيئة أو المدخلات
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("⚠️  لم يتم العثور على توكن البوت!")
        print("يرجى تعيين متغير البيئة TELEGRAM_BOT_TOKEN أو إدخال التوكن:")
        TOKEN = input("أدخل توكن بوت التليجرام: ").strip()
    
    # الحصول على معرف المعلم
    ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")
    
    if not ADMIN_ID:
        print("⚠️  لم يتم العثور على معرف المعلم!")
        print("يرجى تعيين متغير البيئة TELEGRAM_ADMIN_ID أو إدخال المعرف:")
        ADMIN_ID = input("أدخل معرف التليجرام للمعلم: ").strip()
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(TOKEN).build()
    
    # حفظ معرف المعلم
    application.bot_data["admin_id"] = ADMIN_ID
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(set_true_false_answer, pattern="^(set_true|set_false)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 البوت يعمل الآن...")
    print(f"👨‍🏫 معرف المعلم: {ADMIN_ID}")
    print("اضغط Ctrl+C لإيقاف البوت")
    
    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
