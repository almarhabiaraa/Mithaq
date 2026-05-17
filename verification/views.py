# =============================================================================
# verification/views.py
# OWNED BY: Ghadi
# (added by ghadi: public contract verification feature — no login needed)
#
# PURPOSE:
#   Two views that together make the verification feature work:
#     1. PublicVerifyAPIView  — a JSON API called by JavaScript
#     2. VerifyPageView       — the HTML page a human actually visits
#
# HOW THE FEATURE WORKS END-TO-END:
#   User opens /verify/ → sees the HTML page (VerifyPageView)
#   User types a 64-char hash and clicks "تحقق الآن"
#   JavaScript calls GET /api/verify/<hash>/ (PublicVerifyAPIView)
#   The API calls verify_contract_hash() in services.py
#   The API returns a JSON result (always HTTP 200)
#   JavaScript reads verification_status and shows the right card
#
# SECURITY NOTES:
#   - permission_classes = [] is intentional — this is a PUBLIC endpoint
#   - AnonRateThrottle limits to 60 requests/hour per IP (see settings.py)
#   - The API always returns HTTP 200, never 404 — returning 404 for
#     unknown hashes would let attackers enumerate existing hashes
#
# URL MAP (registered in Mithaq/urls.py by Ghadi):
#   GET /verify/                → VerifyPageView   (HTML page for humans)
#   GET /api/verify/<hash>/     → PublicVerifyAPIView (JSON for JavaScript)
# =============================================================================

from django.views.generic import TemplateView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .serializers import VerificationResultSerializer
from .services import verify_contract_hash


class PublicVerifyAPIView(APIView):
    """
    GET /api/verify/<hash_hex>/

    Public JSON endpoint — no authentication required.
    Called by the JavaScript in verify.html when the user submits a hash.

    Throttled: 60 requests/hour per IP via AnonRateThrottle.
    Always returns HTTP 200 — see security note in the file header above.
    """

    # Intentionally empty — this endpoint is public by design
    permission_classes = []

    # Rate limiting to prevent abuse (configured in settings.REST_FRAMEWORK)
    throttle_classes = [AnonRateThrottle]

    def get(self, request, hash_hex):
        # All verification logic lives in services.py — view stays thin
        result = verify_contract_hash(hash_hex)
        serializer = VerificationResultSerializer(result)
        # Always 200 — never 404 (prevents hash enumeration)
        return Response(serializer.data)


class VerifyPageView(TemplateView):
    """
    GET /verify/

    Public HTML page — no authentication required.
    Renders verify.html and passes the API base URL as context
    so the JavaScript knows where to send its fetch() calls.
    """

    template_name = 'verification/verify.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Injected into verify.html as {{ api_url }} → used by JS fetch()
        ctx['api_url'] = '/api/verify/'
        return ctx
