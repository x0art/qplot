"""Tests for OAuth / PKCE module.

Contract verified against 9Router's QoderService
(src/lib/oauth/services/qoder.js): nonce and machine_id are full uuid4
strings, and the selectAccounts params are challenge, challenge_method=S256,
machine_id, nonce — with no redirect_uri and no client_id.
"""

import base64
import hashlib
import uuid
from unittest import mock

import requests

from qoder_autopilot.auth.oauth import (
    base64url_encode,
    generate_pkce_pair,
    initiate_device_flow,
    poll_device_token,
)


class TestBase64urlEncode:
    """Test base64url encoding."""

    def test_no_padding(self):
        result = base64url_encode(b"hello world")
        assert "=" not in result

    def test_url_safe_chars(self):
        result = base64url_encode(b"\xff\xfe\xfd")
        assert "+" not in result
        assert "/" not in result

    def test_decodable(self):
        data = b"test data 12345"
        encoded = base64url_encode(data)
        # Add padding back for decoding
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        decoded = base64.urlsafe_b64decode(encoded)
        assert decoded == data


class TestGeneratePkcePair:
    """Test PKCE pair generation."""

    def test_returns_tuple(self):
        result = generate_pkce_pair()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_verifier_and_challenge_different(self):
        verifier, challenge = generate_pkce_pair()
        assert verifier != challenge

    def test_challenge_is_sha256_of_verifier(self):
        verifier, challenge = generate_pkce_pair()
        expected = base64url_encode(hashlib.sha256(verifier.encode()).digest())
        assert challenge == expected

    def test_unique_each_time(self):
        pairs = {generate_pkce_pair() for _ in range(20)}
        assert len(pairs) == 20


class TestInitiateDeviceFlow:
    """Test device flow initiation (verified 9Router contract)."""

    def test_returns_all_keys(self):
        flow = initiate_device_flow()
        required_keys = {
            "auth_url",
            "callback_url",
            "verifier",
            "challenge",
            "nonce",
            "machine_id",
        }
        assert set(flow.keys()) == required_keys

    def test_auth_url_contains_signin(self):
        flow = initiate_device_flow()
        assert "qoder.com/users/sign-in" in flow["auth_url"]

    def test_auth_url_contains_oauth_callback(self):
        flow = initiate_device_flow()
        assert "oauth_callback=" in flow["auth_url"]

    def test_callback_url_contains_challenge(self):
        flow = initiate_device_flow()
        assert "challenge=" in flow["callback_url"]
        assert "challenge_method=S256" in flow["callback_url"]

    def test_callback_url_contains_nonce(self):
        flow = initiate_device_flow()
        assert f"nonce={flow['nonce']}" in flow["callback_url"]

    def test_callback_url_has_no_client_id(self):
        flow = initiate_device_flow()
        assert "client_id=" not in flow["callback_url"]

    def test_callback_url_has_no_redirect_uri(self):
        flow = initiate_device_flow()
        assert "redirect_uri=" not in flow["callback_url"]

    def test_callback_url_points_at_selectaccounts(self):
        flow = initiate_device_flow()
        assert flow["callback_url"].startswith(
            "https://qoder.com/device/selectAccounts?"
        )

    def test_nonce_is_uuid4(self):
        flow = initiate_device_flow()
        nonce = flow["nonce"]
        assert len(nonce) == 36  # full UUID with dashes
        assert "-" in nonce
        # Raises ValueError if not a valid UUID
        assert str(uuid.UUID(nonce)) == nonce

    def test_machine_id_is_uuid4(self):
        flow = initiate_device_flow()
        machine_id = flow["machine_id"]
        assert len(machine_id) == 36  # full UUID with dashes
        assert "-" in machine_id
        # Raises ValueError if not a valid UUID
        assert str(uuid.UUID(machine_id)) == machine_id

    def test_callback_params_order_matches_9router(self):
        flow = initiate_device_flow()
        after_qs = flow["callback_url"].split("?", 1)[1]
        # 9Router's URLSearchParams insertion order:
        # challenge, challenge_method, machine_id, nonce
        assert after_qs.startswith("challenge="), f"Expected challenge first, got: {after_qs[:60]}"
        assert "&challenge_method=S256&machine_id=" in after_qs
        assert after_qs.endswith(f"nonce={flow['nonce']}")

    def test_unique_flows(self):
        flows = [initiate_device_flow() for _ in range(5)]
        nonces = {f["nonce"] for f in flows}
        assert len(nonces) == 5, "Nonces should be unique"


class TestPollDeviceToken:
    """Test device token polling semantics (verified 9Router contract).

    202/404 = still pending (keep polling), 200 + token = authorized,
    200 without token and any other status = terminal failure.
    """

    def test_returns_token_on_200(self):
        body = {"token": "dt-123", "user_id": "42", "refresh_token": "rt-1"}
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get",
            return_value=mock.Mock(status_code=200, json=lambda: body),
        ) as m:
            result = poll_device_token("n", "v", max_attempts=5, interval=0)
        assert result == body
        assert m.call_count == 1

    def test_200_without_token_is_terminal(self):
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get",
            return_value=mock.Mock(status_code=200, json=lambda: {}),
        ) as m:
            result = poll_device_token("n", "v", max_attempts=5, interval=0)
        assert result is None
        assert m.call_count == 1  # terminal — no further polling

    def test_500_is_terminal(self):
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get",
            return_value=mock.Mock(status_code=500, json=lambda: {}),
        ) as m:
            result = poll_device_token("n", "v", max_attempts=5, interval=0)
        assert result is None
        assert m.call_count == 1

    def test_pending_then_authorized(self):
        pending = mock.Mock(status_code=202)
        body = {"token": "dt-9"}
        ok = mock.Mock(status_code=200, json=lambda: body)
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get", side_effect=[pending, ok]
        ) as m:
            result = poll_device_token("n", "v", max_attempts=5, interval=0)
        assert result == body
        assert m.call_count == 2

    def test_pending_timeout_returns_none(self):
        pending = mock.Mock(status_code=404)
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get", return_value=pending
        ) as m:
            result = poll_device_token("n", "v", max_attempts=2, interval=0)
        assert result is None
        assert m.call_count == 2  # polled twice, then gave up

    def test_network_error_retries(self):
        body = {"token": "dt-5"}
        ok = mock.Mock(status_code=200, json=lambda: body)
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get",
            side_effect=[requests.exceptions.ConnectionError("boom"), ok],
        ) as m:
            result = poll_device_token("n", "v", max_attempts=5, interval=0)
        assert result == body
        assert m.call_count == 2  # network errors stay retryable

    def test_poll_url_and_headers_match_9router(self):
        body = {"token": "dt-7"}
        ok = mock.Mock(status_code=200, json=lambda: body)
        with mock.patch("time.sleep"), mock.patch(
            "qoder_autopilot.auth.oauth.requests.get", return_value=ok
        ) as m:
            poll_device_token(
                "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "verifier-abc",
                max_attempts=1,
                interval=0,
            )
        call = m.call_args
        # requests.get(url, headers=..., timeout=...) — url is positional
        assert call.args[0] == (
            "https://openapi.qoder.sh/api/v1/deviceToken/poll"
            "?nonce=9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
            "&verifier=verifier-abc"
            "&challenge_method=S256"
        )
        assert call.kwargs["headers"] == {
            "Accept": "application/json",
            "User-Agent": "Go-http-client/2.0",
        }
        assert call.kwargs["timeout"] == 15
