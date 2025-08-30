
import sqlite3
import time

import requests
from flask import Flask, g, render_template, request, send_from_directory

app = Flask(__name__)
API_KEY = "ef0cc4d3880644acbd65f6218a3beed6"
DATABASE = 'weather.db'

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
           CREATE TABLE IF NOT EXISTS weather(
            city TEXT PRIMARY KEY,
            temperature REAL,
            description TEXT,
            humidity INTEGER,
            windspeed REAL,
            pressure REAL,
            visibility REAL,
            icon TEXT,
            last_updated INTEGER,
            lon Real,
            lat Real
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
        return'snowy'
    elif c == '50d' or c == '50n':
        return 'foggy'
    else:
        return 'cloudy'


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/', methods=['GET'])
def index():
    weather = None
    # Get user's city from IP if not provided
    if request.method == 'GET':
        city = request.args.get('city', type=str)
        if not city:
            try:
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                geo_resp = requests.get(f'http://ip-api.com/json/{ip}')
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
                    city = geo_data.get('city', 'Uyo')
                else:
                    city = 'Uyo'
            except Exception:
                city = 'Uyo'
        try:
            conn = sqlite3.connect("weather.db")
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM weather WHERE city like ?", (city,))
            row = cursor.fetchone()
            
            current_time = int(time.time())
            if row:
            # check if the data is older than 30 minutes (1800 sec)
                if current_time - row[8] < 1800:
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
                        'lat': row[10]
                    }
                    
#                    print(weather)
                    
                    conn.close()
                    return render_template("index.html", weather=weather)
            
            # city not in database and not searched within the 
            # last 30 minutes, get weather report from API
            from urllib.parse import quote_plus
            city_encoded = quote_plus(city)
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={API_KEY}&units=metric"
            response = requests.get(url)
            
#            raise ExceptionType("Error")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if the response is for a country, not a city
                if data.get('sys') and not data.get('main'):
                    weather = { 'error': 'This is not a valid city' }
                    conn.close()
                    return render_template("index.html", weather=weather)
                if data.get('main') and data.get('weather'):
                    weather = {
                        'temperature': int(data['main']['temp']),
                        'description': data['weather'][0]['description'],
                        'visibility': data['visibility'],
                        'windspeed': data['wind']['speed'],
                        'humidity': data['main']['humidity'],
                        'pressure': data['main']['pressure'],
                        'city': data['name'],
                        'icon': get_cloud(data['weather'][0]['icon']),
                        'lon': data['coord']['lon'],
                        'lat': data['coord']['lat'],
                    }
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO weather (city, temperature, description, humidity, windspeed, pressure, visibility, icon, last_updated, lon, lat) 
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (weather['city'], weather['temperature'], weather['description'], weather['humidity'], weather['windspeed'], weather['pressure'], weather['visibility'], weather['icon'], current_time, weather['lon'], weather['lat'],))

                    conn.commit()
                    conn.close()
                    return render_template("index.html", weather=weather)
                else:
                    weather = { 'error': 'City not Found' }
                    conn.close()
                    return render_template("index.html", weather=weather)
            else:
                weather = { 'error': 'City not Found' }
                conn.close()
                return render_template("index.html", weather=weather)
        
        except Exception as e:
            print(e)
            weather = {'error': 'Unexpected exception'}
            return render_template("index.html", weather=weather)


@app.route('/images/<path:filename>')
def image_handler(filename):
    return send_from_directory('static/img', filename)



if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
    
