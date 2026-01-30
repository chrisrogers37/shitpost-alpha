"""
Conftest for shitty_ui tests.
Provides fixtures and mocks for dashboard testing.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock the settings import before any shitty_ui modules are loaded
mock_settings = MagicMock()
mock_settings.DATABASE_URL = "sqlite:///test.db"
sys.modules["shit.config.shitpost_settings"] = MagicMock()
sys.modules["shit.config.shitpost_settings"].settings = mock_settings

# Set DATABASE_URL environment variable as fallback
os.environ["DATABASE_URL"] = "sqlite:///test.db"
