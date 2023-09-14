""" Admin classes for flatlanders app """
from django.contrib import admin
from .models import Post, RegisteredUser


class PostAdmin(admin.ModelAdmin):
    """Admin class for Post"""

    list_display = (
        "uri",
        "is_community_match",
        "text",
        "indexed_at",
        "created_at",
    )

    search_fields = ("uri", "text", "author__did")


class RegisteredUserAdmin(admin.ModelAdmin):
    """Admin class for RegisteredUser"""

    list_display = (
        "did",
        "indexed_at",
        "last_updated",
        "expires_at",
    )

    search_fields = ("did",)


admin.site.register(Post, PostAdmin)
admin.site.register(RegisteredUser, RegisteredUserAdmin)
