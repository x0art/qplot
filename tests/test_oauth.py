"""Tests for OAuth / PKCE module."""

import base64
import hashlib

from qoder_autopilot.auth.oauth import (
    base64url_encode,
    generate_pkce_pair,
    initiate_device_flow,
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
    """Test device flow initiation (real Qoder format with client_id)."""

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

    def test_callback_url_has_redirect_uri(self):
        flow = initiate_device_flow()
        assert "redirect_uri=" in flow["callback_url"]
        assert "qoder%3A%2F%2Faicoding.aicoding-agent%2Flogin-success" in flow["callback_url"]

    def test_nonce_is_hex_without_dashes(self):
        flow = initiate_device_flow()
        assert len(flow["nonce"]) == 32
        assert "-" not in flow["nonce"]
        # Should be valid hex
        int(flow["nonce"], 16)

    def test_machine_id_is_base64url(self):
        flow = initiate_device_flow()
        assert len(flow["machine_id"]) == 108  # 81 bytes → 108 chars base64url
        assert "+" not in flow["machine_id"]
        assert "/" not in flow["machine_id"]
        assert "=" not in flow["machine_id"]  # no padding

    def test_callback_params_order_nonce_first(self):
        flow = initiate_device_flow()
        # nonce should be the first query param after the base URL
        after_qs = flow["callback_url"].split("?", 1)[1]
        assert after_qs.startswith("nonce="), f"Expected nonce first, got: {after_qs[:50]}"

    def test_unique_flows(self):
        flows = [initiate_device_flow() for _ in range(5)]
        nonces = {f["nonce"] for f in flows}
        assert len(nonces) == 5, "Nonces should be unique"
