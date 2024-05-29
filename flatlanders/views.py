from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views import View

from flatlanders.algorithms import ALGORITHMS


class DidJson(View):
    """View that gets the well known DID JSON for the feed generator"""

    def get(self, _):
        """Return the well known DID JSON for the feed generator"""

        response_data = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": settings.FEEDGEN_SERVICE_DID,
            "service": [
                {
                    "id": "#bsky_fg",
                    "type": "BskyFeedGenerator",
                    "serviceEndpoint": f"https://{settings.FEEDGEN_HOSTNAME}",
                }
            ],
        }
        return JsonResponse(response_data)


class DescribeFeedGenerator(View):
    """View that describes the feed generator"""

    def get(self, _):
        """Return the description of the feed generator"""
        feeds = [{"uri": uri} for uri in ALGORITHMS]
        response_data = {"did": settings.FEEDGEN_SERVICE_DID, "feeds": feeds}

        return JsonResponse(response_data)


class FeedSkeleton(View):
    """View that returns the feed skeleton"""

    def get(self, request):
        """Return the feed skeleton for a given algorithm"""
        uri = request.GET.get("feed", None)

        if uri not in ALGORITHMS:
            return HttpResponse("Unsupported algorithm", status=400)

        try:
            cursor = request.GET.get("cursor", None)
            limit = request.GET.get("limit", "20")
            # Convert limit to int
            limit = int(limit)
            body = ALGORITHMS[uri](cursor=cursor, limit=limit)
        except ValueError as error:
            return HttpResponse(f"Malformed cursor:{error}", status=400)

        return JsonResponse(body)
