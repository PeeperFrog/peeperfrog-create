#!/usr/bin/env python3
"""
Tests for LinkedIn MCP Server.
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
import time
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import linkedin_server


class TestTokenManagement(unittest.TestCase):
    """Test token loading, saving, and expiration checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_tokens = {
            "access_token": "test_access_token_123",
            "refresh_token": "test_refresh_token_456",
            "expires_at": time.time() + 86400,  # Expires in 1 day
            "scope": "profile email w_member_social"
        }

    @patch('linkedin_server.TOKENS_FILE')
    def test_load_tokens_success(self, mock_tokens_file):
        """Test loading tokens from file successfully."""
        mock_tokens_file.exists.return_value = True

        with patch('builtins.open', mock_open(read_data=json.dumps(self.test_tokens))):
            tokens = linkedin_server.load_tokens()

        self.assertEqual(tokens["access_token"], "test_access_token_123")
        self.assertEqual(tokens["refresh_token"], "test_refresh_token_456")
        self.assertIn("expires_at", tokens)

    @patch('linkedin_server.TOKENS_FILE')
    def test_load_tokens_file_not_exists(self, mock_tokens_file):
        """Test loading tokens when file doesn't exist."""
        mock_tokens_file.exists.return_value = False

        tokens = linkedin_server.load_tokens()

        self.assertEqual(tokens, {})

    @patch('linkedin_server.TOKENS_FILE')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.chmod')
    def test_save_tokens(self, mock_chmod, mock_file, mock_tokens_file):
        """Test saving tokens to file."""
        mock_tokens_file.parent.mkdir = MagicMock()

        linkedin_server.save_tokens(self.test_tokens)

        # Verify file was opened for writing
        mock_file.assert_called_once()
        # Verify permissions were set to 0o600
        mock_chmod.assert_called_once()

    def test_is_token_expired_valid(self):
        """Test token expiration check with valid token."""
        # Token expires in 30 days
        future_tokens = {
            "expires_at": time.time() + (30 * 24 * 60 * 60)
        }

        is_expired = linkedin_server.is_token_expired(future_tokens)

        self.assertFalse(is_expired)

    def test_is_token_expired_soon(self):
        """Test token expiration check with token expiring soon (< 7 days)."""
        # Token expires in 5 days (should be considered expired)
        soon_tokens = {
            "expires_at": time.time() + (5 * 24 * 60 * 60)
        }

        is_expired = linkedin_server.is_token_expired(soon_tokens)

        self.assertTrue(is_expired)

    def test_is_token_expired_past(self):
        """Test token expiration check with already expired token."""
        # Token expired yesterday
        past_tokens = {
            "expires_at": time.time() - 86400
        }

        is_expired = linkedin_server.is_token_expired(past_tokens)

        self.assertTrue(is_expired)

    def test_is_token_expired_missing_field(self):
        """Test token expiration check with missing expires_at field."""
        incomplete_tokens = {}

        is_expired = linkedin_server.is_token_expired(incomplete_tokens)

        self.assertTrue(is_expired)  # Should default to expired


class TestAPIHelpers(unittest.TestCase):
    """Test LinkedIn API helper functions."""

    def test_get_linkedin_headers(self):
        """Test LinkedIn API headers generation."""
        access_token = "test_token_123"

        headers = linkedin_server.get_linkedin_headers(access_token)

        self.assertEqual(headers["Authorization"], "Bearer test_token_123")
        self.assertEqual(headers["LinkedIn-Version"], linkedin_server.LINKEDIN_API_VERSION)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-Restli-Protocol-Version"], "2.0.0")

    @patch('linkedin_server.load_tokens')
    def test_get_person_urn_success(self, mock_load):
        """Test getting person URN successfully."""
        # Mock tokens with user_info containing sub
        mock_load.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "user_info": {
                "sub": "abc123xyz"
            }
        }

        person_urn = linkedin_server.get_person_urn()

        self.assertEqual(person_urn, "urn:li:person:abc123xyz")

    @patch('linkedin_server.load_tokens')
    def test_get_person_urn_failure(self, mock_load):
        """Test getting person URN when user info is missing."""
        # Mock tokens without user_info
        mock_load.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_refresh"
        }

        with self.assertRaises(Exception) as context:
            linkedin_server.get_person_urn()

        self.assertIn("No user info found in tokens", str(context.exception))

    def test_get_author_urn_organization(self):
        """Test getting author URN for organization."""
        with patch('linkedin_server.get_organization_id', return_value="123456"):
            author_urn = linkedin_server.get_author_urn(target="organization")

        self.assertEqual(author_urn, "urn:li:organization:123456")

    def test_get_author_urn_personal(self):
        """Test getting author URN for personal profile."""
        with patch('linkedin_server.get_person_urn', return_value="urn:li:person:abc123"):
            author_urn = linkedin_server.get_author_urn(target="personal")

        self.assertEqual(author_urn, "urn:li:person:abc123")

    def test_get_author_urn_specific_org(self):
        """Test getting author URN for specific organization ID."""
        author_urn = linkedin_server.get_author_urn(target="987654")

        self.assertEqual(author_urn, "urn:li:organization:987654")


class TestPostURNNormalization(unittest.TestCase):
    """Test post URN normalization."""

    def test_normalize_post_urn_already_normalized(self):
        """Test normalizing already normalized URN."""
        urn = "urn:li:share:1234567890"

        normalized = linkedin_server.normalize_post_urn(urn)

        self.assertEqual(normalized, urn)

    def test_normalize_post_urn_activity_format(self):
        """Test normalizing activity format URN (returns as-is)."""
        urn = "urn:li:activity:1234567890"

        normalized = linkedin_server.normalize_post_urn(urn)

        # Function returns URNs as-is if they start with "urn:"
        self.assertEqual(normalized, urn)

    def test_normalize_post_urn_ugcpost_format(self):
        """Test normalizing ugcPost format URN (returns as-is)."""
        urn = "urn:li:ugcPost:1234567890"

        normalized = linkedin_server.normalize_post_urn(urn)

        # Function returns URNs as-is if they start with "urn:"
        self.assertEqual(normalized, urn)

    def test_normalize_post_urn_plain_id(self):
        """Test normalizing plain numeric ID."""
        post_id = "1234567890"

        normalized = linkedin_server.normalize_post_urn(post_id)

        self.assertEqual(normalized, "urn:li:share:1234567890")


class TestConfigurationLoading(unittest.TestCase):
    """Test configuration loading."""

    @patch('linkedin_server.CONFIG_FILE')
    def test_load_config_success(self, mock_config_file):
        """Test loading configuration successfully."""
        mock_config_file.exists.return_value = True
        test_config = {
            "linkedin_organization_id": "123456",
            "debug": True
        }

        with patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
            config = linkedin_server.load_config()

        self.assertEqual(config["linkedin_organization_id"], "123456")
        self.assertTrue(config["debug"])

    @patch('linkedin_server.CONFIG_FILE')
    def test_load_config_file_not_exists(self, mock_config_file):
        """Test loading configuration when file doesn't exist."""
        mock_config_file.exists.return_value = False

        config = linkedin_server.load_config()

        self.assertEqual(config, {})


class TestTokenRefresh(unittest.TestCase):
    """Test OAuth token refresh functionality."""

    @patch('os.environ.get')
    @patch('httpx.post')
    def test_refresh_access_token_success(self, mock_post, mock_env_get):
        """Test successful token refresh."""
        # Mock environment variables
        mock_env_get.side_effect = lambda key, default=None: {
            "LINKEDIN_CLIENT_ID": "test_client_id",
            "LINKEDIN_CLIENT_SECRET": "test_client_secret"
        }.get(key, default)

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 5184000,
            "refresh_token": "new_refresh_token"
        }
        mock_post.return_value = mock_response

        old_tokens = {
            "refresh_token": "old_refresh_token",
            "expires_at": time.time() - 100  # Expired
        }

        with patch('linkedin_server.save_tokens') as mock_save:
            new_tokens = linkedin_server.refresh_access_token(old_tokens)

        self.assertEqual(new_tokens["access_token"], "new_access_token")
        self.assertEqual(new_tokens["refresh_token"], "new_refresh_token")
        self.assertIn("expires_at", new_tokens)
        mock_save.assert_called_once()

    @patch('os.environ.get')
    @patch('httpx.post')
    def test_refresh_access_token_failure(self, mock_post, mock_env_get):
        """Test token refresh failure."""
        mock_env_get.side_effect = lambda key, default=None: {
            "LINKEDIN_CLIENT_ID": "test_client_id",
            "LINKEDIN_CLIENT_SECRET": "test_client_secret"
        }.get(key, default)

        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid refresh token"
        mock_post.return_value = mock_response

        old_tokens = {"refresh_token": "invalid_refresh_token"}

        with self.assertRaises(Exception) as context:
            linkedin_server.refresh_access_token(old_tokens)

        self.assertIn("Token refresh failed: 400", str(context.exception))


class TestGetValidToken(unittest.TestCase):
    """Test getting valid access token with auto-refresh."""

    @patch('linkedin_server.load_tokens')
    @patch('linkedin_server.is_token_expired')
    def test_get_valid_token_fresh(self, mock_is_expired, mock_load):
        """Test getting valid token when token is fresh."""
        mock_load.return_value = {
            "access_token": "fresh_token",
            "expires_at": time.time() + 86400
        }
        mock_is_expired.return_value = False

        token = linkedin_server.get_valid_token()

        self.assertEqual(token, "fresh_token")

    @patch('linkedin_server.load_tokens')
    @patch('linkedin_server.is_token_expired')
    @patch('linkedin_server.refresh_access_token')
    def test_get_valid_token_expired(self, mock_refresh, mock_is_expired, mock_load):
        """Test getting valid token when token is expired (auto-refresh)."""
        old_tokens = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token",
            "expires_at": time.time() - 100
        }
        new_tokens = {
            "access_token": "refreshed_token",
            "expires_at": time.time() + 86400
        }

        mock_load.return_value = old_tokens
        mock_is_expired.return_value = True
        mock_refresh.return_value = new_tokens

        token = linkedin_server.get_valid_token()

        self.assertEqual(token, "refreshed_token")
        mock_refresh.assert_called_once_with(old_tokens)

    @patch('linkedin_server.load_tokens')
    def test_get_valid_token_no_tokens(self, mock_load):
        """Test getting valid token when no tokens exist."""
        mock_load.return_value = {}

        with self.assertRaises(Exception) as context:
            linkedin_server.get_valid_token()

        self.assertIn("No access token found", str(context.exception))


class TestOrganizationID(unittest.TestCase):
    """Test organization ID retrieval."""

    @patch('linkedin_server.CFG', {"linkedin": {"organization_id": "123456"}})
    @patch('os.environ.get')
    def test_get_organization_id_from_config(self, mock_env):
        """Test getting organization ID from config."""
        mock_env.return_value = None  # No env variable set

        org_id = linkedin_server.get_organization_id()

        self.assertEqual(org_id, "123456")

    @patch('linkedin_server.CFG', {})
    @patch('os.environ.get')
    def test_get_organization_id_from_env(self, mock_env):
        """Test getting organization ID from environment variable."""
        mock_env.return_value = "789012"

        org_id = linkedin_server.get_organization_id()

        self.assertEqual(org_id, "789012")

    @patch('linkedin_server.CFG', {})
    @patch('os.environ.get')
    def test_get_organization_id_not_found(self, mock_env):
        """Test getting organization ID when not configured."""
        mock_env.return_value = None

        org_id = linkedin_server.get_organization_id()

        self.assertIsNone(org_id)


if __name__ == '__main__':
    unittest.main()
