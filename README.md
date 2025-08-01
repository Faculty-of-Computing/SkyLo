# Weather Web Application

A web-based weather application that allows users to view current weather conditions and forecasts for any location. Built by Group 4 as part of the Faculty of Computing project.

## Features

- Search for weather data by city or location
- View current weather conditions and 5-day forecasts
- User-friendly interface for easy navigation
- Stores most searched and most recently searched locations in a local database

## Technologies Used

- Python (Flask)
- HTML/CSS (templates)
- SQLite for local data storage
- OpenWeatherMap API for weather data

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

- `weather_searches.db` stores search history and statistics

## License

This project is for educational purposes only.
