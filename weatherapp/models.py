# weather/models.py
from django.db import models
from django.contrib.auth.models import User


class City(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=2, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

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
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.city_name} - {self.updated_at}"
