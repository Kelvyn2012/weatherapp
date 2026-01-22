# weather/admin.py
from django.contrib import admin
from .models import City, WeatherCache


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "user", "added_at")
    list_filter = ("country", "added_at")
    search_fields = ("name", "user__username")
    ordering = ("-added_at",)


@admin.register(WeatherCache)
class WeatherCacheAdmin(admin.ModelAdmin):
    list_display = ("city_name", "updated_at")
    search_fields = ("city_name",)
    ordering = ("-updated_at",)
    readonly_fields = ("data", "forecast_data", "updated_at")
