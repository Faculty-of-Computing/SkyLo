import os
import time
import sqlite3
import requests
from flask import Flask, g, render_template, request, session, redirect, url_for, flash, make_response, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import quote_plus
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app initialization
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))  # Secure random key for development
app.config['DATABASE'] = os.environ.get('DATABASE_PATH', 'weather.db')
app.config['API_KEY'] = os.environ.get('OPENWEATHER_API_KEY', 'ef0cc4d3880644acbd65f6218a3beed6')  # Use env var in production
app.config['SESSION_COOKIE_SECURE'] = False  # Set to False for local development (no HTTPS)
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # Session timeout (30 minutes)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Prevent CSRF issues
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Enhance security

# Database connection management
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'], timeout=10)
        db.row_factory = sqlite3.Row  # Enable row access by column name
        db.execute('PRAGMA journal_mode=WAL;')
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Database initialization
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather (
                city TEXT PRIMARY KEY,
                temperature REAL,
                description TEXT,
                humidity INTEGER,
                windspeed REAL,
                pressure REAL,
                visibility REAL,
                icon TEXT,
                last_updated INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        db.commit()
        logger.info("Database initialized or verified")
        cursor.close()

# Weather icon mapping
def get_cloud(icon_code):
    mapping = {
        '01d': 'sunny', '01n': 'moon',
        '02d': 'cloudy', '02n': 'cloudy',
        '03d': 'scattered', '03n': 'scattered',
        '04d': 'broken', '04n': 'broken',
        '09d': 'rainy', '09n': 'rainy',
        '10d': 'rainy', '10n': 'rainy',
        '11d': 'thunder', '11n': 'thunder',
        '13d': 'snowy', '13n': 'snowy',
        '50d': 'foggy', '50n': 'foggy'
    }
    return mapping.get(icon_code, 'cloudy')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.info(f"Checking session: username={session.get('username')}")
        if 'username' not in session:
            logger.warning("No username in session, redirecting to login")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        logger.info(f"Login attempt for username: {username}")
        if not username or not password:
            error = 'Username and password are required.'
        else:
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
                user = cursor.fetchone()
                if user and check_password_hash(user['password'], password):
                    session['username'] = username
                    session.permanent = True  # Enable session timeout
                    logger.info(f"Login successful for {username}, session set: {session}")
                    flash('Login successful!', 'success')
                    return redirect(url_for('index'))
                else:
                    error = 'Invalid username or password.'
                    logger.warning(f"Login failed for {username}: Invalid credentials")
            except sqlite3.Error as e:
                logger.error(f"Database error during login: {e}")
                error = 'An error occurred. Please try again.'
            finally:
                cursor.close()
    response = make_response(render_template('login.html', error=error))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            error = 'Username and password are required.'
        else:
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, generate_password_hash(password))
                )
                db.commit()
                logger.info(f"User {username} signed up successfully")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = 'Username already exists.'
                logger.warning(f"Signup failed: Username {username} already exists")
            except sqlite3.Error as e:
                logger.error(f"Database error during signup: {e}")
                error = 'An error occurred. Please try again.'
            finally:
                cursor.close()
    response = make_response(render_template('signup.html', error=error))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User {username} logged out, session cleared: {session}")
    flash('You have been logged out.', 'info')
    response = make_response(redirect(url_for('login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory('static', filename)
    except FileNotFoundError:
        logger.error(f"Static file not found: {filename}")
        return "Static file not found", 404

@app.route('/', methods=['GET'])
@login_required
def index():
    weather = None
    city = request.args.get('city', type=str)
    if not city:
        try:
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            geo_resp = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
            geo_resp.raise_for_status()
            city = geo_resp.json().get('city', 'London')  # Changed fallback to London for reliability
            logger.info(f"Detected city from IP: {city}")
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch city from IP: {e}")
            city = 'London'  # More reliable fallback city

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM weather WHERE city = ?", (city,))
        row = cursor.fetchone()
        current_time = int(time.time())

        if row and current_time - row['last_updated'] < 1800:
            weather = {
                'city': row['city'],
                'temperature': row['temperature'],
                'description': row['description'],
                'humidity': row['humidity'],
                'windspeed': row['windspeed'],
                'pressure': row['pressure'],
                'visibility': row['visibility'] / 1000,  # Convert meters to kilometers
                'icon': row['icon'],
            }
            logger.info(f"Retrieved weather data for {city} from database")
        else:
            # Fetch from OpenWeatherMap API with retry
            city_encoded = quote_plus(city)
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={app.config['API_KEY']}&units=metric"
            for attempt in range(3):  # Retry up to 3 times
                try:
                    response = requests.get(url, timeout=5)
                    response.raise_for_status()
                    data = response.json()
                    if data.get('cod') == '404':
                        weather = {'error': 'City not found.'}
                        logger.warning(f"City not found: {city}")
                        break
                    elif data.get('main') and data.get('weather'):
                        weather = {
                            'temperature': data['main']['temp'],
                            'description': data['weather'][0]['description'].capitalize(),
                            'visibility': data['visibility'] / 1000,  # Convert to kilometers
                            'windspeed': data['wind'].get('speed', 0),
                            'humidity': data['main']['humidity'],
                            'pressure': data['main']['pressure'],
                            'city': data['name'],
                            'icon': get_cloud(data['weather'][0]['icon'])
                        }
                        cursor.execute('''
                            INSERT OR REPLACE INTO weather (city, temperature, description, humidity, windspeed, pressure, visibility, icon, last_updated) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            weather['city'], weather['temperature'], weather['description'],
                            weather['humidity'], weather['windspeed'], weather['pressure'],
                            weather['visibility'] * 1000, weather['icon'], current_time
                        ))
                        db.commit()
                        logger.info(f"Fetched and stored weather data for {city} from API")
                        break
                    else:
                        weather = {'error': 'Invalid response from weather service.'}
                        logger.error(f"Invalid API response for {city}")
                        break
                except requests.RequestException as e:
                    logger.warning(f"API request failed (attempt {attempt + 1}/3): {e}")
                    if attempt == 2:  # Last attempt failed
                        weather = {'error': 'Unable to fetch weather data after multiple attempts.'}
                    time.sleep(2 ** attempt)  # Exponential backoff
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        weather = {'error': 'Database error occurred. Using default data.'}
        weather = {
            'city': 'London',
            'temperature': 15.0,
            'description': 'Cloudy',
            'humidity': 70,
            'windspeed': 5.0,
            'pressure': 1013,
            'visibility': 10.0,
            'icon': 'cloudy'
        }  # Default weather data
    finally:
        cursor.close()

    # Ensure weather is always provided
    if weather is None:
        logger.warning("No weather data available, using default data")
        weather = {
            'city': 'London',
            'temperature': 15.0,
            'description': 'Cloudy',
            'humidity': 70,
            'windspeed': 5.0,
            'pressure': 1013,
            'visibility': 10.0,
            'icon': 'cloudy'
        }

    logger.info(f"Rendering index with weather: {weather}, city: {city}, username: {session.get('username')}")
    response = make_response(render_template('index.html', weather=weather, username=session.get('username')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)  # Disable debug in production