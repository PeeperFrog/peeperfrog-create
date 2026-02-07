#!/usr/bin/env python3
"""
Tests for Gemini Batch API module.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_batch import submit_batch_job, check_batch_status, retrieve_batch_results


class TestGeminiBatch(unittest.TestCase):

    @patch('gemini_batch.requests.post')
    def test_submit_batch_job_success(self, mock_post):
        """Test successful batch job submission."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "test-job-123",
            "status": "pending"
        }
        mock_post.return_value = mock_response

        requests_list = [{
            "prompt": "A beautiful landscape",
            "aspect_ratio": "16:9",
            "image_size": "large",
            "quality": "pro"
        }]

        result = submit_batch_job(requests_list, "fake-api-key")

        self.assertTrue(result["success"])
        self.assertIn("batch_job_id", result)
        self.assertEqual(result["request_count"], 1)
        self.assertIn("estimated_completion_time", result)

    @patch('gemini_batch.requests.post')
    def test_submit_batch_job_failure(self, mock_post):
        """Test batch job submission failure."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        requests_list = [{"prompt": "test"}]
        result = submit_batch_job(requests_list, "fake-api-key")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch('gemini_batch.requests.get')
    def test_check_batch_status_pending(self, mock_get):
        """Test checking status of pending batch job."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "PROCESSING",
            "totalTasks": 5,
            "completedTasks": 2
        }
        mock_get.return_value = mock_response

        result = check_batch_status("test-job-123", "fake-api-key")

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["progress"], "2/5 completed")

    @patch('gemini_batch.requests.get')
    def test_check_batch_status_completed(self, mock_get):
        """Test checking status of completed batch job."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "COMPLETED",
            "totalTasks": 3,
            "completedTasks": 3,
            "results": [
                {"request_id": "img_1", "response": {"candidates": []}},
                {"request_id": "img_2", "response": {"candidates": []}},
                {"request_id": "img_3", "response": {"candidates": []}}
            ]
        }
        mock_get.return_value = mock_response

        result = check_batch_status("test-job-123", "fake-api-key")

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("results", result)

    @patch('gemini_batch.requests.get')
    def test_check_batch_status_not_found(self, mock_get):
        """Test checking status of non-existent batch job."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = check_batch_status("nonexistent-job", "fake-api-key")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch('gemini_batch.check_batch_status')
    @patch('gemini_batch.requests.get')
    def test_retrieve_batch_results_not_complete(self, mock_get, mock_check):
        """Test retrieving results when batch is not complete."""
        mock_check.return_value = {
            "success": True,
            "status": "processing"
        }

        result = retrieve_batch_results("test-job-123", "fake-api-key", "/tmp/test")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_submit_batch_job_with_reference_images(self):
        """Test batch submission with reference images."""
        with patch('gemini_batch.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "name": "test-job-456",
                "status": "pending"
            }
            mock_post.return_value = mock_response

            requests_list = [{
                "prompt": "A landscape",
                "aspect_ratio": "16:9",
                "image_size": "large",
                "quality": "pro",
                "reference_images": ["base64encodedimage1", "base64encodedimage2"]
            }]

            result = submit_batch_job(requests_list, "fake-api-key")

            self.assertTrue(result["success"])
            self.assertIn("batch_job_id", result)

            # Verify the API call included reference images
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            self.assertIn("requests", payload)
            self.assertTrue(len(payload["requests"]) > 0)

    def test_submit_batch_job_with_gemini_opts(self):
        """Test batch submission with Gemini-specific options."""
        with patch('gemini_batch.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "name": "test-job-789",
                "status": "pending"
            }
            mock_post.return_value = mock_response

            requests_list = [{
                "prompt": "A photo",
                "aspect_ratio": "1:1",
                "image_size": "large",
                "quality": "pro",
                "gemini_opts": {
                    "search_grounding": True,
                    "thinking_level": "high",
                    "media_resolution": "high"
                }
            }]

            result = submit_batch_job(requests_list, "fake-api-key")

            self.assertTrue(result["success"])

    def test_batch_job_with_multiple_requests(self):
        """Test batch submission with multiple images."""
        with patch('gemini_batch.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "name": "test-job-multi",
                "status": "pending"
            }
            mock_post.return_value = mock_response

            requests_list = [
                {"prompt": "Image 1", "aspect_ratio": "16:9", "quality": "pro"},
                {"prompt": "Image 2", "aspect_ratio": "1:1", "quality": "fast"},
                {"prompt": "Image 3", "aspect_ratio": "4:3", "quality": "pro"}
            ]

            result = submit_batch_job(requests_list, "fake-api-key")

            self.assertTrue(result["success"])
            self.assertEqual(result["request_count"], 3)


if __name__ == '__main__':
    unittest.main()
