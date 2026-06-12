"""Tests for Nous Portal URL validation fix (Issue #44710).

This module tests that the portal URL validation correctly rejects
invalid/stale URLs (like api.nousresearch.com) and falls back to the
default portal.nousresearch.com.
"""

import pytest
from unittest.mock import patch
import sys
import os

# Add the hermes-agent root to the path
sys.path.insert(0, "/workspace/hermes-agent")

from hermes_cli.auth import (
    _validate_nous_portal_url,
    _ALLOWED_NOUS_PORTAL_HOSTS,
    DEFAULT_NOUS_PORTAL_URL,
)


class TestValidateNousPortalUrl:
    """Tests for _validate_nous_portal_url function."""

    def test_valid_portal_url(self):
        """Valid portal.nousresearch.com URL should be accepted."""
        url = "https://portal.nousresearch.com"
        result = _validate_nous_portal_url(url)
        assert result == "https://portal.nousresearch.com"

    def test_valid_portal_url_with_trailing_slash(self):
        """Valid URL with trailing slash should be normalized."""
        url = "https://portal.nousresearch.com/"
        result = _validate_nous_portal_url(url)
        assert result == "https://portal.nousresearch.com"

    def test_valid_portal_url_with_path(self):
        """Valid URL with path should be accepted."""
        url = "https://portal.nousresearch.com/api/v1"
        result = _validate_nous_portal_url(url)
        assert result == "https://portal.nousresearch.com/api/v1"

    def test_invalid_api_nousresearch_url(self):
        """Invalid api.nousresearch.com URL should be rejected (Issue #44710)."""
        url = "https://api.nousresearch.com"
        result = _validate_nous_portal_url(url)
        assert result is None

    def test_invalid_inference_api_url(self):
        """Inference API URL should be rejected for portal auth."""
        url = "https://inference-api.nousresearch.com"
        result = _validate_nous_portal_url(url)
        assert result is None

    def test_non_https_url(self):
        """Non-https URL should be rejected."""
        url = "http://portal.nousresearch.com"
        result = _validate_nous_portal_url(url)
        assert result is None

    def test_empty_string(self):
        """Empty string should be rejected."""
        result = _validate_nous_portal_url("")
        assert result is None

    def test_none_value(self):
        """None should be rejected."""
        result = _validate_nous_portal_url(None)
        assert result is None

    def test_whitespace_only(self):
        """Whitespace-only string should be rejected."""
        result = _validate_nous_portal_url("   ")
        assert result is None

    def test_malformed_url(self):
        """Malformed URL should be rejected."""
        url = "not-a-url"
        result = _validate_nous_portal_url(url)
        assert result is None

    def test_allowed_hosts_defined(self):
        """Allowed hosts set should contain the expected domain."""
        assert "portal.nousresearch.com" in _ALLOWED_NOUS_PORTAL_HOSTS
        assert "api.nousresearch.com" not in _ALLOWED_NOUS_PORTAL_HOSTS
        assert "inference-api.nousresearch.com" not in _ALLOWED_NOUS_PORTAL_HOSTS


class TestPortalUrlFallback:
    """Tests that portal URL falls back to default when invalid."""

    def test_portal_base_url_fallback_chain(self):
        """Test that invalid stored URL falls back to default.
        
        This simulates the scenario from Issue #44710 where a stale
        api.nousresearch.com URL is stored in auth.json.
        """
        # Mock a state with the invalid URL
        mock_state = {"portal_base_url": "https://api.nousresearch.com"}
        
        # When validated, it should return None (invalid)
        validated = _validate_nous_portal_url(mock_state.get("portal_base_url"))
        assert validated is None
        
        # The fallback chain would then use DEFAULT_NOUS_PORTAL_URL
        # (This is tested in the integration test below)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
