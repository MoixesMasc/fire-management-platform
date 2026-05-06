"""Root pytest configuration — shared fixtures and settings."""
import os

import pytest

# Point all services to LocalStack for tests
os.environ.setdefault("DYNAMODB_ENDPOINT_URL", "http://localhost:4566")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("COGNITO_REGION", "us-east-1")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_TEST")
os.environ.setdefault("COGNITO_CLIENT_ID", "test-client-id")
os.environ.setdefault("LOG_LEVEL", "ERROR")  # suppress logs during tests
