# weatherapp/views.py
from django.http import JsonResponse
import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime
from .models import City, WeatherCache

API_KEY = settings.OPENWEATHER_API_KEY


def get_air_quality(lat, lon):
    """Fetch air quality data"""
    url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            aqi = data["list"][0]["main"]["aqi"]
            aqi_labels = {
                1: "Good",
                2: "Fair",
                3: "Moderate",
                4: "Poor",
                5: "Very Poor",
            }
            components = data["list"][0]["components"]
            return {
                "aqi": aqi,
                "aqi_label": aqi_labels.get(aqi, "Unknown"),
                "pm2_5": components.get("pm2_5", 0),
                "pm10": components.get("pm10", 0),
                "no2": components.get("no2", 0),
                "o3": components.get("o3", 0),
            }
    except:
        pass
    return None


def get_weather_data(city_name, use_cache=True, lat=None, lon=None):
    """Fetch comprehensive weather data with caching (30 minutes)"""
    if use_cache and city_name:
        try:
            cache = WeatherCache.objects.get(city_name=city_name.lower())
            if timezone.now() - cache.updated_at < timedelta(minutes=30):
                return (
                    cache.data,
                    cache.forecast_data,
                    cache.hourly_data if hasattr(cache, "hourly_data") else None,
                    (
                        cache.air_quality_data
                        if hasattr(cache, "air_quality_data")
                        else None
                    ),
                    None,
                )
        except WeatherCache.DoesNotExist:
            pass

    # Build URLs based on city name or coordinates
    if lat and lon:
        current_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    else:
        current_url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_KEY}&units=metric"
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={API_KEY}&units=metric"

    try:
        current_response = requests.get(current_url, timeout=5)
        forecast_response = requests.get(forecast_url, timeout=5)

        if current_response.status_code == 200 and forecast_response.status_code == 200:
            current_data = current_response.json()
            forecast_data = forecast_response.json()

            # Get coordinates for additional data
            lat = current_data["coord"]["lat"]
            lon = current_data["coord"]["lon"]

            # Get air quality
            air_quality = get_air_quality(lat, lon)

            # Get hourly forecast from 5-day forecast
            hourly_forecasts = [
                {
                    "time": item["dt_txt"].split(" ")[1][:5],
                    "temp": round(item["main"]["temp"], 1),
                    "feels_like": round(item["main"]["feels_like"], 1),
                    "description": item["weather"][0]["description"],
                    "icon": item["weather"][0]["icon"],
                    "humidity": item["main"]["humidity"],
                    "wind_speed": item["wind"]["speed"],
                    "pop": int(item.get("pop", 0) * 100),
                }
                for item in forecast_data["list"][:8]
            ]  # First 24 hours (8 x 3-hour intervals)

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
                        "humidity": item["main"]["humidity"],
                        "wind_speed": item["wind"]["speed"],
                    }
                else:
                    daily_forecasts[date]["temp_min"] = min(
                        daily_forecasts[date]["temp_min"], item["main"]["temp_min"]
                    )
                    daily_forecasts[date]["temp_max"] = max(
                        daily_forecasts[date]["temp_max"], item["main"]["temp_max"]
                    )

            processed_forecast = list(daily_forecasts.values())[:5]

            # Check for weather alerts
            alerts = []
            if current_data["weather"][0]["id"] < 600:  # Severe weather codes
                alert_type = current_data["weather"][0]["main"]
                if alert_type in ["Thunderstorm", "Drizzle", "Rain", "Snow"]:
                    alerts.append(
                        {
                            "type": alert_type,
                            "severity": (
                                "Moderate"
                                if current_data["weather"][0]["id"] > 500
                                else "Severe"
                            ),
                            "description": current_data["weather"][0][
                                "description"
                            ].capitalize(),
                        }
                    )

            # Build comprehensive weather data
            weather_data = {
                "city": current_data["name"],
                "country": current_data["sys"]["country"],
                "latitude": lat,
                "longitude": lon,
                "temperature": round(current_data["main"]["temp"], 1),
                "feels_like": round(current_data["main"]["feels_like"], 1),
                "temp_min": round(current_data["main"]["temp_min"], 1),
                "temp_max": round(current_data["main"]["temp_max"], 1),
                "description": current_data["weather"][0]["description"],
                "icon": current_data["weather"][0]["icon"],
                "humidity": current_data["main"]["humidity"],
                "wind_speed": current_data["wind"]["speed"],
                "wind_deg": current_data["wind"].get("deg", 0),
                "pressure": current_data["main"]["pressure"],
                "visibility": current_data.get("visibility", 0) / 1000,  # Convert to km
                "clouds": current_data["clouds"]["all"],
                "sunrise": datetime.fromtimestamp(
                    current_data["sys"]["sunrise"]
                ).strftime("%I:%M %p"),
                "sunset": datetime.fromtimestamp(
                    current_data["sys"]["sunset"]
                ).strftime("%I:%M %p"),
                "alerts": alerts,
            }

            # Update cache
            if city_name:
                WeatherCache.objects.update_or_create(
                    city_name=city_name.lower(),
                    defaults={
                        "data": weather_data,
                        "forecast_data": processed_forecast,
                        "hourly_data": hourly_forecasts,
                        "air_quality_data": air_quality,
                    },
                )

            return weather_data, processed_forecast, hourly_forecasts, air_quality, None
        else:
            return None, None, None, None, "City not found. Please try again."
    except Exception as e:
        return None, None, None, None, f"Error fetching weather data: {str(e)}"


def index(request):
    """Main homepage view"""
    weather_data = None
    forecast_data = None
    hourly_data = None
    air_quality = None
    error_message = None
    user_cities = []

    if request.user.is_authenticated:
        user_cities = City.objects.filter(user=request.user)

    if request.method == "POST":
        city = request.POST.get("city")
        if city:
            weather_data, forecast_data, hourly_data, air_quality, error_message = (
                get_weather_data(city)
            )

    return render(
        request,
        "weatherapp/index.html",
        {
            "weather_data": weather_data,
            "forecast_data": forecast_data,
            "hourly_data": hourly_data,
            "air_quality": air_quality,
            "error_message": error_message,
            "user_cities": user_cities,
        },
    )


def get_location_weather(request):
    """API endpoint for geolocation-based weather"""
    if request.method == "POST":
        import json

        data = json.loads(request.body)
        lat = data.get("latitude")
        lon = data.get("longitude")

        if lat and lon:
            weather_data, forecast_data, hourly_data, air_quality, error = (
                get_weather_data(None, use_cache=False, lat=lat, lon=lon)
            )

            if weather_data:
                # Save as default city for logged-in users
                if request.user.is_authenticated:
                    City.objects.update_or_create(
                        user=request.user,
                        name=weather_data["city"],
                        defaults={
                            "country": weather_data["country"],
                            "latitude": lat,
                            "longitude": lon,
                            "is_default": True,
                        },
                    )

                return JsonResponse(
                    {"success": True, "redirect_url": f"/?city={weather_data['city']}"}
                )

        return JsonResponse({"success": False, "error": "Invalid coordinates"})

    return JsonResponse({"success": False, "error": "Invalid request"})


@login_required
def add_city(request):
    if request.method == "POST":
        city_name = request.POST.get("city_name")
        if city_name:
            # Verify city exists by fetching weather
            weather_data, _, _, _, error = get_weather_data(city_name, use_cache=False)
            if weather_data:
                City.objects.get_or_create(
                    user=request.user,
                    name=weather_data["city"],
                    defaults={
                        "country": weather_data.get("country", ""),
                        "latitude": weather_data.get("latitude"),
                        "longitude": weather_data.get("longitude"),
                    },
                )
                messages.success(request, f"{weather_data['city']} added to favorites!")
            else:
                messages.error(request, error or "Could not add city.")
    return redirect("index")


@login_required
def delete_city(request, city_id):
    try:
        city = City.objects.get(id=city_id, user=request.user)
        city.delete()
        messages.success(request, "City removed from favorites.")
    except City.DoesNotExist:
        messages.error(request, "City not found.")
    return redirect("index")


@login_required
def dashboard(request):
    user_cities = City.objects.filter(user=request.user)
    cities_weather = []

    for city in user_cities:
        weather_data, _, _, _, _ = get_weather_data(city.name)
        if weather_data:
            cities_weather.append({"id": city.id, "data": weather_data})

    return render(
        request,
        "weatherapp/dashboard.html",
        {
            "cities_weather": cities_weather,
        },
    )


def register_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful!")
            return redirect("index")
    else:
        form = UserCreationForm()
    return render(request, "weatherapp/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                return redirect("index")
    else:
        form = AuthenticationForm()
    return render(request, "weatherapp/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect("index")
