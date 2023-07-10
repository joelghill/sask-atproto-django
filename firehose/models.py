from django.db import models

# Subscription State model
class SubscriptionState(models.Model):
    """Subscription State model
    Records the current state of a subscription to the ATP feed.
    """
    service = models.CharField(max_length=255, unique=True)
    cursor = models.IntegerField()