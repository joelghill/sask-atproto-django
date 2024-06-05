"""This module contains the models for the flatlanders app."""

from datetime import timedelta

from django.db import models
from django.utils import timezone


class RegisteredUser(models.Model):
    """Represents a registered user"""

    # The DID of the user
    did = models.CharField(max_length=255, primary_key=True)
    # The date the user was indexed
    indexed_at = models.DateTimeField(auto_now_add=True)
    # The date the user was last updated
    last_updated = models.DateTimeField(auto_now=True)
    # Expiry date of the user. Defaults to now, which means the user is expired.
    expires_at = models.DateTimeField(
        default=timezone.now,
        null=True,
    )

    def __str__(self):
        return self.did

    def is_active(self):
        """Returns whether or not the user is active"""
        return self.expires_at is None or self.expires_at > timezone.now()

    def is_registered(self):
        """Returns whether or not the user is registered"""
        return self.expires_at is None

    def register(self):
        """Registers the user"""
        self.expires_at = None
        self.save()

    def expire(self):
        """Expires the user"""
        self.expires_at = timezone.now()
        self.save()

    def extend(self, minutes: int):
        """Extends the expiry date of the user"""
        self.expires_at = timezone.now() + timedelta(minutes=minutes)
        self.save()
