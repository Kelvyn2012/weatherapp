import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import City, WeatherCache

API_KEY = "YOUR_API_KEY_HERE"  # Replace with your OpenWeatherMap API key


def get_weather_data(city_name, use_cache=True):
    """Fetch weather data with caching (30 minutes)"""
    if use_cache:
        try:
            cache = WeatherCache.objects.get(city_name=city_name.lower())
            if timezone.now() - cache.updated_at < timedelta(minutes=30):
                return cache.data, cache.forecast_data, None
        except WeatherCache.DoesNotExist:
            pass

    # Fetch current weather
    current_url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_KEY}&units=metric"
    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={API_KEY}&units=metric"

    try:
        current_response = requests.get(current_url, timeout=5)
        forecast_response = requests.get(forecast_url, timeout=5)

        if current_response.status_code == 200 and forecast_response.status_code == 200:
            current_data = current_response.json()
            forecast_data = forecast_response.json()

            # Process forecast data to get daily forecasts
            daily_forecasts = {}
            for item in forecast_data["list"]:
                date = item["dt_txt"].split(" ")[0]
                if date not in daily_forecasts:
                    daily_forecasts[date] = {
                        "temp_min": item["main"]["temp_min"],
                        "temp_max": item["main"]["temp_max"],
                        "description": item["weather"][0]["description"],
                        "icon": item["weather"][0]["icon"],
                        "date": date,
                    }
                else:
                    daily_forecasts[date]["temp_min"] = min(
                        daily_forecasts[date]["temp_min"], item["main"]["temp_min"]
                    )
                    daily_forecasts[date]["temp_max"] = max(
                        daily_forecasts[date]["temp_max"], item["main"]["temp_max"]
                    )

            processed_forecast = list(daily_forecasts.values())[:5]

            weather_data = {
                "city": current_data["name"],
                "country": current_data["sys"]["country"],
                "temperature": round(current_data["main"]["temp"], 1),
                "feels_like": round(current_data["main"]["feels_like"], 1),
                "description": current_data["weather"][0]["description"],
                "icon": current_data["weather"][0]["icon"],
                "humidity": current_data["main"]["humidity"],
                "wind_speed": current_data["wind"]["speed"],
                "pressure": current_data["main"]["pressure"],
            }

            # Update cache
            WeatherCache.objects.update_or_create(
                city_name=city_name.lower(),
                defaults={"data": weather_data, "forecast_data": processed_forecast},
            )

            return weather_data, processed_forecast, None
        else:
            return None, None, "City not found. Please try again."
    except Exception as e:
        return None, None, f"Error fetching weather data: {str(e)}"


def index(request):
    weather_data = None
    forecast_data = None
    error_message = None
    user_cities = []

    if request.user.is_authenticated:
        user_cities = City.objects.filter(user=request.user)

    if request.method == "POST":
        city = request.POST.get("city")
        if city:
            weather_data, forecast_data, error_message = get_weather_data(city)

    return render(
        request,
        "weather/index.html",
        {
            "weather_data": weather_data,
            "forecast_data": forecast_data,
            "error_message": error_message,
            "user_cities": user_cities,
        },
    )
