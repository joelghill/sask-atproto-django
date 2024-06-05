from enum import StrEnum

from django.db import models


class SKPoliLabels(StrEnum):
    """ Labels used in Sask Politics labelling"""

    POLITICAL_PARTY = "skpoli-political-party"
    POLITICIAN = "skpoli-politician"
    POLITICAL_CONTENT = "skpoli-content"


# Subscription State model
class LabelerCursorState(models.Model):
    """Subscription State model
    Records the current state of a subscription to the ATP feed.
    """

    labeler_service = models.CharField(max_length=255, unique=True)
    cursor = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.labeler_service} - {self.cursor.isoformat() if self.cursor else None}"
