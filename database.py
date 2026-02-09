import sqlite3
import json

def init_db():
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_id TEXT NOT NULL,
        type TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        options TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def add_question(photo_id, q_type, correct_answer, options=None):
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    
    options_json = json.dumps(options) if options else None
    
    cursor.execute('''
    INSERT INTO questions (photo_id, type, correct_answer, options)
    VALUES (?, ?, ?, ?)
    ''', (photo_id, q_type, correct_answer, options_json))
    
    conn.commit()
    conn.close()

def get_random_question():
    conn = sqlite3.connect('questions.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM questions ORDER BY RANDOM() LIMIT 1')
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        question = dict(row)
        if question['options']:
            question['options'] = json.loads(question['options'])
        return question
    return None

# تهيئة قاعدة البيانات عند الاستيراد
init_db()
