# =============================================================================
# verification/services.py
# OWNED BY: Ghadi
# (added by ghadi: all verification logic lives here — views only call this)
#
# PURPOSE:
#   One function: verify_contract_hash(hash_hex)
#   Takes a 64-char hex string → looks it up in the DB → checks blockchain
#   → returns a safe result dict with NO personal data (no names, emails, etc.)
#
# WHAT IT READS FROM (read-only, never writes):
#   contracts.Contract         → canonical_hash, status, completed_at, id
#   contracts.ContractParty    → count only (no names)
#   blockchain.ChainTransaction → tx_hash, confirmed_at, block_number
#
# RESULT STATUSES:
#   INVALID_HASH       — not a 64-char hex string
#   NOT_FOUND          — no contract with this hash exists
#   VALID_PENDING_CHAIN — contract found, waiting for blockchain confirmation
#   VALID_AND_ANCHORED  — contract found + confirmed on blockchain (Sepolia testnet)
#
# SECURITY RULE:
#   This function NEVER returns PII. No names, emails, national IDs, or
#   clause content. Only: contract UUID, status, dates, party count, and tx hash.
# =============================================================================

import re

from blockchain.models import ChainTransaction
from contracts.models import Contract, ContractParty


def verify_contract_hash(hash_hex: str) -> dict:
    """
    Verify a contract by its canonical SHA-256 hash and return a safe result dict.

    The result always contains ALL keys — callers can rely on the shape without
    checking for missing keys. No PII (names, emails, national IDs, clause content,
    IP addresses) is ever included in the output.

    Parameters:
        hash_hex: The candidate hash string submitted by the user.

    Returns a dict with "verification_status" set to one of:
        "INVALID_HASH"          — input is not a valid 64-char hex string
        "NOT_FOUND"             — no contract with this canonical_hash exists
        "VALID_PENDING_CHAIN"   — contract found but no confirmed blockchain tx yet
        "VALID_AND_ANCHORED"    — contract found + confirmed on blockchain

    Security notes:
        - Input is stripped and lowercased before any DB query.
        - The regex check prevents SQL wildcard injection via the ORM's LIKE fallback.
        - HTTP 200 must always be returned by the view (not 404) to prevent
          hash-enumeration attacks by timing or status-code sniffing.
    """
    # ── Step 1: sanitise and validate format ──────────────────────────────────
    hash_hex = hash_hex.strip().lower()

    NOT_FOUND_BASE = {
        'contract_id':              None,
        'contract_status':          None,
        'signed_at':                None,
        'parties_count':            None,
        'blockchain_tx':            None,
        'blockchain_confirmed_at':  None,
        'blockchain_block_number':  None,
    }

    if len(hash_hex) != 64 or not re.fullmatch(r'[0-9a-f]{64}', hash_hex):
        return {'hash': hash_hex, 'verification_status': 'INVALID_HASH', **NOT_FOUND_BASE}

    # ── Step 2: look up the contract ──────────────────────────────────────────
    contract = Contract.objects.filter(canonical_hash=hash_hex).first()

    if contract is None:
        return {'hash': hash_hex, 'verification_status': 'NOT_FOUND', **NOT_FOUND_BASE}

    # ── Step 3: get blockchain proof (CONFIRMED tx only) ──────────────────────
    chain_tx = (
        ChainTransaction.objects
        .filter(contract=contract, status=ChainTransaction.Status.CONFIRMED)
        .first()
    )

    parties_count = ContractParty.objects.filter(contract=contract).count()

    verification_status = 'VALID_AND_ANCHORED' if chain_tx else 'VALID_PENDING_CHAIN'

    # ── Step 4: build safe result — NO PII ───────────────────────────────────
    return {
        'hash':                     hash_hex,
        'verification_status':      verification_status,
        'contract_id':              str(contract.id),
        'contract_status':          contract.status,
        'signed_at':                contract.completed_at,
        'parties_count':            parties_count,
        'blockchain_tx':            chain_tx.tx_hash or None if chain_tx else None,
        'blockchain_confirmed_at':  chain_tx.confirmed_at if chain_tx else None,
        'blockchain_block_number':  chain_tx.block_number if chain_tx else None,
    }
