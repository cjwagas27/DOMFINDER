import sqlite3
import hashlib
import os
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'database.db')


# ── Database setup ────────────────────────────────────────────────────────────

def get_db():
    """Open a database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist yet."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users_table (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                email      TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                role       TEXT    NOT NULL DEFAULT 'student',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bookings_table (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                dorm_id    INTEGER NOT NULL,
                move_in    TEXT    NOT NULL,
                move_out   TEXT    NOT NULL,
                message    TEXT,
                status     TEXT    NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users_table(id)
            )
        ''')
        conn.commit()


def hash_password(password: str) -> str:
    """SHA-256 hash for password storage."""
    return hashlib.sha256(password.encode()).hexdigest()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the landing page."""
    return send_from_directory('.', 'index.html')


@app.route('/api/register', methods=['POST'])
def register():
    data     = request.get_json()
    name     = (data.get('name')     or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    password = (data.get('password') or '').strip()
    role     = (data.get('role')     or 'student').strip()

    # ── Validation ──
    if not name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    if role not in ('student', 'owner'):
        return jsonify({'success': False, 'message': 'Invalid role selected.'}), 400

    # ── Insert ──
    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO users_table (name, email, password, role) VALUES (?, ?, ?, ?)',
                (name, email, hash_password(password), role)
            )
            conn.commit()
        return jsonify({'success': True, 'message': f'Account created! Welcome, {name}.'}), 201

    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'An account with this email already exists.'}), 409


@app.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = (data.get('email')    or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({'success': False, 'message': 'Please fill in all fields.'}), 400

    with get_db() as conn:
        user = conn.execute(
            'SELECT * FROM users_table WHERE email = ? AND password = ?',
            (email, hash_password(password))
        ).fetchone()

    if not user:
        return jsonify({'success': False, 'message': 'Incorrect email or password.'}), 401

    return jsonify({
        'success': True,
        'message': f'Welcome back, {user["name"]}!',
        'user': {
            'id':   user['id'],
            'name': user['name'],
            'role': user['role']
        }
    }), 200


@app.route('/api/book', methods=['POST'])
def book():
    data     = request.get_json()
    user_id  = data.get('user_id')
    dorm_id  = data.get('dorm_id')
    move_in  = (data.get('move_in')  or '').strip()
    move_out = (data.get('move_out') or '').strip()
    message  = (data.get('message')  or '').strip()

    if not user_id or not dorm_id or not move_in or not move_out:
        return jsonify({'success': False, 'message': 'Missing required fields.'}), 400

    if move_out <= move_in:
        return jsonify({'success': False, 'message': 'Move-out date must be after move-in date.'}), 400

    with get_db() as conn:
        conn.execute(
            '''INSERT INTO bookings_table (user_id, dorm_id, move_in, move_out, message)
               VALUES (?, ?, ?, ?, ?)''',
            (user_id, dorm_id, move_in, move_out, message)
        )
        conn.commit()

    return jsonify({'success': True, 'message': 'Booking request submitted successfully.'}), 201


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print('DormFinder running at http://127.0.0.1:5000')
    app.run(debug=True, port=5000)
