import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import City, WeatherCache


@login_required
def add_city(request):
    if request.method == "POST":
        city_name = request.POST.get("city_name")
        if city_name:
            # Verify city exists by fetching weather
            weather_data, _, error = get_weather_data(city_name, use_cache=False)
            if weather_data:
                City.objects.get_or_create(
                    user=request.user,
                    name=weather_data["city"],
                    defaults={"country": weather_data.get("country", "")},
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
        weather_data, _, _ = get_weather_data(city.name)
        if weather_data:
            cities_weather.append({"id": city.id, "data": weather_data})

    return render(
        request,
        "weather/dashboard.html",
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
    return render(request, "weather/register.html", {"form": form})


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
    return render(request, "weather/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect("index")
