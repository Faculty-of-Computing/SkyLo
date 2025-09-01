# SkyLo: A Weather Web Application.

## Problem Statement: Create a web-based weather application that displays current weather conditions and forecasts for a given location.

# Weather Web Application

SkyLo is a web-based weather application built with Flask and PostgreSQL, providing real-time weather updates for cities worldwide. It integrates with the OpenWeatherMap API to fetch weather data and displays it with an interactive map powered by Leaflet. The application caches data in a PostgreSQL database to optimize API usage and supports geolocation-based city detection using the user's IP address. This project is hosted on Railway.com for both the frontend and the database.

## Features

- Real-Time Weather Data: Displays current temperature, humidity, wind speed, pressure, visibility, and weather description for any city.
- Interactive Map: Utilizes Leaflet to display the city's location, accompanied by a popup containing weather details.
- IP-Based Geolocation: Automatically detects the user's city using the ip-api.com service if no city is specified.
- Data Caching: Stores weather data in a PostgreSQL database, updating only when data is older than 30 minutes to reduce API calls.
- Responsive Design: Adapts to various screen sizes for a seamless experience on mobile and desktop devices.
- Error Handling: Gracefully handles invalid city inputs and API errors with user-friendly messages.
- Secure Configuration: Utilizes environment variables for sensitive data, such as API keys and database URLs, which are managed via Railway's dashboard.

## Technologies Used

- Backend: Flask (Python web framework), PostgreSQL (database), psycopg2 (PostgreSQL adapter)
- Frontend: HTML, CSS, JavaScript, Leaflet (interactive maps)
- APIs: OpenWeatherMap (weather data), ip-api.com (geolocation)
- Deployment: Gunicorn (WSGI server), Railway.com (hosting platform for frontend and database)
- Other Libraries: pycountry (country name conversion), python-dotenv (environment variable management)

## How It Works

1. Enter a location in the search bar
2. The app fetches weather data from OpenWeatherMap
3. Results are displayed with current conditions and forecast
4. Most searched and recent locations are saved in the database for quick access

## Setup & Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Open your browser and go to `http://localhost:5000`

## Database

- `weather.db` stores search history and statistics

## License

This project is for educational purposes only.

## Acknowledgements

- OpenWeatherMap for weather data.
- ip-api.com for geolocation services.
- Leaflet for interactive maps.
- Railway for seamless hosting and database management.

## Developers
Developed by 0'22/0'23 computer Science Group_4 for 200L UUY-CSC222 Project, University of Uyo, Uyo. 
