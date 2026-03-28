import os
import sys
import psutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'school-class-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== БАЗА ДАННЫХ ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    role = db.Column(db.String(50), default='student')
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    teacher = db.Column(db.String(150), nullable=False)

class Homework(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    task = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.String(50), nullable=False)
    teacher = db.Column(db.String(150), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    lesson_num = db.Column(db.Integer, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    teacher = db.Column(db.String(150), nullable=False)
    room = db.Column(db.String(10), nullable=False)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=True)

class ServerLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(200), nullable=False)
    admin = db.Column(db.String(150), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== МОНИТОРИНГ СЕРВЕРА ====================

def get_server_stats():
    return {
        'cpu': psutil.cpu_percent(interval=1),
        'cpu_cores': psutil.cpu_count(),
        'ram_total': round(psutil.virtual_memory().total / (1024**3), 2),
        'ram_used': round(psutil.virtual_memory().used / (1024**3), 2),
        'ram_percent': psutil.virtual_memory().percent,
        'disk_total': round(psutil.disk_usage('/').total / (1024**3), 2),
        'disk_used': round(psutil.disk_usage('/').used / (1024**3), 2),
        'disk_percent': psutil.disk_usage('/').percent,
        'uptime': datetime.now().strftime('%H:%M:%S'),
        'pid': os.getpid(),
    }

# ==================== API ДЛЯ ЧАТА ====================

@app.route('/api/chat/messages')
def get_chat_messages():
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(50).all()
    return jsonify([{
        'id': m.id,
        'username': m.username,
        'message': m.message,
        'timestamp': m.timestamp.strftime('%H:%M:%S'),
        'is_online': m.is_online
    } for m in reversed(messages)])

@app.route('/api/chat/online')
def get_online_users():
    users = User.query.filter_by(is_online=True).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'full_name': u.full_name,
        'role': u.role,
        'last_seen': u.last_seen.strftime('%H:%M:%S')
    } for u in users])

# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    page = request.args.get('page', 'home')
    
    grades = []
    homework = []
    schedule = []
    server_stats = {}
    logs = []
    students = []
    all_users = []
    
    if current_user.is_authenticated:
        # Обновляем статус онлайн
        current_user.is_online = True
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Ученик видит только свои оценки
        if current_user.role == 'student':
            grades = Grade.query.filter_by(student=current_user.full_name).order_by(Grade.date.desc()).all()
        
        # Учитель и админ видят всё
        if current_user.role in ['admin', 'teacher']:
            grades = Grade.query.order_by(Grade.date.desc()).all()
            homework = Homework.query.order_by(Homework.date.desc()).all()
            schedule = Schedule.query.order_by(Schedule.day, Schedule.lesson_num).all()
            students = User.query.filter_by(role='student').all()
        
        # Админ видит сервер
        if current_user.role == 'admin':
            server_stats = get_server_stats()
            logs = ServerLog.query.order_by(ServerLog.date.desc()).limit(15).all()
        
        # Все видят список пользователей
        all_users = User.query.all()
    
    # Все видят ДЗ и расписание
    if not homework:
        homework = Homework.query.order_by(Homework.date.desc()).all()
    if not schedule:
        schedule = Schedule.query.order_by(Schedule.day, Schedule.lesson_num).all()
    
    return render_template('index.html',
                           page=page,
                           grades=grades,
                           homework=homework,
                           schedule=schedule,
                           server_stats=server_stats,
                           logs=logs,
                           students=students,
                           all_users=all_users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            session['role'] = user.role
            flash(f'✅ Добро пожаловать, {user.full_name}!', 'success')
            return redirect(url_for('index'))
        
        flash('❌ Неверный логин или пароль', 'danger')
    
    return redirect(url_for('index', page='login'))

@app.route('/logout')
@login_required
def logout():
    current_user.is_online = False
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    logout_user()
    session.clear()
    flash('👋 Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    message = request.form.get('message')
    if message:
        chat_msg = ChatMessage(
            user_id=current_user.id,
            username=current_user.full_name,
            message=message,
            is_online=current_user.is_online
        )
        db.session.add(chat_msg)
        db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/action', methods=['POST'])
@login_required
def action():
    action_type = request.form.get('action_type')
    
    # 📊 Оценки (учитель, админ)
    if action_type == 'grade':
        if current_user.role in ['admin', 'teacher']:
            student = request.form.get('student')
            subject = request.form.get('subject')
            grade = request.form.get('grade')
            if student and grade:
                db.session.add(Grade(
                    student=student,
                    subject=subject,
                    grade=int(grade),
                    teacher=current_user.full_name
                ))
    
    # 📚 Домашка (учитель, админ)
    elif action_type == 'homework':
        if current_user.role in ['admin', 'teacher']:
            subject = request.form.get('subject')
            task = request.form.get('task')
            deadline = request.form.get('deadline')
            if subject and task:
                db.session.add(Homework(
                    subject=subject,
                    task=task,
                    deadline=deadline,
                    teacher=current_user.full_name
                ))
    
    # 📅 Расписание (учитель, админ)
    elif action_type == 'schedule':
        if current_user.role in ['admin', 'teacher']:
            day = request.form.get('day')
            lesson_num = request.form.get('lesson_num')
            subject = request.form.get('subject')
            teacher = request.form.get('teacher')
            room = request.form.get('room')
            if day and subject:
                db.session.add(Schedule(
                    day=day,
                    lesson_num=int(lesson_num),
                    subject=subject,
                    teacher=teacher,
                    room=room
                ))
    
    # 🖥 ДЕЙСТВИЯ С СЕРВЕРОМ (только админ)
    elif action_type == 'server_restart':
        if current_user.role == 'admin':
            log = ServerLog(action='🔄 Перезапуск сервера', admin=current_user.username)
            db.session.add(log)
            db.session.commit()
            python = sys.executable
            os.execl(python, python, *sys.argv)
    
    elif action_type == 'server_stop':
        if current_user.role == 'admin':
            log = ServerLog(action='⏹ Остановка сервера', admin=current_user.username)
            db.session.add(log)
            db.session.commit()
            os._exit(0)
    
    elif action_type == 'server_clear_logs':
        if current_user.role == 'admin':
            log = ServerLog(action='🗑 Очистка логов', admin=current_user.username)
            db.session.add(log)
            ServerLog.query.delete()
            db.session.commit()
    
    elif action_type == 'server_clear_db':
        if current_user.role == 'admin':
            log = ServerLog(action='🗑 Очистка базы данных', admin=current_user.username)
            db.session.add(log)
            Grade.query.delete()
            Homework.query.delete()
            Schedule.query.delete()
            ChatMessage.query.delete()
            db.session.commit()
    
    db.session.commit()
    flash('✅ Действие выполнено', 'success')
    return redirect(request.referrer or url_for('index'))

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            # Создаём пользователей с почтами
            users = [
                # Админ и учитель
                User(username='admin', password=generate_password_hash('admin'), 
                     full_name='Администратор', email='admin@school.ru', role='admin'),
                User(username='elena', password=generate_password_hash('elena'), 
                     full_name='Елена Яковлевна', email='elena@school.ru', role='teacher'),
                
                # Ученики с почтами
                User(username='matvey', password=generate_password_hash('123'), 
                     full_name='Матвей', email='matvey@school.ru', role='student'),
                User(username='katya', password=generate_password_hash('123'), 
                     full_name='Катя', email='katya@school.ru', role='student'),
                User(username='misha', password=generate_password_hash('123'), 
                     full_name='Миша', email='misha@school.ru', role='student'),
                User(username='nastya', password=generate_password_hash('123'), 
                     full_name='Настя', email='nastya@school.ru', role='student'),
                User(username='ksyusha', password=generate_password_hash('123'), 
                     full_name='Ксюша', email='ksyusha@school.ru', role='student'),
                User(username='sasha', password=generate_password_hash('123'), 
                     full_name='Саша', email='sasha@school.ru', role='student'),
                User(username='vera', password=generate_password_hash('123'), 
                     full_name='Вера', email='vera@school.ru', role='student'),
                User(username='borya', password=generate_password_hash('123'), 
                     full_name='Боря', email='borya@school.ru', role='student'),
                User(username='svetik', password=generate_password_hash('123'), 
                     full_name='Светик', email='svetik@school.ru', role='student'),
                User(username='german', password=generate_password_hash('123'), 
                     full_name='Герман', email='german@school.ru', role='student'),
                User(username='pasha', password=generate_password_hash('123'), 
                     full_name='Паша', email='pasha@school.ru', role='student'),
                User(username='diana', password=generate_password_hash('123'), 
                     full_name='Диана', email='diana@school.ru', role='student'),
                User(username='feodor', password=generate_password_hash('123'), 
                     full_name='Феодор', email='feodor@school.ru', role='student'),
                User(username='angelina', password=generate_password_hash('123'), 
                     full_name='Ангелина', email='angelina@school.ru', role='student'),
                User(username='danya', password=generate_password_hash('123'), 
                     full_name='Даня', email='danya@school.ru', role='student'),
                User(username='elina', password=generate_password_hash('123'), 
                     full_name='Элина', email='elina@school.ru', role='student'),
                User(username='miron', password=generate_password_hash('123'), 
                     full_name='Мирон', email='miron@school.ru', role='student'),
                User(username='alie', password=generate_password_hash('123'), 
                     full_name='Алие', email='alie@school.ru', role='student'),
                User(username='anya', password=generate_password_hash('123'), 
                     full_name='Аня', email='anya@school.ru', role='student'),
                User(username='dasha', password=generate_password_hash('123'), 
                     full_name='Даша', email='dasha@school.ru', role='student'),
                User(username='deniz', password=generate_password_hash('123'), 
                     full_name='Дэниз', email='deniz@school.ru', role='student'),
                User(username='anton', password=generate_password_hash('123'), 
                     full_name='Антон', email='anton@school.ru', role='student'),
                User(username='alina', password=generate_password_hash('123'), 
                     full_name='Алина', email='alina@school.ru', role='student'),
            ]
            
            for u in users:
                db.session.add(u)
            
            # Тестовое расписание
            db.session.add(Schedule(day='Понедельник', lesson_num=1, subject='Алгебра', 
                                   teacher='Елена Яковлевна', room='305'))
            db.session.add(Schedule(day='Понедельник', lesson_num=2, subject='Русский язык', 
                                   teacher='Мария Петровна', room='301'))
            db.session.add(Schedule(day='Вторник', lesson_num=1, subject='Физика', 
                                   teacher='Игорь Сергеевич', room='210'))
            
            # Тестовая домашка
            db.session.add(Homework(subject='Алгебра', task='Стр. 45 №123, 124', 
                                   deadline='25.10', teacher='Елена Яковлевна'))
            db.session.add(Homework(subject='Русский язык', task='Упражнение 56', 
                                   deadline='26.10', teacher='Мария Петровна'))
            
            # Тестовые оценки
            db.session.add(Grade(student='Матвей', subject='Алгебра', grade=5, 
                                teacher='Елена Яковлевна'))
            db.session.add(Grade(student='Катя', subject='Русский язык', grade=4, 
                                teacher='Мария Петровна'))
            db.session.add(Grade(student='Миша', subject='Алгебра', grade=3, 
                                teacher='Елена Яковлевна'))
            
            # Тестовые сообщения в чат
            db.session.add(ChatMessage(user_id=1, username='Администратор', 
                                       message='Всем привет! Добро пожаловать в чат класса! 🎉'))
            db.session.add(ChatMessage(user_id=2, username='Елена Яковлевна', 
                                       message='Не забывайте делать домашнее задание! 📚'))
            
            db.session.commit()
            
            print("\n" + "="*60)
            print("✅ БАЗА ДАННЫХ СОЗДАНА!")
            print("="*60)
            print("🔧 АДМИН:   admin / admin")
            print("👩‍🏫 УЧИТЕЛЬ: elena / elena")
            print("="*60)
            print("🎓 УЧЕНИКИ (пароль 123):")
            print("  matvey, katya, misha, nastya, ksyusha, sasha,")
            print("  vera, borya, svetik, german, pasha, diana,")
            print("  feodor, angelina, danya, elina, miron, alie,")
            print("  anya, dasha, deniz, anton, alina")
            print("="*60)
            print("\n🚀 Сервер запущен: http://127.0.0.1:5000")
            print("⏹  Для остановки: Ctrl+C\n")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000, host='0.0.0.0')