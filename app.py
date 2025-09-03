import psycopg2
import time
import requests
from flask import Flask, g, render_template, request, send_from_directory, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix  # Added for proper IP handling
import pycountry  # Requires installation: pip install pycountry
from urllib.parse import quote_plus
from psycopg2 import pool
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # Handle X-Forwarded-For for proxies
API_KEY = os.getenv('API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

# Initialize connection pool using DATABASE_URL
db_pool = psycopg2.pool.SimpleConnectionPool(1, 20, DATABASE_URL)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = db_pool.getconn()
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Create weather table
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
                last_updated INTEGER,
                lon REAL,
                lat REAL
            )
        ''')
        # Create IP cache table to store IP-to-city mappings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_cache (
                ip TEXT PRIMARY KEY,
                city TEXT,
                country TEXT,
                last_updated INTEGER
            )
        ''')
        db.commit()
        cursor.close()

def get_cloud(c):
    if c == '01d':
        return 'sunny'
    elif c == '01n':
        return 'moon'
    elif c == '02d' or c == '02n':
        return 'cloudy'
    elif c == '03d' or c == '03n':
        return 'scattered'
    elif c == '04d' or c == '04n':
        return 'broken'
    elif c == '09d' or c == '09n':
        return 'rainy'
    elif c == '10d' or c == '10n':
        return 'rainy'
    elif c == '11d' or c == '11n':
        return 'thunder'
    elif c == '13d' or c == '13n':
        return 'snowy'
    elif c == '50d' or c == '50n':
        return 'foggy'
    else:
        return 'cloudy'

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db_pool.putconn(db)

@app.route('/', methods=['GET'])
def index():
    weather = {}
    if request.method == 'GET':
        city = request.args.get('city', type=str)
        if not city:
            try:
                # Get client IP, accounting for proxies
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                print(f"Client IP: {ip}")  # Debug log
                conn = get_db()
                cursor = conn.cursor()
                
                # Check IP cache
                cursor.execute("SELECT city, last_updated FROM ip_cache WHERE ip = %s", (ip,))
                ip_cache = cursor.fetchone()
                current_time = int(time.time())
                
                if ip_cache and (current_time - ip_cache[1] < 86400):  # Cache valid for 24 hours
                    city = ip_cache[0]
                    print(f"Using cached city for IP {ip}: {city}")
                else:
                    # Try ip-api.com first
                    geo_resp = requests.get(f'http://ip-api.com/json/{ip}')
                    print(f"ip-api.com response: {geo_resp.status_code}, {geo_resp.text}")  # Debug log
                    if geo_resp.status_code == 200:
                        geo_data = geo_resp.json()
                        if geo_data.get('status') != 'fail':
                            city = geo_data.get('city', 'Uyo')
                            country = geo_data.get('country', 'Unknown Country')
                        else:
                            city = 'Uyo'
                            country = 'Unknown Country'
                    else:
                        # Fallback to ipinfo.io
                        geo_resp = requests.get(f'https://ipinfo.io/{ip}/json')
                        print(f"ipinfo.io response: {geo_resp.status_code}, {geo_resp.text}")  # Debug log
                        if geo_resp.status_code == 200:
                            geo_data = geo_resp.json()
                            city = geo_data.get('city', 'Uyo')
                            country = geo_data.get('country', 'Unknown Country')
                            if country and len(country) == 2:  # Convert country code to name
                                country = pycountry.countries.get(alpha_2=country).name if pycountry.countries.get(alpha_2=country) else 'Unknown Country'
                        else:
                            city = 'Uyo'
                            country = 'Unknown Country'
                    
                    # Update IP cache
                    cursor.execute('''
                        INSERT INTO ip_cache (ip, city, country, last_updated)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (ip) DO UPDATE
                        SET city = EXCLUDED.city,
                            country = EXCLUDED.country,
                            last_updated = EXCLUDED.last_updated
                    ''', (ip, city, country, current_time))
                    conn.commit()
                
                cursor.close()
            except Exception as e:
                print(f"Geolocation error: {e}")
                city = 'Uyo'

        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM weather WHERE city ILIKE %s", (city,))
            row = cursor.fetchone()
            
            current_time = int(time.time())
            if row and (current_time - row[8] < 1800):  # Check if data is fresh (30 minutes)
                weather = {
                    'city': row[0],
                    'temperature': int(row[1]),
                    'description': row[2],
                    'humidity': row[3],
                    'windspeed': row[4],
                    'pressure': row[5],
                    'visibility': row[6],
                    'icon': row[7],
                    'lon': row[9],
                    'lat': row[10],
                    'key': API_KEY,
                }
                cursor.close()
                return render_template("index.html", weather=weather)
            
            # Fetch new weather data from API
            city_encoded = quote_plus(city)
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={API_KEY}&units=metric"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('sys') and not data.get('main'):
                    weather = {'error': 'This is not a valid city', 'icon': 'cloudy', 'lat': 0.0, 'lon': 0.0}
                    cursor.close()
                    return render_template("index.html", weather=weather)
                
                if data.get('main') and data.get('weather'):
                    country_code = data['sys']['country']
                    country_name = pycountry.countries.get(alpha_2=country_code).name if pycountry.countries.get(alpha_2=country_code) else 'Unknown Country'
                    weather = {
                        'temperature': int(data['main']['temp']),
                        'description': data['weather'][0]['description'],
                        'visibility': data['visibility'],
                        'windspeed': data['wind']['speed'],
                        'humidity': data['main']['humidity'],
                        'pressure': data['main']['pressure'],
                        'city': f"{data['name']}, {country_name}",
                        'icon': get_cloud(data['weather'][0]['icon']),
                        'lon': data['coord']['lon'],
                        'lat': data['coord']['lat'],
                        'key': API_KEY,
                    }
                    
                    cursor.execute('''
                        INSERT INTO weather (city, temperature, description, humidity, windspeed, pressure, visibility, icon, last_updated, lon, lat)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (city) DO UPDATE
                        SET temperature = EXCLUDED.temperature,
                            description = EXCLUDED.description,
                            humidity = EXCLUDED.humidity,
                            windspeed = EXCLUDED.windspeed,
                            pressure = EXCLUDED.pressure,
                            visibility = EXCLUDED.visibility,
                            icon = EXCLUDED.icon,
                            last_updated = EXCLUDED.last_updated,
                            lon = EXCLUDED.lon,
                            lat = EXCLUDED.lat
                    ''', (weather['city'], weather['temperature'], weather['description'], weather['humidity'], weather['windspeed'], weather['pressure'], weather['visibility'], weather['icon'], current_time, weather['lon'], weather['lat']))
                    conn.commit()
                    cursor.close()
                    return render_template("index.html", weather=weather)
                else:
                    weather = {'error': 'City not Found', 'icon': 'cloudy', 'lat': 0.0, 'lon': 0.0}
                    cursor.close()
                    return render_template("index.html", weather=weather)
            else:
                weather = {'error': 'City not Found', 'icon': 'cloudy', 'lat': 0.0, 'lon': 0.0}
                cursor.close()
                return render_template("index.html", weather=weather)
        
        except Exception as e:
            print(f"Weather API error: {e}")
            weather = {'error': 'Unexpected exception', 'icon': 'cloudy', 'lat': 0.0, 'lon': 0.0}
            if 'cursor' in locals():
                cursor.close()
            return render_template("index.html", weather=weather)

@app.route('/images/<path:filename>')
def image_handler(filename):
    return send_from_directory('static/img', filename)

@app.route('/latlng', methods=['POST'])
def handle_latlng():
    try:
        body = request.get_json()
        lat = body['lat']
        lng = body['lng']
        
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&exclude=daily,hourly&appid={API_KEY}&units=metric"
        response = requests.get(url)
       
        if response.status_code == 200:
            data = response.json()
            weather = {
                'temperature': int(data['main']['temp']),
                'description': data['weather'][0]['description'],
                'city': data['name'],
            }
            return jsonify(weather)
        return jsonify({'error': 'No data'})
    except Exception as e:
        print(f"LatLng API error: {e}")
        return jsonify({'error': 'Unexpected exception'})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)