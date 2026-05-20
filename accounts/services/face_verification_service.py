# =============================================================================
# accounts/services/face_verification_service.py
#
# PURPOSE:
#   Handles the server-side part of face verification.
#   The actual face comparison happens in the browser using face-api.js.
#   This service only marks the user as verified after the browser confirms
#   the faces match.
#
# FLOW:
#   1. Browser runs face-api.js → compares selfie vs ID photo
#   2. If match → browser calls POST /api/accounts/verify-identity/confirm/
#   3. This service marks user.is_verified = True
# =============================================================================

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def mark_user_verified(user) -> bool:
    """
    Mark a user as identity-verified.

    Called after face-api.js confirms a successful face match in the browser.
    Sets is_verified=True and records the timestamp.

    Returns:
        True if successfully marked
        False if already verified
    """
    if user.is_verified:
        logger.info('User already verified | user=%s', user.id)
        return False

    user.is_verified = True
    user.verified_at = timezone.now()
    user.save(update_fields=['is_verified', 'verified_at'])

    logger.info(
        'User verified successfully | user=%s verified_at=%s',
        user.id, user.verified_at,
    )
    return True


def is_user_verified(user) -> bool:
    """
    Check if a user has completed identity verification.

    Used by signing_service.py before allowing contract signatures.

    Returns:
        True if verified
        False if not verified
    """
    return user.is_verified