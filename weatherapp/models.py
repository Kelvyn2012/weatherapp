# weather/models.py
from django.db import models
from django.contrib.auth.models import User


class City(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=2, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    is_default = models.BooleanField(default=False)  # For geolocation default city

    class Meta:
        verbose_name_plural = "Cities"
        unique_together = ("user", "name")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.name} - {self.user.username}"


class WeatherCache(models.Model):
    city_name = models.CharField(max_length=100, unique=True)
    data = models.JSONField()
    forecast_data = models.JSONField(null=True, blank=True)
    hourly_data = models.JSONField(null=True, blank=True)  # New: hourly forecast
    air_quality_data = models.JSONField(null=True, blank=True)  # New: air quality
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.city_name} - {self.updated_at}"


class WeatherAlert(models.Model):
    city_name = models.CharField(max_length=100)
    alert_type = models.CharField(max_length=50)  # e.g., "Thunderstorm", "Heat Wave"
    severity = models.CharField(
        max_length=20
    )  # "Minor", "Moderate", "Severe", "Extreme"
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.alert_type} - {self.city_name}"
