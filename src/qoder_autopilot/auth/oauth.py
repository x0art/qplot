"""
Qoder Autopilot — OAuth / PKCE Device Auth Flow
=================================================
Implements the PKCE (Proof Key for Code Exchange) device authorization flow
for Qoder, verified against 9Router's QoderService
(src/lib/oauth/services/qoder.js + open-sse/providers/registry/qoder.js).

Verified contract (from 9Router):
    - PKCE verifier = 32 random bytes, base64url, no padding
    - challenge     = S256 of verifier, base64url, no padding
    - nonce         = uuid4() — full UUID *with dashes*
    - machine_id    = uuid4() — full UUID *with dashes*
    - selectAccounts params (insertion order): challenge, challenge_method=S256,
      machine_id, nonce — NO redirect_uri, NO client_id
    - poll endpoint: openapi.qoder.sh/api/v1/deviceToken/poll
      ?nonce=...&verifier=...&challenge_method=S256 (UA: Go-http-client/2.0)
      — 202/404 = still pending, 200 + token = authorized

Flow:
    1. Generate PKCE verifier + challenge
    2. Build auth URL (sign-in page wrapping the selectAccounts callback, so a
       brand-new account can sign up and then land on the nonce-confirmation page)
    3. User completes auth in browser (sign-up / sign-in)
    4. Poll device token endpoint until authorized
    5. Use access token for API calls
"""

import base64
import hashlib
import os
import time
import uuid
from urllib.parse import quote as url_quote
from urllib.parse import urlencode

import requests

from ..infra import config
from ..utils.logger import log, log_err, log_ok


def base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE verifier + S256 challenge (32 random bytes).

    Returns:
        Tuple of (verifier, challenge).
    """
    verifier = base64url_encode(os.urandom(32))
    challenge = base64url_encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def initiate_device_flow() -> dict:
    """Generate the full device auth URL and parameters (verified against 9Router).

    Mirrors QoderService.initiateDeviceFlow() exactly for the selectAccounts
    callback params:
    - nonce as a full uuid4 string *with dashes*
    - machine_id as a full uuid4 string *with dashes*
    - param insertion order: challenge, challenge_method=S256, machine_id, nonce
    - NO redirect_uri and NO client_id (the real 9Router client sends neither)

    auth_url wraps the callback in the sign-in page (oauth_callback=...) so a
    NEW account can sign up and then land on device/selectAccounts, whose JS
    confirms the nonce. The bare selectAccounts URL alone assumes the user is
    already logged in, which would break registration.

    Returns:
        dict with keys: auth_url, callback_url, verifier, challenge, nonce, machine_id
    """
    verifier, challenge = generate_pkce_pair()
    nonce = str(uuid.uuid4())       # full UUID, e.g. "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    machine_id = str(uuid.uuid4())  # full UUID — matches 9Router's uuidv4()

    # Insertion order matches 9Router's URLSearchParams({
    #   challenge, challenge_method: "S256", machine_id, nonce })
    callback_params = urlencode(
        {
            "challenge": challenge,
            "challenge_method": "S256",
            "machine_id": machine_id,
            "nonce": nonce,
        }
    )
    callback_url = f"{config.QODER_LOGIN_URL}?{callback_params}"

    # Wrap in sign-in page with oauth_callback
    auth_url = f"{config.QODER_SIGNIN_URL}?oauth_callback={url_quote(callback_url, safe='')}"

    return {
        "auth_url": auth_url,
        "callback_url": callback_url,
        "verifier": verifier,
        "challenge": challenge,
        "nonce": nonce,
        "machine_id": machine_id,
    }


def poll_device_token(
    nonce: str,
    verifier: str,
    max_attempts: int = 150,
    interval: int = 2,
) -> dict | None:
    """Poll Qoder deviceToken endpoint until user authorizes.

    Args:
        nonce: The nonce from initiate_device_flow().
        verifier: The PKCE verifier from initiate_device_flow().
        max_attempts: Maximum number of polling attempts.
        interval: Seconds between polls.

    Returns:
        dict with {token, refresh_token, user_id, expires_at} or None on timeout.
    """
    url = (
        f"{config.QODER_DEVICE_TOKEN_URL}"
        f"?nonce={url_quote(nonce)}"
        f"&verifier={url_quote(verifier)}"
        f"&challenge_method=S256"
    )
    headers = {"Accept": "application/json", "User-Agent": "Go-http-client/2.0"}

    log(f"   🔄 Polling device token (max {max_attempts * interval}s)...")
    for i in range(max_attempts):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code in (202, 404):
                # Still pending — user hasn't authorized yet
                if i % 10 == 0 and i > 0:
                    log(f"   ⏳ Poll #{i} — still waiting...")
                time.sleep(interval)
                continue
            if r.status_code == 200:
                body = r.json()
                if body.get("token"):
                    log_ok(f"Device token received! user_id={body.get('user_id', '?')}")
                    return body
                # 200 without a token — upstream shape changed; terminal (matches 9Router)
                log_err(f"Device token poll returned 200 but no token: {body}")
                return None
            # Anything else is a terminal failure (matches 9Router's throw)
            log_err(f"Device token poll failed: HTTP {r.status_code}")
            return None
        except requests.RequestException as e:
            # Transient network errors stay retryable for headless automation
            log(f"   ⚠️ Poll error: {e}")
            time.sleep(interval)

    log_err("Device token poll timed out")
    return None


def fetch_userinfo(access_token: str) -> dict:
    """Fetch Qoder user profile. Best-effort, returns {} on failure."""
    try:
        r = requests.get(
            config.QODER_USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "Go-http-client/2.0",
            },
            timeout=15,
        )
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    return {}
