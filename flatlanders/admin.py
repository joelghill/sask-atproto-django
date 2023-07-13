""" Admin classes for flatlanders app """
from django.contrib import admin
from .models import Post, RegisteredUser


class PostAdmin(admin.ModelAdmin):
    """Admin class for Post"""

    list_display = (
        "uri",
        "cid",
        "author",
        "text",
        "indexed_at",
        "reposts",
        "likes",
        "is_community_match",
    )


class RegisteredUserAdmin(admin.ModelAdmin):
    """Admin class for RegisteredUser"""

    list_display = (
        "did",
        "indexed_at",
        "last_updated",
        "expires_at",
    )


admin.site.register(Post, PostAdmin)
admin.site.register(RegisteredUser, RegisteredUserAdmin)
