# =============================================================================
# payments/services/moyasar_service.py
# OWNED BY: Ghadi
#
# PURPOSE:
#   All communication with the Moyasar payment API lives here.
#   Nothing outside this file should ever call the Moyasar API directly.
#
# SANDBOX VS PRODUCTION:
#   Keys are in .env — NEVER put them in code.
#   Current .env uses sandbox keys (sk_test_... / pk_test_...).
#   Before going live: replace with production keys from moyasar.com dashboard.
#   Also update MOYASAR_CALLBACK_URL in .env to the real server domain.
#
# MOYASAR AMOUNTS:
#   Moyasar uses halalas (smallest SAR unit): 1 SAR = 100 halalas.
#   All amounts are multiplied by 100 before sending to the API.
#   Example: plan.price = 99 SAR → API receives amount = 9900
#
# RETRY LOGIC:
#   Both GET and POST calls use a shared session with automatic exponential-
#   backoff retry on transient server errors (429, 500-504) and connection
#   failures. POST requests include an Idempotency-Key header so retrying
#   the same request never creates a duplicate charge on Moyasar.
#
# SECURITY RULES (never break these):
#   - Never trust callback query params alone — always call verify_payment()
#     to re-fetch the real status from Moyasar's API.
#   - Always check amount matches the local PaymentRecord before activating.
#   - SELECT FOR UPDATE on PaymentRecord prevents double-processing.
#
# CALLED FROM:
#   payments/views.py → CheckoutView.post()         → initiate_payment()
#   payments/views.py → PaymentCallbackView.get()   → handle_callback()
#   payments/views.py → WebhookView.post()          → handle_callback()
#
# FUTURE WORK (Ghadi):
#   - Support stcpay and applepay (currently card only)
# =============================================================================

import logging
import uuid

import requests
from django.conf import settings
from django.db import transaction
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from payments.models import PaymentRecord
from subscriptions.models import SubscriptionPlan

logger = logging.getLogger(__name__)

# ── Retry configuration ────────────────────────────────────────────────────────
# These values control how the shared session retries failed requests.
#
_RETRY_TOTAL         = 3      # max attempts after the first failure
_RETRY_BACKOFF       = 0.5    # exponential backoff factor:
                               #   attempt 1 → wait 0.5 s
                               #   attempt 2 → wait 1.0 s
                               #   attempt 3 → wait 2.0 s
_RETRY_ON_STATUSES   = frozenset({429, 500, 502, 503, 504})
                               # 429 = rate-limited, 5xx = Moyasar server errors
                               # 4xx client errors are NOT retried (our fault)
_REQUEST_TIMEOUT     = 10     # seconds per individual attempt


class MoyasarError(Exception):
    """Raised when the Moyasar API is unreachable or returns an unexpected response."""
    pass


# ── Internal helpers ───────────────────────────────────────────────────────────

def _auth() -> tuple:
    """Return HTTP Basic Auth tuple for Moyasar: (secret_key, empty_password)."""
    return (settings.MOYASAR_API_KEY, '')


def _session(retry_post: bool = False) -> requests.Session:
    """
    Build a requests.Session with automatic exponential-backoff retry.

    retry_post:
        Set True only when the POST request carries an Idempotency-Key header,
        making it safe to retry without risking duplicate charges on Moyasar.
        Defaults to False so accidental POST retries without the key are blocked.
    """
    methods = {'GET', 'HEAD', 'OPTIONS'}
    if retry_post:
        methods.add('POST')

    retry = Retry(
        total           = _RETRY_TOTAL,
        backoff_factor  = _RETRY_BACKOFF,
        status_forcelist= _RETRY_ON_STATUSES,
        allowed_methods = methods,
        raise_on_status = False,   # let raise_for_status() handle HTTP errors
    )

    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://',  adapter)   # needed for localhost sandbox testing
    return session


# ── Public service functions ───────────────────────────────────────────────────

def initiate_payment(user, plan: SubscriptionPlan, payment_method: str = 'creditcard') -> str:
    """
    Create a PaymentRecord and call the Moyasar API to open a payment session.

    A temporary unique placeholder is written to moyasar_payment_id so the record
    can be saved before the API call (its ID is included in metadata sent to Moyasar).
    The real Moyasar payment ID replaces it once the API responds successfully.

    Amount is converted from SAR to halalas (× 100) as required by Moyasar.

    An Idempotency-Key header (= payment_record.id) is sent so Moyasar treats
    all retries of the same request as a single payment — no duplicate charges.

    Returns:
        The Moyasar-hosted payment URL to redirect the user to.

    Raises:
        MoyasarError: if the API is unreachable, all retries are exhausted,
                      or the response structure is unexpected.
    """
    amount_halalas = int(plan.price * 100)

    payment_record = PaymentRecord.objects.create(
        user=user,
        plan=plan,
        moyasar_payment_id=f'tmp_{uuid.uuid4().hex}',
        amount=plan.price,
        currency='SAR',
        status=PaymentRecord.Status.INITIATED,
    )

    payload = {
        'amount':       amount_halalas,
        'currency':     'SAR',
        'description':  f'Mithaq - {plan.name_ar}',
        'callback_url': settings.MOYASAR_CALLBACK_URL,
        'source': {
            'type': payment_method,   # 'creditcard', 'stcpay', or 'applepay'
        },
        'metadata': {
            'user_id':            str(user.id),
            'plan_id':            str(plan.id),
            'payment_record_id':  str(payment_record.id),
        },
    }

    logger.info(
        'Initiating Moyasar payment | user=%s plan=%s amount_halalas=%s attempt_max=%s',
        user.id, plan.id, amount_halalas, _RETRY_TOTAL + 1,
    )

    try:
        # retry_post=True is safe here because of the Idempotency-Key header.
        # Moyasar returns the same payment object for the same key on retries.
        response = _session(retry_post=True).post(
            f'{settings.MOYASAR_BASE_URL}/payments',
            json=payload,
            auth=_auth(),
            timeout=_REQUEST_TIMEOUT,
            headers={'Idempotency-Key': str(payment_record.id)},
        )
        logger.info(
            'Moyasar initiate response | http_status=%s body=%.500s',
            response.status_code, response.text,
        )
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        payment_record.delete()
        raise MoyasarError(
            f'Moyasar API timed out after {_REQUEST_TIMEOUT}s '
            f'(tried {_RETRY_TOTAL + 1} time(s))'
        )
    except requests.exceptions.RequestException as exc:
        payment_record.delete()
        raise MoyasarError(f'Moyasar API request failed after retries: {exc}')

    moyasar_id  = data.get('id')
    # Card payments return the hosted-page redirect URL under source.transaction_url
    payment_url = (
        data.get('source', {}).get('transaction_url')
        or data.get('url')
    )

    if not moyasar_id or not payment_url:
        payment_record.delete()
        raise MoyasarError(f'Unexpected Moyasar response structure: {data}')

    payment_record.moyasar_payment_id = moyasar_id
    payment_record.save(update_fields=['moyasar_payment_id'])

    logger.info(
        'PaymentRecord id=%s linked to Moyasar payment_id=%s',
        payment_record.id, moyasar_id,
    )
    return payment_url


def handle_callback(moyasar_payment_id: str) -> str:
    """
    Process a Moyasar payment callback safely.

    Never trusts the callback query parameters alone — always re-fetches the
    payment status from the Moyasar API to verify it.

    Uses SELECT FOR UPDATE on the PaymentRecord to prevent double-processing
    when Moyasar fires the callback more than once.

    Performs an amount integrity check: if the amount Moyasar reports does not
    match what was stored locally (in halalas), the payment is rejected and
    logged as a warning without activating the subscription.

    Returns:
        'paid'      — payment verified, subscription activated.
        'failed'    — payment failed, cancelled, or amount mismatch.
        'refunded'  — payment was refunded; PaymentRecord marked REFUNDED.
        'initiated' — payment still pending (no action taken).

    Raises:
        ValueError:    if no matching PaymentRecord exists locally.
        MoyasarError:  if the Moyasar verification API call fails.
    """
    from subscriptions.services.subscription_service import activate_subscription

    logger.info('Handling callback | moyasar_payment_id=%s', moyasar_payment_id)

    moyasar_data   = verify_payment(moyasar_payment_id)
    moyasar_status = moyasar_data.get('status', '').lower()
    moyasar_amount = moyasar_data.get('amount')   # in halalas

    logger.info(
        'Moyasar verified | payment_id=%s status=%s amount_halalas=%s',
        moyasar_payment_id, moyasar_status, moyasar_amount,
    )

    with transaction.atomic():
        try:
            record = (
                PaymentRecord.objects
                .select_for_update()
                .select_related('user', 'plan')
                .get(moyasar_payment_id=moyasar_payment_id)
            )
        except PaymentRecord.DoesNotExist:
            logger.error('No PaymentRecord found | moyasar_payment_id=%s', moyasar_payment_id)
            raise ValueError(f'PaymentRecord not found for Moyasar ID: {moyasar_payment_id}')

        # Idempotency: already in a terminal state — skip processing
        if record.status == PaymentRecord.Status.PAID:
            logger.info('Payment already PAID, skipping | payment_id=%s', moyasar_payment_id)
            return 'paid'
        if record.status == PaymentRecord.Status.REFUNDED:
            logger.info('Payment already REFUNDED, skipping | payment_id=%s', moyasar_payment_id)
            return 'refunded'

        # Amount integrity check (local SAR × 100 must match Moyasar halalas)
        expected_halalas = int(record.amount * 100)
        if moyasar_amount != expected_halalas:
            logger.warning(
                'Amount mismatch — NOT activating | expected=%s moyasar=%s payment_id=%s',
                expected_halalas, moyasar_amount, moyasar_payment_id,
            )
            record.status = PaymentRecord.Status.FAILED
            record.save(update_fields=['status', 'updated_at'])
            return 'failed'

        if moyasar_status == 'paid':
            record.status = PaymentRecord.Status.PAID
            record.save(update_fields=['status', 'updated_at'])
            activate_subscription(record.user, record.plan)
            logger.info('Subscription activated | user=%s plan=%s', record.user.id, record.plan.id)
            return 'paid'

        if moyasar_status == 'refunded':
            record.status = PaymentRecord.Status.REFUNDED
            record.save(update_fields=['status', 'updated_at'])
            logger.info(
                'Payment refunded by Moyasar | user=%s payment_id=%s',
                record.user.id, moyasar_payment_id,
            )
            # Subscription is intentionally left active after a refund.
            # Deactivating it is a business decision for manual or admin action.
            return 'refunded'

        if moyasar_status in ('failed', 'cancelled'):
            record.status = PaymentRecord.Status.FAILED
            record.save(update_fields=['status', 'updated_at'])
            logger.info('Payment %s | user=%s', moyasar_status, record.user.id)
            return 'failed'

        return 'initiated'


def verify_payment(moyasar_payment_id: str) -> dict:
    """
    Fetch the raw payment object from the Moyasar API.

    GET is idempotent, so the session is configured to retry automatically
    on transient errors (5xx, 429, connection failures) with exponential backoff.

    Used internally by handle_callback and available for manual verification.

    Returns:
        The full Moyasar payment dict (amounts are in halalas).

    Raises:
        MoyasarError: if all retries are exhausted or the request fails.
    """
    url = f'{settings.MOYASAR_BASE_URL}/payments/{moyasar_payment_id}'
    logger.info(
        'Verifying payment | moyasar_payment_id=%s attempt_max=%s',
        moyasar_payment_id, _RETRY_TOTAL + 1,
    )

    try:
        response = _session(retry_post=False).get(
            url,
            auth=_auth(),
            timeout=_REQUEST_TIMEOUT,
        )
        logger.info('Moyasar verify response | http_status=%s', response.status_code)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        raise MoyasarError(
            f'Moyasar API timed out after {_REQUEST_TIMEOUT}s '
            f'(tried {_RETRY_TOTAL + 1} time(s))'
        )
    except requests.exceptions.RequestException as exc:
        raise MoyasarError(f'Moyasar API request failed after retries: {exc}')
