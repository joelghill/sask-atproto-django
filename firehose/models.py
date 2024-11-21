import logging

from django.db import models

logger = logging.getLogger("feed")


# Subscription State model
class SubscriptionState(models.Model):
    """Subscription State model
    Records the current state of a subscription to the ATP feed.
    """

    service = models.CharField(max_length=255, unique=True)
    cursor = models.FloatField(default=0.0)

    def __str__(self) -> str:
        return f"{self.service} - {self.cursor}"
