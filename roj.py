from flask import Flask, render_template_string, request, redirect, url_for, session
from datetime import datetime, date, timedelta
import json
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'yfhs_secret_key_2026'
DATA_FILE = Path(__file__).with_name("church_leaders.json")
APP_DATA_FILE = Path(__file__).with_name("app_data.json")
PERSIST_KEYS = ["schedules", "attendance", "attendance_drafts", "announcements", "church_leaders", "chat_messages"]


def load_church_leaders():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_church_leaders(leaders):
    DATA_FILE.write_text(json.dumps(leaders, ensure_ascii=True, indent=2), encoding="utf-8")


def load_runtime_store():
    if not APP_DATA_FILE.exists():
        return {}
    try:
        loaded = json.loads(APP_DATA_FILE.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_runtime_store(payload):
    APP_DATA_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def persist_runtime_data():
    payload = {}
    for key in PERSIST_KEYS:
        payload[key] = session.get(key, {} if key == "attendance_drafts" else [])
    save_runtime_store(payload)
    session.modified = True


def parse_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def get_third_sunday(year, month):
    first_day = date(year, month, 1)
    days_until_sunday = (6 - first_day.weekday()) % 7
    first_sunday = first_day + timedelta(days=days_until_sunday)
    return first_sunday + timedelta(days=14)


def html_escape(value):
    text = str(value if value is not None else "")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def get_upcoming_fellowship_date():
    today = date.today()
    this_month_third = get_third_sunday(today.year, today.month)
    if this_month_third >= today:
        return this_month_third.strftime("%Y-%m-%d")
    next_month = today.month + 1
    next_year = today.year + (1 if next_month > 12 else 0)
    next_month = 1 if next_month > 12 else next_month
    return get_third_sunday(next_year, next_month).strftime("%Y-%m-%d")


def get_next_fellowship_date(from_fellowship_date):
    try:
        base = datetime.strptime(from_fellowship_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return get_upcoming_fellowship_date()
    next_month = base.month + 1
    next_year = base.year + (1 if next_month > 12 else 0)
    next_month = 1 if next_month > 12 else next_month
    return get_third_sunday(next_year, next_month).strftime("%Y-%m-%d")


def normalize_draft_groups(raw_drafts):
    if not isinstance(raw_drafts, list):
        return []
    if raw_drafts and isinstance(raw_drafts[0], dict) and "members" in raw_drafts[0]:
        return raw_drafts
    # Backward compatibility: old flat member list -> one active group
    return [{
        "fellowship_date": get_upcoming_fellowship_date(),
        "submitted": False,
        "submitted_at": "",
        "members": raw_drafts
    }]


def init_session_data():
    runtime_data = load_runtime_store()
    default_data = {
        'page': 'landing',
        'username': None,
        'admin_logged_in': False,
        'leader_logged_in': False,
        'leader_profile': None,
        'schedules': [
            {"id": 1, "date": "2026-01-18", "time": "10:00", "location": "Church Main Hall", "status": "upcoming"},
            {"id": 2, "date": "2026-02-15", "time": "10:00", "location": "Youth Center", "status": "upcoming"}
        ],
        'attendance': [],
        'attendance_drafts': {},
        'announcements': [],
        'church_leaders': [],
        'chat_messages': []
    }
    for key, value in default_data.items():
        if key not in session:
            session[key] = value
    for key in PERSIST_KEYS:
        if key in runtime_data:
            session[key] = runtime_data.get(key)
    existing_announcements = session.get('announcements', [])
    demo_titles = {"Next Fellowship Prep", "Attendance Reminder"}
    if existing_announcements and all(a.get("title") in demo_titles for a in existing_announcements):
        session['announcements'] = []
    session['attendance'] = [a for a in session.get('attendance', []) if a.get('full_name')]
    if not session.get('church_leaders'):
        session['church_leaders'] = load_church_leaders()


STYLE = """
* { margin: 0; padding: 0; box-sizing: border-box; scroll-behavior: smooth; }
body {
    font-family: "Poppins", sans-serif;
    line-height: 1.6;
    color: white;
    background: linear-gradient(rgba(15,32,39,0.85), rgba(44,83,100,0.85)),
                url("https://images.unsplash.com/photo-1578662996442-48f60103fc96?ixlib=rb-4.0.3&auto=format&fit=crop&w=2070&q=80")
                center/cover no-repeat fixed;
    overflow-x: hidden;
    min-height: 100vh;
}

nav.top-nav {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    background: rgba(15,32,39,0.95);
    backdrop-filter: blur(10px);
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    z-index: 1000;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
nav.top-nav h1 { font-size: 1.5rem; letter-spacing: 2px; color: #4fc3f7; }
nav.top-nav ul { list-style: none; display: flex; gap: 2rem; align-items: center; }
nav.top-nav ul li a {
    color: white; text-decoration: none;
    font-weight: 500; padding: 0.5rem 1rem;
    border-radius: 25px; transition: all 0.3s;
}
nav.top-nav ul li a:hover { background: rgba(79,195,247,0.2); color: #4fc3f7; }

section {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 8rem 10% 4rem;
}
section h2 {
    font-size: 2.5rem;
    margin-bottom: 1.5rem;
    background: linear-gradient(45deg, #4fc3f7, #81d4fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
}
section p {
    max-width: 900px;
    font-size: 1.2rem;
    color: #f1f8ff;
    margin-bottom: 1rem;
    line-height: 1.8;
}

.btn {
    display: inline-block;
    padding: 1rem 2.5rem;
    background: linear-gradient(45deg, #4fc3f7, #81d4fa);
    color: white;
    border-radius: 30px;
    text-decoration: none;
    font-weight: 600;
    font-size: 1.1rem;
    transition: all 0.3s;
    box-shadow: 0 8px 25px rgba(79,195,247,0.4);
    margin: 1rem;
    border: none;
    cursor: pointer;
}
.btn:hover { transform: translateY(-3px); box-shadow: 0 12px 35px rgba(79,195,247,0.6); }
.btn-danger { background: linear-gradient(45deg, #f44336, #ef5350); }

.services {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 2.5rem;
    margin-top: 4rem;
    width: 100%;
}
.card {
    background: rgba(255,255,255,0.12);
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    padding: 2.5rem 2rem;
    backdrop-filter: blur(15px);
    border: 1px solid rgba(79,195,247,0.3);
    transition: all 0.4s;
}
.card:hover { transform: translateY(-12px); background: rgba(79,195,247,0.15); }
.card h3 { color: #4fc3f7; margin-bottom: 1rem; font-size: 1.4rem; }
.card i { font-size: 3rem; color: #4fc3f7; margin-bottom: 1rem; display: block; }

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
    margin-top: 3rem;
    width: 100%;
}
.stat-card {
    background: rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 2.5rem 2rem;
    backdrop-filter: blur(15px);
    border-left: 5px solid #4fc3f7;
    text-align: center;
    transition: all 0.3s;
}
.stat-card:hover { transform: translateY(-5px); }
.stat-card h3 { font-size: 2.5rem; color: #4fc3f7; margin-bottom: 0.5rem; }
.stat-card p { color: #f1f8ff; font-size: 1.1rem; }

footer {
    text-align: center;
    padding: 2rem;
    background: rgba(15,32,39,0.95);
    color: #b3d9ff;
    font-size: 1rem;
}

.admin-nav {
    position: fixed;
    top: 0;
    left: 0;
    width: 280px;
    height: 100vh;
    background: rgba(15,32,39,0.95);
    backdrop-filter: blur(10px);
    color: white;
    padding: 1.5rem 1rem;
    z-index: 1000;
    box-shadow: 4px 0 20px rgba(0,0,0,0.5);
    overflow-y: auto;
}
.admin-nav h1 { font-size: 1.5rem; letter-spacing: 2px; color: #4fc3f7; margin-bottom: 2rem; }
.admin-nav ul { list-style: none; display: flex; flex-direction: column; gap: 0.8rem; margin: 0; padding: 0; }
.admin-nav ul li { width: 100%; }
.admin-nav ul li a {
    color: white;
    text-decoration: none;
    font-weight: 500;
    padding: 0.9rem 1rem;
    border-radius: 12px;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.admin-nav ul li a:hover, .admin-nav ul li a.active {
    background: rgba(79,195,247,0.2);
    color: #4fc3f7;
}

.content-wrapper {
    margin-left: 280px;
    padding: 2rem;
    min-height: 100vh;
    width: calc(100% - 280px);
}

.dashboard-section {
    display: none;
    min-height: 80vh;
    padding: 2rem 0;
}
.dashboard-section.active { display: block; }

table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
th { background: rgba(79,195,247,0.2); color: #4fc3f7; font-weight: 600; }
tr:hover { background: rgba(79,195,247,0.1); }

.form-group { margin-bottom: 1.5rem; }
.form-group label { display: block; margin-bottom: 0.5rem; color: #f1f8ff; }
.form-group input, .form-group textarea, .form-group select {
    width: 100%;
    padding: 1rem;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.3);
    background: rgba(255,255,255,0.1);
    color: white;
    backdrop-filter: blur(10px);
    font-size: 1rem;
}
.form-group input::placeholder, .form-group textarea::placeholder { color: rgba(255,255,255,0.7); }

@media (max-width: 768px) {
    nav.top-nav {
        flex-direction: column;
        gap: 1rem;
        padding: 1rem;
    }

    nav.top-nav ul {
        flex-wrap: wrap;
        justify-content: center;
        gap: 0.8rem;
    }

    .admin-nav {
        width: 100%;
        height: auto;
        position: relative;
        box-shadow: none;
    }

    .content-wrapper {
        margin-left: 0;
        width: 100%;
        padding: 1.5rem;
    }

    section {
        padding: 7rem 5% 4rem;
    }

    section h2 {
        font-size: 2rem;
    }
}
"""


@app.route('/')
def landing():
    init_session_data()
    session['page'] = 'landing'
    return render_template_string(f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>✝️ YFHS | Youth Fellowship Hosting Scheduler</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>{STYLE}</style>
</head>
<body>
<nav class="top-nav">
    <h1>✝️ YFHS</h1>
    <ul>
        <li><a href="#home">Home</a></li>
        <li><a href="#about">About</a></li>
        <li><a href="#features">Features</a></li>
        <li><a href="#objectives">Objectives</a></li>
        <li><a href="#contact">Contact</a></li>
        <li><a href="/login" class="btn" style="padding: 0.5rem 1.5rem; font-size: 1rem; margin: 0;">🔐 Login</a></li>
    </ul>
</nav>

<section id="home">
    <h2>Youth Fellowship Hosting Scheduler</h2>
    <p>YFHS is a web-based platform designed to streamline youth fellowship scheduling, attendance tracking, announcements, and real-time communication at <strong>Jesus Christ Global Life Changing and Healing Ministry</strong>.</p>
    <p>AI-powered automation meets spiritual community management.</p>
    <a href="/login" class="btn">🚀 Start Managing</a>
    <a href="#features" class="btn">✨ Explore Features</a>
</section>

<section id="about">
    <h2>About the Project</h2>
    <p>YFHS was developed to solve the challenges of manual fellowship scheduling, scattered attendance records, and lack of centralized communication in youth ministry.</p>
    <p>Our AI-powered system automatically schedules every 3rd Sunday, tracks attendance in real-time, broadcasts announcements instantly, and provides comprehensive analytics for church leaders and administrators.</p>
    <a href="#features" class="btn">See System Features</a>
</section>

<section id="features">
    <h2>✨ System Features</h2>
    <div class="services">
        <div class="card"><i class="fas fa-robot"></i><h3>🤖 AI Scheduling</h3><p>Automatically schedules youth fellowships every 3rd Sunday of the month with one click.</p></div>
        <div class="card"><i class="fas fa-calendar-check"></i><h3>📅 Smart Calendar</h3><p>Complete schedule management with manual overrides and real-time updates.</p></div>
        <div class="card"><i class="fas fa-users"></i><h3>👥 Attendance Tracking</h3><p>Leaders submit attendance instantly - track youth participation effortlessly.</p></div>
        <div class="card"><i class="fas fa-bullhorn"></i><h3>📢 Instant Announcements</h3><p>Broadcast important updates to all leaders and youth instantly.</p></div>
        <div class="card"><i class="fas fa-comments"></i><h3>💬 Real-time Chat</h3><p>Direct communication between admin and church leaders for quick coordination.</p></div>
        <div class="card"><i class="fas fa-chart-line"></i><h3>📈 Analytics Dashboard</h3><p>Comprehensive reports on attendance trends, participation rates, and performance metrics.</p></div>
    </div>
</section>

<section id="objectives">
    <h2>🎯 Objectives</h2>
    <p>The main objective is to develop an AI-powered web application that automates youth fellowship scheduling, centralizes attendance records, enables instant communication, and provides actionable analytics for church leadership.</p>
    <div class="stats-grid">
        <div class="stat-card"><h3>100% Automated</h3><p>AI schedules every fellowship</p></div>
        <div class="stat-card"><h3>Real-time Data</h3><p>Live attendance & communication</p></div>
        <div class="stat-card"><h3>Complete Control</h3><p>Admin dashboard for all functions</p></div>
    </div>
</section>

<section id="contact">
    <h2>📞 Contact Information</h2>
    <p><strong>Jesus Christ Global Life Changing and Healing Ministry</strong></p>
    <p>Libungan, Soccsksargen, Philippines</p>
    <p>This system serves church leaders, youth ministry coordinators, and administrators in organizing impactful fellowship gatherings.</p>
    <a href="/login" class="btn">👑 Admin Login</a>
</section>

<footer>
    &copy; 2026 YFHS | Youth Fellowship Hosting Scheduler | Jesus Christ Global Ministry
</footer>
</body>
</html>
    """)


@app.route('/login', methods=['GET', 'POST'])
def login():
    init_session_data()
    error = False

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['leader_logged_in'] = False
            session['leader_profile'] = None
            session['username'] = username
            return redirect(url_for('admin'))

        leaders = session.get('church_leaders', [])
        matched_leader = next(
            (
                leader for leader in leaders
                if leader.get('username', '').strip() == username
                and leader.get('password', '').strip() == password
            ),
            None
        )
        if matched_leader:
            session['admin_logged_in'] = False
            session['leader_logged_in'] = True
            session['leader_profile'] = matched_leader
            session['username'] = matched_leader.get('full_name', username)
            return redirect(url_for('leader_dashboard'))

        error = True

    login_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YFHS Login</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
{STYLE}
body {{
    background: linear-gradient(-45deg, #1565c0, #1976d2, #42a5f5, #64b5f6);
    background-size: 400% 400%;
    animation: gradientShift 15s ease infinite;
    min-height: 100vh;
}}
@keyframes gradientShift {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
.login-container {{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 100%;
    max-width: 450px;
    z-index: 1001;
}}
.login-card {{
    background: rgba(255,255,255,0.15);
    backdrop-filter: blur(25px);
    border-radius: 25px;
    border: 1px solid rgba(255,255,255,0.25);
    padding: 3rem 2.5rem;
    box-shadow: 0 25px 45px rgba(0,0,0,0.3);
}}
input {{
    width: 100%;
    padding: 1.2rem;
    margin-bottom: 1.5rem;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.4);
    background: rgba(255,255,255,0.1);
    color: white;
    font-size: 1rem;
    backdrop-filter: blur(10px);
}}
input::placeholder {{ color: rgba(255,255,255,0.7); }}
nav.top-nav {{
    position: relative;
    width: 100%;
    justify-content: flex-start;
}}
</style>
</head>
<body>
<nav class="top-nav">
    <h1 style="color: white;">✝️ YFHS Login</h1>
</nav>
<div class="login-container">
    <div class="login-card">
        <div style="text-align: center; margin-bottom: 2rem;">
            <i class="fas fa-church" style="font-size: 4rem; color: white;"></i>
        </div>
        <h2 style="color: white; font-weight: 700; margin-bottom: 1.5rem;">Youth Fellowship Login</h2>
        <p style="color: rgba(255,255,255,0.9); margin-bottom: 2rem;">Jesus Christ Global Ministry</p>
    """

    if error:
        login_template += """
        <div style="background: rgba(255,102,102,0.3); border: 1px solid rgba(255,102,102,0.5); border-radius: 12px; color: #ff6666; padding: 1rem; margin-bottom: 1.5rem;">
            ❌ Invalid credentials!
        </div>
        """

    login_template += """
        <form method="POST">
            <input type="text" name="username" placeholder="👤 Username (admin o church leader)" required>
            <input type="password" name="password" placeholder="🔑 Password" required>
            <button type="submit" class="btn" style="width: 100%; padding: 1.2rem; font-size: 1.1rem;">🚀 Enter Dashboard</button>
        </form>

        <div style="text-align: center; margin-top: 2rem; color: rgba(255,255,255,0.8); font-size: 0.95rem;">
            <p><strong>🔑 Demo Credentials:</strong><br>Admin: admin / admin123<br>Church Leader: use registered leader username/password</p>
        </div>
    </div>
</div>
</body>
</html>
    """
    return render_template_string(login_template)


@app.route('/register_leader', methods=['POST'])
def register_leader():
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    leaders = session.get('church_leaders', [])
    leader_data = {
        "id": len(leaders) + 1,
        "full_name": request.form.get('fullname', '').strip(),
        "church": request.form.get('church', '').strip(),
        "address": request.form.get('address', '').strip(),
        "current_youths": parse_int(request.form.get('current_youths', '0').strip(), 0),
        "age": request.form.get('age', '').strip(),
        "username": request.form.get('username', '').strip(),
        "password": request.form.get('password', '').strip(),
        "gender": request.form.get('grader', '').strip(),
        "registered_date": datetime.now().strftime('%Y-%m-%d %H:%M')
    }

    required_fields = ["full_name", "church", "address", "age", "username", "password", "gender"]
    if any(not leader_data[field] for field in required_fields):
        return redirect(url_for('admin'))

    leaders.append(leader_data)
    save_church_leaders(leaders)
    session['church_leaders'] = leaders
    persist_runtime_data()
    return redirect(url_for('admin'))


@app.route('/admin/send_message', methods=['POST'])
def admin_send_message():
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    target_username = request.form.get('target_username', '').strip()
    message = request.form.get('message', '').strip()
    if target_username and message:
        chat_messages = session.get('chat_messages', [])
        chat_messages.append({
            "sender_role": "admin",
            "sender_name": session.get('username', 'Admin'),
            "target_username": target_username,
            "message": message,
            "sent_at": datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        session['chat_messages'] = chat_messages
        persist_runtime_data()
    return redirect(url_for('admin', section='communicate_leader', chat_user=target_username))


@app.route('/leader/send_message', methods=['POST'])
def leader_send_message():
    init_session_data()
    if not session.get('leader_logged_in'):
        return redirect(url_for('login'))

    message = request.form.get('message', '').strip()
    leader = session.get('leader_profile') or {}
    username = leader.get('username', '').strip()
    if username and message:
        chat_messages = session.get('chat_messages', [])
        chat_messages.append({
            "sender_role": "leader",
            "sender_name": leader.get('full_name', username),
            "target_username": username,
            "message": message,
            "sent_at": datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        session['chat_messages'] = chat_messages
        persist_runtime_data()
    return redirect(url_for('leader_dashboard'))


@app.route('/leader/submit_attendance', methods=['POST'])
def leader_submit_attendance():
    init_session_data()
    if not session.get('leader_logged_in'):
        return redirect(url_for('login'))

    leader = session.get('leader_profile') or {}
    username = leader.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip()
    age = request.form.get('age', '').strip()
    allergies = request.form.get('allergies', '').strip()
    if username and full_name and age and allergies:
        drafts = session.get('attendance_drafts', {})
        leader_groups = normalize_draft_groups(drafts.get(username, []))
        if not leader_groups:
            leader_groups = [{
                "fellowship_date": get_upcoming_fellowship_date(),
                "submitted": False,
                "submitted_at": "",
                "members": []
            }]
        active_group = leader_groups[-1]
        next_id = max((a.get("id", 0) for a in active_group.get("members", [])), default=0) + 1
        active_group.setdefault("members", []).append({
            "id": next_id,
            "full_name": full_name,
            "age": age,
            "allergies": allergies
        })
        drafts[username] = leader_groups
        session['attendance_drafts'] = drafts
        persist_runtime_data()
    return redirect(url_for('leader_dashboard', section='leader_submit'))


@app.route('/leader/update_attendance/<int:attendance_id>', methods=['POST'])
def leader_update_attendance(attendance_id):
    init_session_data()
    if not session.get('leader_logged_in'):
        return redirect(url_for('login'))

    leader = session.get('leader_profile') or {}
    current_username = leader.get('username', '')
    full_name = request.form.get('full_name', '').strip()
    age = request.form.get('age', '').strip()
    allergies = request.form.get('allergies', '').strip()
    group_index = parse_int(request.form.get("group_index", "0"), 0)
    drafts = session.get('attendance_drafts', {})
    leader_groups = normalize_draft_groups(drafts.get(current_username, []))
    if 0 <= group_index < len(leader_groups):
        members = leader_groups[group_index].get("members", [])
        for item in members:
            if item.get("id") == attendance_id:
                if full_name and age and allergies:
                    item["full_name"] = full_name
                    item["age"] = age
                    item["allergies"] = allergies
                break
        leader_groups[group_index]["members"] = members

    drafts[current_username] = leader_groups
    session['attendance_drafts'] = drafts
    persist_runtime_data()
    return redirect(url_for('leader_dashboard', section='leader_submit'))


@app.route('/leader/delete_attendance/<int:attendance_id>', methods=['POST'])
def leader_delete_attendance(attendance_id):
    init_session_data()
    if not session.get('leader_logged_in'):
        return redirect(url_for('login'))

    leader = session.get('leader_profile') or {}
    current_username = leader.get('username', '')
    group_index = parse_int(request.form.get("group_index", "0"), 0)
    drafts = session.get('attendance_drafts', {})
    leader_groups = normalize_draft_groups(drafts.get(current_username, []))
    if 0 <= group_index < len(leader_groups):
        members = leader_groups[group_index].get("members", [])
        leader_groups[group_index]["members"] = [a for a in members if a.get("id") != attendance_id]
    drafts[current_username] = leader_groups
    session['attendance_drafts'] = drafts
    persist_runtime_data()
    return redirect(url_for('leader_dashboard', section='leader_submit'))


@app.route('/leader/finalize_attendance', methods=['POST'])
def leader_finalize_attendance():
    init_session_data()
    if not session.get('leader_logged_in'):
        return redirect(url_for('login'))

    leader = session.get('leader_profile') or {}
    username = leader.get('username', '').strip()
    if not username:
        return redirect(url_for('leader_dashboard', section='leader_submit'))

    drafts = session.get('attendance_drafts', {})
    leader_groups = normalize_draft_groups(drafts.get(username, []))
    if not leader_groups:
        return redirect(url_for('leader_dashboard', section='leader_submit'))

    active_group = leader_groups[-1]
    leader_drafts = active_group.get("members", [])
    if leader_drafts and not active_group.get("submitted", False):
        attendance = session.get('attendance', [])
        next_id = max((a.get("id", 0) for a in attendance), default=0) + 1
        submission_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        batch_id = f"{username}-{active_group.get('fellowship_date', get_upcoming_fellowship_date())}-{submission_time}"
        for row in leader_drafts:
            attendance.append({
                "id": next_id,
                "leader": leader.get('full_name', username),
                "church": leader.get('church', 'N/A'),
                "full_name": row.get("full_name", ""),
                "age": row.get("age", ""),
                "allergies": row.get("allergies", ""),
                "date": active_group.get("fellowship_date", get_upcoming_fellowship_date()),
                "submitted": submission_time,
                "submitted_by": username,
                "batch_id": batch_id
            })
            next_id += 1
        active_group["submitted"] = True
        active_group["submitted_at"] = submission_time
        leader_groups[-1] = active_group
        leader_groups.append({
            "fellowship_date": get_next_fellowship_date(active_group.get("fellowship_date", "")),
            "submitted": False,
            "submitted_at": "",
            "members": []
        })
        drafts[username] = leader_groups
        session['attendance'] = attendance
        session['attendance_drafts'] = drafts
    persist_runtime_data()
    return redirect(url_for('leader_dashboard', section='leader_submit'))


@app.route('/admin/create_announcement', methods=['POST'])
def admin_create_announcement():
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    title = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    if title and message:
        announcements = session.get('announcements', [])
        next_id = max((a.get('id', 0) for a in announcements), default=0) + 1
        announcements.append({
            "id": next_id,
            "title": title,
            "message": message,
            "date": datetime.now().strftime('%Y-%m-%d')
        })
        session['announcements'] = announcements
        persist_runtime_data()
    return redirect(url_for('admin', section='announcements'))


@app.route('/admin/update_announcement/<int:announcement_id>', methods=['POST'])
def admin_update_announcement(announcement_id):
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    title = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    announcements = session.get('announcements', [])
    for announcement in announcements:
        if announcement.get("id") == announcement_id and title and message:
            announcement["title"] = title
            announcement["message"] = message
            announcement["date"] = datetime.now().strftime('%Y-%m-%d')
            break
    session['announcements'] = announcements
    persist_runtime_data()
    return redirect(url_for('admin', section='announcements'))


@app.route('/admin/delete_announcement/<int:announcement_id>', methods=['POST'])
def admin_delete_announcement(announcement_id):
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    announcements = [a for a in session.get('announcements', []) if a.get("id") != announcement_id]
    for idx, ann in enumerate(announcements, start=1):
        ann["id"] = idx
    session['announcements'] = announcements
    persist_runtime_data()
    return redirect(url_for('admin', section='announcements'))


@app.route('/admin/generate_ai_calendar', methods=['POST'])
def admin_generate_ai_calendar():
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    schedules = session.get('schedules', [])
    today = date.today()

    parsed_schedule_dates = []
    for sched in schedules:
        try:
            parsed_schedule_dates.append(datetime.strptime(sched.get("date", ""), "%Y-%m-%d").date())
        except (TypeError, ValueError):
            continue

    if parsed_schedule_dates:
        latest_saved_date = max(parsed_schedule_dates)
        latest_saved_month_anchor = date(latest_saved_date.year, latest_saved_date.month, 1)
        today_month_anchor = date(today.year, today.month, 1)
        base = latest_saved_month_anchor if latest_saved_month_anchor > today_month_anchor else today_month_anchor
        base_year, base_month = base.year, base.month
    else:
        base_year, base_month = today.year, today.month

    next_month = base_month + 1
    next_year = base_year + (1 if next_month > 12 else 0)
    next_month = 1 if next_month > 12 else next_month

    next_third_sunday = get_third_sunday(next_year, next_month)
    schedule_date = next_third_sunday.strftime('%Y-%m-%d')

    schedules.append({
        "id": len(schedules) + 1,
        "date": schedule_date,
        "time": "10:00",
        "location": "Church Main Hall",
        "status": "upcoming"
    })
    schedules = sorted(schedules, key=lambda x: x.get("date", "9999-99-99"))
    for idx, sched in enumerate(schedules, start=1):
        sched["id"] = idx

    session['schedules'] = schedules
    persist_runtime_data()
    return redirect(url_for(
        'admin',
        section='announcements',
        generated_date=schedule_date,
        generated_title=f"Youth Fellowship Schedule - {schedule_date}"
    ))


@app.route('/update_leader/<int:leader_id>', methods=['POST'])
def update_leader(leader_id):
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    leaders = session.get('church_leaders', [])
    for leader in leaders:
        if leader.get("id") == leader_id:
            leader["full_name"] = request.form.get('fullname', '').strip()
            leader["church"] = request.form.get('church', '').strip()
            leader["address"] = request.form.get('address', '').strip()
            leader["current_youths"] = parse_int(request.form.get('current_youths', '0').strip(), 0)
            leader["age"] = request.form.get('age', '').strip()
            leader["username"] = request.form.get('username', '').strip()
            leader["password"] = request.form.get('password', '').strip()
            leader["gender"] = request.form.get('grader', '').strip()
            break

    save_church_leaders(leaders)
    session['church_leaders'] = leaders
    persist_runtime_data()
    return redirect(url_for('admin', section='register_leader'))


@app.route('/delete_leader/<int:leader_id>', methods=['POST'])
def delete_leader(leader_id):
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    leaders = session.get('church_leaders', [])
    leaders = [l for l in leaders if l.get("id") != leader_id]

    for index, leader in enumerate(leaders, start=1):
        leader["id"] = index

    save_church_leaders(leaders)
    session['church_leaders'] = leaders
    persist_runtime_data()
    return redirect(url_for('admin'))


@app.route('/admin')
def admin():
    init_session_data()
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    username = session.get('username', 'Admin')
    schedules = session.get('schedules', [])
    attendance = session.get('attendance', [])
    announcements = session.get('announcements', [])
    leaders = session.get('church_leaders', [])
    chat_messages = session.get('chat_messages', [])

    # Count total youths per church for dashboard graph
    church_counts = {}
    for l in leaders:
        church = l.get("church", "").strip() or "No Church"
        church_counts[church] = church_counts.get(church, 0) + parse_int(l.get("current_youths", 0), 0)
    churches = list(church_counts.keys())
    counts = list(church_counts.values())
    max_count = max(counts) if counts else 1
    bar_divisor = max_count if max_count > 0 else 1
    total_youth = sum(parse_int(l.get("current_youths", 0), 0) for l in leaders)
    leaders_for_chat = sorted(leaders, key=lambda x: x.get("full_name", "").lower())
    selected_chat_username = request.args.get('chat_user', '').strip()
    chat_user_requested = bool(selected_chat_username)
    if not any(l.get("username") == selected_chat_username for l in leaders_for_chat):
        selected_chat_username = leaders_for_chat[0].get("username", "") if leaders_for_chat else ""
    selected_chat_name = next(
        (l.get("full_name", l.get("username", "Leader")) for l in leaders_for_chat if l.get("username") == selected_chat_username),
        "Leader"
    )
    conversation = [
        m for m in chat_messages
        if m.get("target_username", "").strip() == selected_chat_username
    ] if selected_chat_username else []
    selected_section = request.args.get('section', 'register_leader').strip()
    generated_date = request.args.get('generated_date', '').strip()
    generated_title = request.args.get('generated_title', '').strip()
    generated_message = "Announcement" if generated_date else ""
    safe_generated_title = html_escape(generated_title)
    safe_generated_message = html_escape(generated_message)
    edit_announcement_id = parse_int(request.args.get('edit_announcement_id', ''), 0)
    announcement_to_edit = next((a for a in announcements if a.get("id") == edit_announcement_id), None)
    announcement_form_action = (
        f"/admin/update_announcement/{edit_announcement_id}" if announcement_to_edit else "/admin/create_announcement"
    )
    announcement_form_title = html_escape(announcement_to_edit.get("title", "") if announcement_to_edit else generated_title)
    announcement_form_message = html_escape(announcement_to_edit.get("message", "") if announcement_to_edit else generated_message)
    edit_leader_id = parse_int(request.args.get('edit_leader_id', ''), 0)
    leader_to_edit = next((l for l in leaders if l.get("id") == edit_leader_id), None)
    leader_form_action = f"/update_leader/{edit_leader_id}" if leader_to_edit else "/register_leader"
    valid_sections = {"dashboard", "announcements", "register_leader", "communicate_leader", "export_report"}
    selected_export_date = request.args.get('export_date', '').strip()
    selected_export_leader = request.args.get('export_leader', '').strip()
    registered_leader_names = sorted({l.get("full_name", "").strip() for l in leaders if l.get("full_name", "").strip()})
    member_attendance = [
        a for a in attendance
        if a.get("full_name", "").strip()
        and a.get("leader", "").strip() in registered_leader_names
    ]
    available_export_dates = sorted({a.get("date", "") for a in member_attendance if a.get("date", "")})
    available_export_leaders = registered_leader_names
    if selected_export_leader and selected_export_leader not in available_export_leaders:
        selected_export_leader = ""
    filtered_attendance = [
        a for a in member_attendance
        if (not selected_export_date or a.get("date", "") == selected_export_date)
        and (not selected_export_leader or a.get("leader", "") == selected_export_leader)
    ]
    # AI-style analytics computed from attendance records
    attendance_by_date = {}
    for item in member_attendance:
        record_date = item.get("date", "")
        attendance_by_date[record_date] = attendance_by_date.get(record_date, 0) + 1
    sorted_dates = sorted([d for d in attendance_by_date.keys() if d])
    latest_date = sorted_dates[-1] if sorted_dates else ""
    previous_date = sorted_dates[-2] if len(sorted_dates) > 1 else ""
    latest_count = attendance_by_date.get(latest_date, 0)
    previous_count = attendance_by_date.get(previous_date, 0)
    if latest_date and previous_date:
        if latest_count > previous_count:
            attendance_trend = f"Upward trend: {previous_count} to {latest_count} attendees."
        elif latest_count < previous_count:
            attendance_trend = f"Downward trend: {previous_count} to {latest_count} attendees."
        else:
            attendance_trend = f"Stable trend: {latest_count} attendees in last two fellowships."
    elif latest_date:
        attendance_trend = f"Single recorded trend point: {latest_count} attendees on {latest_date}."
    else:
        attendance_trend = "No attendance trend available yet."

    active_churches = sorted({a.get("church", "").strip() for a in member_attendance if a.get("church", "").strip()})
    active_churches_count = len(active_churches)
    total_registered_youth_capacity = total_youth if total_youth > 0 else 0
    participation_rate = (
        round((len(member_attendance) / total_registered_youth_capacity) * 100, 2)
        if total_registered_youth_capacity else 0.0
    )
    batches_count = len({
        (a.get("batch_id") or f"{a.get('leader','')}|{a.get('church','')}|{a.get('date','')}|{a.get('submitted','')}")
        for a in filtered_attendance
    })
    fellowship_performance = round((len(member_attendance) / batches_count), 2) if batches_count else 0.0
    top_church = "N/A"
    if member_attendance:
        church_member_counts = {}
        for item in member_attendance:
            c = item.get("church", "N/A")
            church_member_counts[c] = church_member_counts.get(c, 0) + 1
        top_church = max(church_member_counts, key=church_member_counts.get)

    ai_analytical_summary = (
        f"Attendance Trend: {attendance_trend} "
        f"Participation Rate: {participation_rate}% based on current registered youths. "
        f"Active Churches: {active_churches_count}. "
        f"Fellowship Performance: average {fellowship_performance} members per fellowship submission. "
        f"Top Performing Church: {top_church}."
    )
    grouped_attendance = {}
    for a in filtered_attendance:
        key = a.get("batch_id") or f"{a.get('leader','')}|{a.get('church','')}|{a.get('date','')}|{a.get('submitted','')}"
        if key not in grouped_attendance:
            grouped_attendance[key] = {
                "leader": a.get("leader", "N/A"),
                "church": a.get("church", "N/A"),
                "date": a.get("date", "N/A"),
                "submitted": a.get("submitted", "N/A"),
                "rows": []
            }
        grouped_attendance[key]["rows"].append(a)
    grouped_attendance_html = "".join([
        (
            f'<div class="attendance-group" '
            f'data-leader="{html_escape(grouped_attendance[k]["leader"])}" '
            f'data-church="{html_escape(grouped_attendance[k]["church"])}" '
            f'data-submitted="{html_escape(grouped_attendance[k]["submitted"])}" '
            f'data-fellowship-date="{html_escape(grouped_attendance[k]["date"])}" '
            f'style="margin-bottom:1rem;">'
            f'<div class="group-meta" style="margin-bottom:0.45rem; color:#d7efff;"><strong>Leader:</strong> {grouped_attendance[k]["leader"]} &nbsp; | &nbsp; <strong>Church:</strong> {grouped_attendance[k]["church"]} &nbsp; | &nbsp; <strong>Date Submitted:</strong> {grouped_attendance[k]["submitted"]} &nbsp; | &nbsp; <strong>Fellowship Date:</strong> {grouped_attendance[k]["date"]}</div>'
            f'<table class="adminAttendanceTable">'
            f'<tr><th>Full Name</th><th>Age</th><th>Allergies</th></tr>'
            + "".join([
                f'<tr><td>{html_escape(r.get("full_name","N/A"))}</td><td>{html_escape(r.get("age","N/A"))}</td><td>{html_escape(r.get("allergies","N/A"))}</td></tr>'
                for r in grouped_attendance[k]["rows"]
            ])
            + '</table></div>'
        )
        for k in grouped_attendance
    ])
    if chat_user_requested:
        selected_section = "communicate_leader"
    if selected_section not in valid_sections:
        selected_section = "register_leader"

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YFHS Admin Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>{STYLE}</style>
</head>
<body>
    <nav class="admin-nav">
        <h1>👑 {username} Dashboard</h1>
        <ul>
            <li><a href="#" data-section="dashboard" class="{'active' if selected_section=='dashboard' else ''}"><i class="fas fa-tachometer-alt"></i> Dashboard</a></li>
            <li><a href="#" data-section="announcements" class="{'active' if selected_section=='announcements' else ''}"><i class="fas fa-bullhorn"></i> Announcements</a></li>
            <li><a href="#" data-section="register_leader" class="{'active' if selected_section=='register_leader' else ''}"><i class="fas fa-user-plus"></i> Register Leader</a></li>
            <li><a href="#" data-section="communicate_leader" class="{'active' if selected_section=='communicate_leader' else ''}"><i class="fas fa-comments"></i> Communicate Leader</a></li>
            <li><a href="#" data-section="export_report" class="{'active' if selected_section=='export_report' else ''}"><i class="fas fa-robot"></i> AI Analytical Report</a></li>
            <li><a href="/logout" class="btn btn-danger"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
        </ul>
    </nav>

    <div class="content-wrapper">

        <!-- Dashboard Section (with bar graph based on Register Leader) -->
        <section id="dashboard" class="dashboard-section {'active' if selected_section=='dashboard' else ''}">
            <h1 style="font-size: 2rem; text-align: center; margin-bottom: 1rem; color: #81d4fa;">📌 Dashboard</h1>

            <!-- Bar Graph -->
            <div class="card" style="margin: 1rem auto; max-width: 1000px;">
                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; align-items: start;">
                    <div>
                        <h3>Total Youth per Church</h3>
                        <div style="margin-top: 0.9rem; padding: 1rem; border-radius: 14px; background: rgba(255,255,255,0.06); border: 1px solid rgba(79,195,247,0.25);">
                            <div style="height: 220px; display: flex; align-items: flex-end; justify-content: center; gap: 14px;">
                                {''.join([
                                    f'<div style="width: 82px; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 8px;">'
                                    f'<div style="font-weight: 700; color: #dff3ff; font-size: 0.9rem;">{counts[i]}</div>'
                                    f'<div style="width: 100%; height: {max(28, round(150 * (counts[i] / bar_divisor)))}px; '
                                    f'background: linear-gradient(180deg, #6fd9ff 0%, #29b6f6 55%, #0288d1 100%); '
                                    f'border-radius: 10px 10px 4px 4px; box-shadow: 0 8px 16px rgba(2,136,209,0.35);"></div>'
                                    f'<div style="text-align: center; font-size: 0.72rem; color: #cbe8ff; line-height: 1.2;">{churches[i]}</div>'
                                    f'</div>'
                                    for i in range(len(churches))
                                ])}
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 0.8rem; margin-top: 2.2rem;">
                        <div style="padding: 1rem; border-radius: 12px; border: 1px solid rgba(79,195,247,0.3); background: rgba(79,195,247,0.12); text-align: center;">
                            <div style="font-size: 0.9rem; color: #d7efff;">Total Youth</div>
                            <div style="font-size: 2rem; font-weight: 700; color: #81d4fa;">{total_youth}</div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="announcements" class="dashboard-section {'active' if selected_section=='announcements' else ''}">
            <h2 style="font-size: 2.5rem; text-align: center; margin-bottom: 2rem;">📢 Announcements & AI Calendar</h2>
            <style>
                #announcements .ann-pro-card {{
                    border-radius: 20px;
                    border: 1px solid rgba(79,195,247,0.35);
                    background: linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04));
                    box-shadow: 0 24px 45px rgba(0,0,0,0.30);
                }}
                #announcements .ann-pro-input, #announcements .ann-pro-textarea {{
                    width: 100%;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,0.25);
                    background: rgba(8, 21, 31, 0.72);
                    color: #f5fbff;
                    font-weight: 500;
                    padding: 0.95rem 1rem;
                    transition: all 0.25s ease;
                }}
                #announcements .ann-pro-textarea {{
                    min-height: 140px;
                    resize: vertical;
                }}
                #announcements .ann-pro-input:focus, #announcements .ann-pro-textarea:focus {{
                    outline: none;
                    border-color: #4fc3f7;
                    box-shadow: 0 0 0 3px rgba(79,195,247,0.2);
                    transform: translateY(-1px);
                }}
                #announcements .hint-chip {{
                    display: inline-block;
                    margin-top: 0.7rem;
                    padding: 0.3rem 0.7rem;
                    border-radius: 999px;
                    font-size: 0.82rem;
                    background: rgba(79,195,247,0.18);
                    border: 1px solid rgba(79,195,247,0.35);
                    color: #d7efff;
                }}
            </style>
            <div class="card" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div class="ann-pro-card" style="padding: 1rem;">
                    <h3>Create Announcement</h3>
                    <form method="post" action="{announcement_form_action}" style="margin-top: 0.8rem; display: grid; gap: 0.7rem;">
                        <input class="ann-pro-input" type="text" name="title" placeholder="Announcement title" value="{announcement_form_title}" required>
                        <textarea class="ann-pro-textarea" name="message" placeholder="Write announcement details..." required>{announcement_form_message}</textarea>
                        <button class="btn" type="submit">{"Update Announcement" if announcement_to_edit else "Send to Leader Announcements"}</button>
                    </form>
                    {f'<div class="hint-chip">Generated 3rd Sunday date: {generated_date}</div>' if generated_date else ''}
                    {f'<a class="btn btn-danger" style="padding:0.6rem 1rem; margin-top:0.7rem;" href="/admin?section=announcements">Cancel Edit</a>' if announcement_to_edit else ''}
                </div>
                <div class="ann-pro-card" style="padding: 1rem;">
                    <h3>AI Calendar Scheduler</h3>
                    <p style="margin-top: 0.8rem;">Automatically generate youth fellowship schedules every 3rd Sunday of upcoming months. Admin controls generation, leaders can view only.</p>
                    <form method="post" action="/admin/generate_ai_calendar">
                        <button class="btn" type="submit" style="margin-top: 1rem;">Generate 3rd Sunday Schedule</button>
                    </form>
                </div>
            </div>
            <div class="card" style="margin-top: 1rem;">
                <h3>Sent Announcements</h3>
                <table>
                    <tr><th>Date</th><th>Title</th><th>Message</th><th>Action</th></tr>
                    {''.join([
                        f'<tr>'
                        f'<td>{a.get("date","")}</td>'
                        f'<td>{a.get("title","")}</td>'
                        f'<td>{a.get("message","")}</td>'
                        f'<td style="display:flex; gap:0.5rem;">'
                        f'<a href="/admin?section=announcements&edit_announcement_id={a.get("id",0)}" class="btn" style="padding:0.45rem 0.8rem; margin:0; font-size:0.85rem;">Edit</a>'
                        f'<form method="post" action="/admin/delete_announcement/{a.get("id",0)}" style="margin:0;" onsubmit="return confirm(&quot;Are you sure you want to delete this?&quot;);">'
                        f'<button type="submit" class="btn btn-danger" style="padding:0.45rem 0.8rem; margin:0; font-size:0.85rem;">Delete</button>'
                        f'</form>'
                        f'</td>'
                        f'</tr>'
                        for a in sorted(announcements, key=lambda x: x.get("id", 0), reverse=True)
                    ]) or '<tr><td colspan="4">No announcements yet.</td></tr>'}
                </table>
            </div>
        </section>

        <!-- Register Leader Section -->
        <section id="register_leader" class="dashboard-section {'active' if selected_section=='register_leader' else ''}">
            <div style="margin-bottom: 1.5rem; text-align: center;">
                <h1 style="font-size: 2rem; color: #81d4fa; margin: 0;">Dashboard</h1>
            </div>
            <h2 style="font-size: 2.5rem; text-align: center; margin-bottom: 2rem; background: linear-gradient(45deg, #4fc3f7, #81d4fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                Register Leader
            </h2>

            <!-- Register Leader Form -->
            <style>
                #register_leader .pro-form-card {{
                    max-width: 760px;
                    margin: 0 auto;
                    border-radius: 20px;
                    border: 1px solid rgba(79,195,247,0.35);
                    background: linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04));
                    box-shadow: 0 24px 45px rgba(0,0,0,0.30);
                    animation: registerCardIn 0.65s ease-out;
                }}
                #register_leader .pro-form-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 1rem;
                }}
                #register_leader .field-wrap {{
                    position: relative;
                    animation: fieldFloatIn 0.5s ease both;
                }}
                #register_leader .field-wrap i {{
                    position: absolute;
                    left: 12px;
                    top: 50%;
                    transform: translateY(-50%);
                    color: rgba(255,255,255,0.75);
                    pointer-events: none;
                }}
                #register_leader .pro-input {{
                    width: 100%;
                    padding: 0.95rem 0.95rem 0.95rem 2.3rem;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,0.25);
                    background: rgba(8, 21, 31, 0.72);
                    color: #f5fbff;
                    caret-color: #f5fbff;
                    font-weight: 500;
                    transition: all 0.25s ease;
                }}
                #register_leader .pro-input::placeholder {{
                    color: rgba(230, 243, 255, 0.72);
                }}
                #register_leader .pro-input:focus {{
                    outline: none;
                    border-color: #4fc3f7;
                    box-shadow: 0 0 0 3px rgba(79,195,247,0.2);
                    transform: translateY(-1px);
                }}
                #register_leader .pro-submit {{
                    margin-top: 0.6rem;
                    padding: 1rem;
                    border: none;
                    border-radius: 12px;
                    font-size: 1rem;
                    font-weight: 700;
                    color: #fff;
                    background: linear-gradient(45deg, #29b6f6, #0288d1);
                    cursor: pointer;
                    transition: all 0.25s ease;
                }}
                #register_leader .pro-submit:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 10px 22px rgba(41,182,246,0.35);
                }}
                #register_leader .table-wrap {{
                    overflow-x: auto;
                    border-radius: 14px;
                    border: 1px solid rgba(79,195,247,0.22);
                    background: rgba(0,0,0,0.08);
                }}
                #register_leader .leaders-table {{
                    width: 100%;
                    border-collapse: collapse;
                    min-width: 980px;
                }}
                #register_leader .leaders-table th,
                #register_leader .leaders-table td {{
                    vertical-align: middle;
                    white-space: nowrap;
                }}
                #register_leader .leaders-table td:nth-child(1),
                #register_leader .leaders-table td:nth-child(6),
                #register_leader .leaders-table td:nth-child(7) {{
                    white-space: normal;
                }}
                #register_leader .leaders-table th {{
                    position: sticky;
                    top: 0;
                    z-index: 1;
                }}
                #register_leader .leader-action-cell {{
                    display: flex;
                    align-items: center;
                    gap: 0.45rem;
                    flex-wrap: nowrap;
                }}
                #register_leader .leader-action-cell form {{
                    margin: 0;
                }}
                @keyframes registerCardIn {{
                    from {{ opacity: 0; transform: translateY(14px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                @keyframes fieldFloatIn {{
                    from {{ opacity: 0; transform: translateY(8px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                @media (max-width: 760px) {{
                    #register_leader .pro-form-grid {{ grid-template-columns: 1fr; }}
                }}
            </style>
            <div class="card pro-form-card">
                <h3 style="text-align: center; margin-bottom: 1.1rem;">
                    <i class="fas fa-user-plus"></i> Register Church Leader
                </h3>
                <form method="post" action="{leader_form_action}" style="display: grid; gap: 1rem;">
                    <div class="pro-form-grid">
                        <div class="field-wrap"><i class="fas fa-user"></i><input class="pro-input" type="text" name="fullname" placeholder="Full Name" value="{html_escape(leader_to_edit.get('full_name', '') if leader_to_edit else '')}" required></div>
                        <div class="field-wrap"><i class="fas fa-place-of-worship"></i><input class="pro-input" type="text" name="church" placeholder="Church" value="{html_escape(leader_to_edit.get('church', '') if leader_to_edit else '')}" required></div>
                        <div class="field-wrap"><i class="fas fa-location-dot"></i><input class="pro-input" type="text" name="address" placeholder="Church Address" value="{html_escape(leader_to_edit.get('address', '') if leader_to_edit else '')}" required></div>
                        <div class="field-wrap"><i class="fas fa-users"></i><input class="pro-input" type="number" min="0" name="current_youths" placeholder="No. of Current Youths" value="{parse_int(leader_to_edit.get('current_youths', 0), 0) if leader_to_edit else ''}" required></div>
                        <div class="field-wrap"><i class="fas fa-calendar-days"></i><input class="pro-input" type="number" name="age" placeholder="Age" value="{html_escape(leader_to_edit.get('age', '') if leader_to_edit else '')}" required></div>
                        <div class="field-wrap"><i class="fas fa-at"></i><input class="pro-input" type="text" name="username" placeholder="Username" value="{html_escape(leader_to_edit.get('username', '') if leader_to_edit else '')}" required></div>
                        <div class="field-wrap"><i class="fas fa-key"></i><input class="pro-input" type="password" name="password" placeholder="Password" value="{html_escape(leader_to_edit.get('password', '') if leader_to_edit else '')}" required></div>
                    </div>
                    <div class="field-wrap">
                        <i class="fas fa-venus-mars"></i>
                        <select class="pro-input" name="grader" required>
                            <option value="" style="color: #222;">Select Gender</option>
                            <option value="Male" style="color: #222;" {"selected" if leader_to_edit and leader_to_edit.get("gender", leader_to_edit.get("grader",""))=="Male" else ""}>Male</option>
                            <option value="Female" style="color: #222;" {"selected" if leader_to_edit and leader_to_edit.get("gender", leader_to_edit.get("grader",""))=="Female" else ""}>Female</option>
                        </select>
                    </div>
                    <button class="pro-submit" type="submit">{"Update Leader" if leader_to_edit else "Register Leader"}</button>
                    {f'<a href="/admin?section=register_leader" class="btn btn-danger" style="text-align:center; margin:0;">Cancel Edit</a>' if leader_to_edit else ''}
                </form>
            </div>

            <!-- Church Leader Table -->
            <div class="card" style="margin-top: 2rem;">
                <h3>Church Leader Table</h3>
                <div class="table-wrap">
                <table class="leaders-table">
                    <tr>
                        <th>Name</th>
                        <th>Username</th>
                        <th>Password</th>
                        <th>Age</th>
                        <th>Gender</th>
                        <th>Church</th>
                        <th>Church Address</th>
                        <th>No. of Current Youths</th>
                        <th>Action</th>
                    </tr>
                    {''.join([
                        f'<tr>'
                        f'<td>{l.get("full_name", l.get("name", "N/A"))}</td>'
                        f'<td>{l.get("username", "N/A")}</td>'
                        f'<td>{"*" * len(str(l.get("password", ""))) if l.get("password") else "N/A"}</td>'
                        f'<td>{l.get("age", "N/A")}</td>'
                        f'<td>{l.get("gender", l.get("grader", "N/A"))}</td>'
                        f'<td>{l.get("church", "N/A")}</td>'
                        f'<td>{l.get("address", "N/A")}</td>'
                        f'<td>{parse_int(l.get("current_youths", 0), 0)}</td>'
                        f'<td class="leader-action-cell">'
                        f'<a href="/admin?section=register_leader&edit_leader_id={l.get("id",0)}" class="btn" style="padding: 0.45rem 0.9rem; margin: 0 0.4rem 0 0; font-size: 0.85rem;">Edit</a>'
                        f'<form method="post" action="/delete_leader/{l.get("id", 0)}" '
                        f'onsubmit="return confirm(&quot;Are you sure you want to delete this?&quot;);">'
                        f'<button type="submit" class="btn btn-danger" style="padding: 0.45rem 0.9rem; margin: 0; font-size: 0.85rem;">Delete</button>'
                        f'</form>'
                        f'</td>'
                        f'</tr>'
                        for l in leaders
                    ])}
                </table>
                </div>
            </div>
        </section>

        <!-- Communicate Leader Section -->
        <section id="communicate_leader" class="dashboard-section {'active' if selected_section=='communicate_leader' else ''}">
            <h2 style="font-size: 2.5rem; text-align: center; margin-bottom: 2rem;">🤖 Communicate Leader</h2>
            <div class="card" style="display: grid; grid-template-columns: 1fr 1.3fr; gap: 1rem;">
                <div>
                    <h3>Registered Leaders</h3>
                    <input
                        id="leaderSearchInput"
                        type="text"
                        placeholder="Search by leader name, church, or username"
                        style="width: 100%; margin-top: 0.8rem; padding: 0.9rem 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.25); background: rgba(255,255,255,0.08); color: #fff;"
                    >
                    <div id="leaderListContainer" style="margin-top: 0.8rem; max-height: 360px; overflow-y: auto; display: grid; gap: 0.6rem;">
                        {''.join([
                            f'<a href="/admin?section=communicate_leader&chat_user={l.get("username","")}" '
                            f'class="leader-item" '
                            f'data-fullname="{l.get("full_name","").lower()}" '
                            f'data-username="{l.get("username","").lower()}" '
                            f'data-church="{l.get("church","").lower()}" '
                            f'style="display:block; text-decoration:none; padding:0.8rem; border-radius:10px; border:1px solid rgba(79,195,247,0.28); background: {"rgba(79,195,247,0.2)" if l.get("username","")==selected_chat_username else "rgba(255,255,255,0.06)"};">'
                            f'<div style="font-weight:600; color:#e6f5ff;">{l.get("full_name","N/A")}</div>'
                            f'<div style="font-size:0.86rem; color:#b6defa;">@{l.get("username","N/A")} - {l.get("church","N/A")}</div>'
                            f'</a>'
                            for l in leaders_for_chat
                        ]) or '<div style="padding:0.8rem; border-radius:10px; background:rgba(255,255,255,0.06); color:#cbe8ff;">No registered leaders yet.</div>'}
                    </div>
                </div>
                <div>
                    <h3>Chat {f"with {selected_chat_name}" if selected_chat_username else ""}</h3>
                    <div style="margin-top: 0.8rem; height: 285px; overflow-y: auto; border-radius: 12px; border: 1px solid rgba(79,195,247,0.25); padding: 0.9rem; background: rgba(0,0,0,0.18); display: grid; gap: 0.6rem;">
                        {''.join([
                            f'<div style="justify-self: {"end" if m.get("sender_role")=="admin" else "start"}; max-width: 86%; padding: 0.55rem 0.8rem; border-radius: 10px; background: {"rgba(41,182,246,0.35)" if m.get("sender_role")=="admin" else "rgba(255,255,255,0.14)"};">'
                            f'<div style="font-size: 0.74rem; color: #d7efff; margin-bottom: 0.2rem;">{m.get("sender_name","Unknown")} - {m.get("sent_at","")}</div>'
                            f'<div style="color:#fff;">{m.get("message","")}</div>'
                            f'</div>'
                            for m in conversation
                        ]) or '<div style="color:#cbe8ff;">No messages yet.</div>'}
                    </div>
                    <form method="post" action="/admin/send_message" style="margin-top: 0.8rem; display: grid; gap: 0.6rem;">
                        <input type="hidden" name="target_username" value="{selected_chat_username}">
                        <textarea name="message" placeholder="Type your message..." style="min-height: 90px;" {"required" if selected_chat_username else "disabled"}></textarea>
                        <button class="btn" type="submit" {"disabled" if not selected_chat_username else ""}>Send Message</button>
                    </form>
                </div>
            </div>
        </section>

        <!-- Export Report Section (untouched) -->
        <section id="export_report" class="dashboard-section {'active' if selected_section=='export_report' else ''}">
            <h2 style="font-size: 2.5rem; text-align: center; margin-bottom: 2rem;">🤖 AI Analytical Report</h2>
            <div class="card" style="margin-bottom: 1rem;">
                <h3>AI-Based Analytics Summary</h3>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:0.8rem; margin-top:0.8rem;">
                    <div style="padding:0.8rem; border-radius:12px; border:1px solid rgba(79,195,247,0.3); background:rgba(79,195,247,0.12);">
                        <div style="font-size:0.85rem; color:#d7efff;">Attendance Trend</div>
                        <div style="font-weight:700; color:#fff; margin-top:0.35rem;">{html_escape(attendance_trend)}</div>
                    </div>
                    <div style="padding:0.8rem; border-radius:12px; border:1px solid rgba(79,195,247,0.3); background:rgba(79,195,247,0.12);">
                        <div style="font-size:0.85rem; color:#d7efff;">Participation Rate</div>
                        <div style="font-size:1.25rem; font-weight:700; color:#81d4fa; margin-top:0.35rem;">{participation_rate}%</div>
                    </div>
                    <div style="padding:0.8rem; border-radius:12px; border:1px solid rgba(79,195,247,0.3); background:rgba(79,195,247,0.12);">
                        <div style="font-size:0.85rem; color:#d7efff;">Active Churches</div>
                        <div style="font-size:1.25rem; font-weight:700; color:#81d4fa; margin-top:0.35rem;">{active_churches_count}</div>
                    </div>
                    <div style="padding:0.8rem; border-radius:12px; border:1px solid rgba(79,195,247,0.3); background:rgba(79,195,247,0.12);">
                        <div style="font-size:0.85rem; color:#d7efff;">Fellowship Performance</div>
                        <div style="font-size:1.25rem; font-weight:700; color:#81d4fa; margin-top:0.35rem;">{fellowship_performance} avg members</div>
                    </div>
                </div>
                <p style="margin-top:0.9rem; text-align:left;">{html_escape(ai_analytical_summary)}</p>
            </div>
            <div class="card" style="margin-bottom: 1rem;">
                <h3>Filter Report</h3>
                <form method="get" action="/admin" style="display:flex; gap:0.8rem; align-items:end; flex-wrap:wrap;">
                    <input type="hidden" name="section" value="export_report">
                    <div class="form-group" style="margin:0; min-width:200px;">
                        <label>Select Date</label>
                        <select name="export_date" class="pro-input">
                            <option value="">All Dates</option>
                            {''.join([f'<option value="{d}" {"selected" if d==selected_export_date else ""}>{d}</option>' for d in available_export_dates])}
                        </select>
                    </div>
                    <div class="form-group" style="margin:0; min-width:220px;">
                        <label>Select Leader</label>
                        <select name="export_leader" class="pro-input">
                            <option value="">All Leaders</option>
                            {''.join([f'<option value="{l}" {"selected" if l==selected_export_leader else ""}>{l}</option>' for l in available_export_leaders])}
                        </select>
                    </div>
                    <button class="btn" type="submit" style="margin:0;">Apply Filter</button>
                    <a class="btn btn-danger" href="/admin?section=export_report" style="margin:0;">Reset</a>
                </form>
            </div>
            <div class="card">
                <h3>Recent Attendance</h3>
                {grouped_attendance_html or '<div>No attendance records yet.</div>'}
            </div>
            <div style="text-align: center; margin-top: 2rem;">
                <button class="btn" type="button" onclick="printFilteredAttendance()">🖨️ Print Report</button>
                <button class="btn" type="button" onclick="exportAdminAttendanceCSV()">💾 Export to Excel/CSV</button>
            </div>
        </section>
    </div>

    <script>
    document.querySelectorAll('.admin-nav a[data-section]').forEach(link => {{
        link.addEventListener('click', function(e) {{
            e.preventDefault();
            const section = this.getAttribute('data-section');
            document.querySelectorAll('.admin-nav a').forEach(a => a.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));
            document.getElementById(section).classList.add('active');
        }});
    }});
    const leaderSearchInput = document.getElementById('leaderSearchInput');
    if (leaderSearchInput) {{
        leaderSearchInput.addEventListener('input', function() {{
            const query = this.value.toLowerCase().trim();
            document.querySelectorAll('#leaderListContainer .leader-item').forEach(item => {{
                const searchable = (
                    item.getAttribute('data-fullname') + ' ' +
                    item.getAttribute('data-username') + ' ' +
                    item.getAttribute('data-church')
                );
                item.style.display = searchable.includes(query) ? 'block' : 'none';
            }});
        }});
    }}
    function exportAdminAttendanceCSV() {{
        const groups = Array.from(document.querySelectorAll('.attendance-group'));
        const csvParts = [];
        csvParts.push('"Leader","Church","Fellowship Date","Date Submitted","Full Name","Age","Allergies"');
        groups.forEach(group => {{
            const leader = group.getAttribute('data-leader') || '';
            const church = group.getAttribute('data-church') || '';
            const fellowshipDate = group.getAttribute('data-fellowship-date') || '';
            const submitted = group.getAttribute('data-submitted') || '';
            const rows = Array.from(group.querySelectorAll('table tr'));
            rows.slice(1).forEach(row => {{
                const cols = Array.from(row.querySelectorAll('td')).map(cell => (cell.innerText || '').trim());
                if (cols.length >= 3) {{
                    csvParts.push([
                        leader, church, fellowshipDate, submitted, cols[0], cols[1], cols[2]
                    ].map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','));
                }}
            }});
        }});
        const csv = csvParts.join('\\n');
        const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'attendance_report.csv';
        link.click();
        URL.revokeObjectURL(link.href);
    }}
    function printFilteredAttendance() {{
        const groups = Array.from(document.querySelectorAll('.attendance-group'));
        if (!groups.length) return;
        let printSections = '';
        groups.forEach(group => {{
            const leader = group.getAttribute('data-leader') || '';
            const church = group.getAttribute('data-church') || '';
            const fellowshipDate = group.getAttribute('data-fellowship-date') || '';
            const submitted = group.getAttribute('data-submitted') || '';
            const rows = Array.from(group.querySelectorAll('table tr')).slice(1);
            let tableRows = '';
            rows.forEach(row => {{
                const cols = Array.from(row.querySelectorAll('td')).map(cell => (cell.innerText || '').trim());
                if (cols.length >= 3) {{
                    tableRows += `<tr><td>${{cols[0]}}</td><td>${{cols[1]}}</td><td>${{cols[2]}}</td></tr>`;
                }}
            }});
            printSections += `
                <div style="margin-bottom: 18px;">
                    <div style="margin-bottom: 8px; font-weight: 600;">
                        Leader: ${{leader}} | Church: ${{church}} | Date: ${{fellowshipDate}} | Submitted Date: ${{submitted}}
                    </div>
                    <table>
                        <tr>
                            <th>Full Name</th>
                            <th>Age</th>
                            <th>Allergies</th>
                        </tr>
                        ${{tableRows || '<tr><td colspan="3">No attendance records found.</td></tr>'}}
                    </table>
                </div>
            `;
        }});
        const win = window.open('', '_blank');
        win.document.write(`
            <html>
            <head>
                <title>Filtered Attendance Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 16px; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                    th {{ background: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h2>Filtered Recent Attendance</h2>
                ${{printSections}}
            </body>
            </html>
        `);
        win.document.close();
        win.focus();
        win.print();
        win.close();
    }}
    </script>
</body>
</html>
    """
@app.route('/logout')
def logout():
    init_session_data()
    persist_runtime_data()
    session.clear()
    return redirect(url_for('landing'))


@app.route('/leader')
def leader_dashboard():
    init_session_data()
    if not session.get('leader_logged_in'):
        return redirect(url_for('login'))

    leader = session.get('leader_profile') or {}
    chat_messages = session.get('chat_messages', [])
    announcements = session.get('announcements', [])
    schedules = session.get('schedules', [])
    attendance = session.get('attendance', [])
    full_name = leader.get('full_name', session.get('username', 'Leader'))
    church = leader.get('church', 'N/A')
    address = leader.get('address', 'N/A')
    username = leader.get('username', 'N/A')
    selected_section = request.args.get('section', 'leader_announcements').strip()
    edit_attendance_id = parse_int(request.args.get('edit_attendance_id', ''), 0)
    drafts = session.get('attendance_drafts', {})
    draft_groups = normalize_draft_groups(drafts.get(username, []))
    if not draft_groups:
        draft_groups = [{
            "fellowship_date": get_upcoming_fellowship_date(),
            "submitted": False,
            "submitted_at": "",
            "members": []
        }]
        drafts[username] = draft_groups
        session['attendance_drafts'] = drafts
        persist_runtime_data()
    edit_group_index = parse_int(request.args.get('edit_group_index', ''), len(draft_groups) - 1)
    edit_group_index = min(max(edit_group_index, 0), len(draft_groups) - 1)
    attendance_to_edit = next(
        (
            a for a in draft_groups[edit_group_index].get("members", [])
            if a.get("id") == edit_attendance_id
        ),
        None
    )
    attendance_form_action = (
        f"/leader/update_attendance/{edit_attendance_id}" if attendance_to_edit else "/leader/submit_attendance"
    )
    conversation = [
        m for m in chat_messages
        if m.get('target_username', '').strip() == username
    ]
    leader_group_cards = []
    for gi, g in enumerate(draft_groups):
        member_rows = []
        for m in g.get("members", []):
            if g.get("submitted"):
                action_html = '<span style="color:#8ed3ff;">Done</span>'
            else:
                action_html = (
                    f'<a href="/leader?section=leader_submit&edit_group_index={gi}&edit_attendance_id={m.get("id",0)}" '
                    f'class="btn" style="padding:0.45rem 0.8rem; margin:0; font-size:0.85rem;">Edit</a>'
                    f'<form method="post" action="/leader/delete_attendance/{m.get("id",0)}" style="margin:0;" '
                    f'onsubmit="return confirm(&quot;Are you sure you want to delete this?&quot;);">'
                    f'<input type="hidden" name="group_index" value="{gi}">'
                    f'<button type="submit" class="btn btn-danger" style="padding:0.45rem 0.8rem; margin:0; font-size:0.85rem;">Delete</button>'
                    f'</form>'
                )
            member_rows.append(
                f'<tr>'
                f'<td>{html_escape(m.get("full_name",""))}</td>'
                f'<td>{html_escape(m.get("age",""))}</td>'
                f'<td>{html_escape(m.get("allergies",""))}</td>'
                f'<td style="display:flex; gap:0.45rem;">{action_html}</td>'
                f'</tr>'
            )

        if gi == len(draft_groups) - 1:
            submit_footer = (
                f'<div style="text-align:right; margin-top:0.8rem;">'
                f'<form method="post" action="/leader/finalize_attendance">'
                f'<button class="btn" type="submit" '
                f'{"disabled" if not g.get("members") or g.get("submitted") else ""}>'
                f'{"Done" if g.get("submitted") else "Submit Attendance"}'
                f'</button></form></div>'
            )
        else:
            submit_footer = (
                f'<div style="margin-top:0.8rem; color:#8ed3ff;">'
                f'<strong>Status:</strong> Done ({html_escape(g.get("submitted_at",""))})</div>'
            )

        leader_group_cards.append(
            f'<div class="card" style="max-width: 900px; margin: 1rem auto 0;">'
            f'<h3>Fellowship Date: {g.get("fellowship_date", "N/A")}</h3>'
            f'<table>'
            f'<tr><th>Full Name</th><th>Age</th><th>Allergies</th><th>Action</th></tr>'
            + "".join(member_rows)
            + (f'<tr><td colspan="4">No registered members yet.</td></tr>' if not g.get("members", []) else '')
            + '</table>'
            + submit_footer
            + '</div>'
        )
    leader_group_cards_html = "".join(leader_group_cards)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Church Leader Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>{STYLE}</style>
</head>
<body>
    <nav class="admin-nav">
        <h1>⛪ Leader Panel</h1>
        <ul>
            <li><a href="#" data-section="leader_announcements" class="{'active' if selected_section=='leader_announcements' else ''}"><i class="fas fa-bullhorn"></i> Announcements</a></li>
            <li><a href="#" data-section="leader_communicate" class="{'active' if selected_section=='leader_communicate' else ''}"><i class="fas fa-comments"></i> Communicate Leader</a></li>
            <li><a href="#" data-section="leader_submit" class="{'active' if selected_section=='leader_submit' else ''}"><i class="fas fa-clipboard-check"></i> Submit Attendance</a></li>
            <li><a href="/logout" class="btn btn-danger"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
        </ul>
    </nav>

    <div class="content-wrapper">
        <section id="leader_announcements" class="dashboard-section {'active' if selected_section=='leader_announcements' else ''}">
            <h2 style="font-size: 2.3rem; text-align: center; margin-bottom: 1.2rem;">Announcements</h2>
            <div class="card" style="max-width: 900px; margin: 0 auto;">
                <p style="margin-bottom: 0.7rem;"><strong>Welcome, {full_name}</strong></p>
                <p>Stay updated for upcoming fellowship activities and reminders.</p>
                <hr style="margin: 1rem 0; border-color: rgba(255,255,255,0.18);">
                <p><strong>Church:</strong> {church}</p>
                <p><strong>Address:</strong> {address}</p>
                <p><strong>Username:</strong> {username}</p>
            </div>
            <div class="card" style="max-width: 900px; margin: 1rem auto 0;">
                <h3>Latest Announcements (View Only)</h3>
                <table>
                    <tr><th>Date</th><th>Title</th><th>Message</th></tr>
                    {''.join([
                        f'<tr><td>{a.get("date","")}</td><td>{a.get("title","")}</td><td>{a.get("message","")}</td></tr>'
                        for a in sorted(announcements, key=lambda x: x.get("id", 0), reverse=True)
                    ]) or '<tr><td colspan="3">No announcements yet.</td></tr>'}
                </table>
            </div>
        </section>

        <section id="leader_communicate" class="dashboard-section {'active' if selected_section=='leader_communicate' else ''}">
            <h2 style="font-size: 2.3rem; text-align: center; margin-bottom: 1.2rem;">Communicate Leader</h2>
            <div class="card" style="max-width: 900px; margin: 0 auto;">
                <h3>Leader Communication</h3>
                <p>Use this section to coordinate with admin.</p>
                <div style="margin-top: 0.8rem; height: 250px; overflow-y: auto; border-radius: 12px; border: 1px solid rgba(79,195,247,0.25); padding: 0.9rem; background: rgba(0,0,0,0.18); display: grid; gap: 0.6rem;">
                    {''.join([
                        f'<div style="justify-self: {"start" if m.get("sender_role")=="admin" else "end"}; max-width: 85%; padding: 0.55rem 0.8rem; border-radius: 10px; background: {"rgba(79,195,247,0.35)" if m.get("sender_role")=="admin" else "rgba(255,255,255,0.14)"};">'
                        f'<div style="font-size: 0.74rem; color: #d7efff; margin-bottom: 0.2rem;">{m.get("sender_name","Unknown")} - {m.get("sent_at","")}</div>'
                        f'<div style="color:#fff;">{m.get("message","")}</div>'
                        f'</div>'
                        for m in conversation
                    ]) or '<div style="color:#cbe8ff;">No messages yet.</div>'}
                </div>
                <form method="post" action="/leader/send_message" style="margin-top: 0.8rem;">
                    <textarea name="message" placeholder="Type your message here..." style="min-height: 120px;" required></textarea>
                    <button class="btn" type="submit" style="margin-top: 0.8rem;">Send Message</button>
                </form>
            </div>
        </section>

        <section id="leader_submit" class="dashboard-section {'active' if selected_section=='leader_submit' else ''}">
            <h2 style="font-size: 2.3rem; text-align: center; margin-bottom: 1.2rem;">Submit Attendance</h2>
            <div class="card" style="max-width: 900px; margin: 0 auto;">
                <h3>Member Registration Form</h3>
                <form method="post" action="{attendance_form_action}">
                    <input type="hidden" name="group_index" value="{edit_group_index}">
                    <div class="form-group">
                        <label>Full Name</label>
                        <input type="text" name="full_name" value="{html_escape(attendance_to_edit.get('full_name', '') if attendance_to_edit else '')}" placeholder="Enter full name" required>
                    </div>
                    <div class="form-group">
                        <label>Age</label>
                        <input type="number" name="age" min="1" value="{html_escape(attendance_to_edit.get('age', '') if attendance_to_edit else '')}" placeholder="Enter age" required>
                    </div>
                    <div class="form-group">
                        <label>Allergies</label>
                        <textarea name="allergies" placeholder="Write allergies" required>{html_escape(attendance_to_edit.get('allergies', '') if attendance_to_edit else '')}</textarea>
                    </div>
                    <button class="btn" type="submit">{"Update Member" if attendance_to_edit else "Register Member"}</button>
                    {f'<a href="/leader?section=leader_submit" class="btn btn-danger" style="margin-left:0.4rem;">Cancel Edit</a>' if attendance_to_edit else ''}
                </form>
            </div>
            {leader_group_cards_html}
        </section>
    </div>

    <script>
    document.querySelectorAll('.admin-nav a[data-section]').forEach(link => {{
        link.addEventListener('click', function(e) {{
            e.preventDefault();
            const section = this.getAttribute('data-section');
            document.querySelectorAll('.admin-nav a').forEach(a => a.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));
            document.getElementById(section).classList.add('active');
        }});
    }});
    </script>
</body>
</html>
    """


if __name__ == '__main__':
    app.run(debug=True)