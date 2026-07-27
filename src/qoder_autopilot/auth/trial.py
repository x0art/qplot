"""
Qoder Autopilot — Pro Trial Claim
====================================
Claim the free 14-day Pro trial (300 Credits) by making an authenticated
API call to Qoder's backend. This emulates what the Qoder CLI does on
first sign-in — the trial is granted automatically when a client
authenticates for the first time.

Flow:
    1. Uses the PAT (Personal Access Token) as Bearer auth
    2. POST to Qoder's trial activation endpoint
    3. Returns True/False based on response
"""

import requests

from ..infra import config
from ..utils.logger import log, log_err, log_ok, log_warn


def claim_pro_trial(pat: str) -> bool:
    """Claim the free 14-day Pro trial for a registered Qoder account.

    Makes an authenticated API call mimicking the Qoder CLI's first sign-in.
    The trial (300 Credits, 14 days) is granted automatically when a client
    authenticates for the first time.

    Args:
        pat: Personal Access Token for the account.

    Returns:
        True if trial was claimed successfully, False on failure.
    """
    log("   🏆 Step: Claiming Pro trial (300 Credits / 14 days)...")

    url = config.QODER_TRIAL_URL
    headers = {
        "Authorization": f"Bearer {pat}",
        "User-Agent": "QoderCLI/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, headers=headers, json={}, timeout=15)
        if resp.ok:
            body = resp.json()
            log_ok(f"🎉 Pro trial activated! Credits: {body.get('credits', '?')}, "
                   f"expires: {body.get('expires_at', '?')}")
            return True
        elif resp.status_code == 409:
            # 409 = Conflict — trial already claimed or already active
            log_ok("✅ Pro trial already active or previously claimed")
            return True
        elif resp.status_code in (400, 422):
            body = resp.json()
            msg = body.get("message", body.get("error", resp.reason))
            log_warn(f"   ⚠️ Trial request rejected ({resp.status_code}): {msg}")
            return False
        else:
            log_warn(f"   ⚠️ Trial endpoint returned {resp.status_code}")
            return False
    except requests.RequestException as e:
        log_err(f"Failed to claim Pro trial: {e}")
        return False
