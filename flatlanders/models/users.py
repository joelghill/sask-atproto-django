"""This module contains the models for the flatlanders app."""
from django.db import models


class RegisteredUser(models.Model):
    """Represents a registered user"""

    # The DID of the user
    did = models.CharField(max_length=255, primary_key=True)
    # The date the user was indexed
    indexed_at = models.DateTimeField(auto_now_add=True)
    # The date the user was last updated
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.did
