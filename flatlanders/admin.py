"""Admin classes for flatlanders app"""

from django.contrib import admin

from flatlanders.models.labelers import LabelerCursorState
from flatlanders.models.posts import Post
from flatlanders.models.users import RegisteredUser


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
    )

    search_fields = ("did",)


class LabelerCursorStateAdmin(admin.ModelAdmin):
    """Admin class for labelerCursorState"""

    list_display = (
        "labeler_service",
        "cursor",
    )

    search_fields = ("labeler_service",)


admin.site.register(Post, PostAdmin)
admin.site.register(RegisteredUser, RegisteredUserAdmin)
admin.site.register(LabelerCursorState, LabelerCursorStateAdmin)
