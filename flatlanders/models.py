""" This module contains the models for the flatlanders app. """
from django.db import models


class Post(models.Model):
    """Represents a post from a user"""

    # The URI of the post
    uri = models.CharField(max_length=255, primary_key=True)
    # The CID of the post
    cid = models.CharField(max_length=255)
    # Author of the post. Relationship to RegsiteredUser
    author = models.ForeignKey(
        "RegisteredUser", on_delete=models.CASCADE, related_name="posts"
    )
    # Post text
    text = models.TextField()
    # The parent of the post
    reply_parent = models.CharField(max_length=255, null=True)
    # The root of the post
    reply_root = models.CharField(max_length=255, null=True)
    # The date the post was indexed
    indexed_at = models.DateTimeField(auto_now_add=True)
    # number of reposts
    reposts = models.IntegerField(default=0)
    # number of likes
    likes = models.IntegerField(default=0)
    # Whether or not the post matched the algorithm
    is_community_match = models.BooleanField(default=False)


class RegisteredUser(models.Model):
    """Represents a registered user"""

    # The DID of the user
    did = models.CharField(max_length=255, primary_key=True)
    # The date the user was indexed
    indexed_at = models.DateTimeField(auto_now_add=True)
    # The date the user was last updated
    last_updated = models.DateTimeField(auto_now=True)
    # Expiry date of the user
    expires_at = models.DateTimeField(null=True)
