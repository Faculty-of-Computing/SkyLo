
from flask import Flask, render_template, request, g
import requests
import sqlite3


app = Flask(__name__)
API_KEY = "ef0cc4d3880644acbd65f6218a3beed6"
DATABASE = 'weather_searches.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, timeout=10, check_same_thread=False)
        db.execute('PRAGMA journal_mode=WAL;')
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL,
                ip TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        cursor.close()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    weather = None
    most_frequent = None
    most_recent = None
    if request.method == 'POST':
        city = request.form['city']
        from urllib.parse import quote_plus
        city_encoded = quote_plus(city)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('main') and data.get('weather'):
                weather = {
                    'city': city,
                    'temperature': data['main']['temp'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon']
                }
                # Store search in DB
                db = get_db()
                ip = request.remote_addr or 'unknown'
                cur = db.cursor()
                cur.execute('INSERT INTO searches (city, ip) VALUES (?, ?)', (city, ip))
                db.commit()
                cur.close()
            else:
                weather = {'error': data.get('message', 'Weather data not found')}
        else:
            try:
                error_message = response.json().get('message', 'City not found')
            except Exception:
                error_message = 'City not found'
            weather = {'error': error_message}

    # Fetch most frequent and most recent searched locations (not used in template, but keep for logic)
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT city, COUNT(*) as freq FROM searches GROUP BY city ORDER BY freq DESC LIMIT 1')
    row = cur.fetchone()
    most_frequent = row[0] if row else None
    cur.execute('SELECT city FROM searches ORDER BY timestamp DESC LIMIT 1')
    row = cur.fetchone()
    most_recent = row[0] if row else None
    cur.close()
    return render_template('index.html', weather=weather)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
