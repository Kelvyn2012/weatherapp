# weather/views.py
import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import City, WeatherCache

API_KEY = settings.OPENWEATHER_API_KEY


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
