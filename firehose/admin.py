""" Admin configuration for firehose app """
from django.contrib import admin

# Register The subscription state here
from .models import SubscriptionState


class SubscriptionStateAdmin(admin.ModelAdmin):
    """ Admin class for SubscriptionState
    """
    list_display = ('service', 'cursor')


admin.site.register(SubscriptionState, SubscriptionStateAdmin)
