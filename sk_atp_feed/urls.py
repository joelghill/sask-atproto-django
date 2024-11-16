"""sk_atp_feed URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from flatlanders.views import DescribeFeedGenerator, DidJson, FeedSkeleton

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django.contrib.auth.urls")),
    path(".well-known/did.json", DidJson.as_view(), name="well_known_did"),
    path(
        "xrpc/app.bsky.feed.describeFeedGenerator",
        DescribeFeedGenerator.as_view(),
        name="describe_feed_generator",
    ),
    path(
        "xrpc/app.bsky.feed.getFeedSkeleton",
        FeedSkeleton.as_view(),
        name="get_feed_skeleton",
    ),
]
