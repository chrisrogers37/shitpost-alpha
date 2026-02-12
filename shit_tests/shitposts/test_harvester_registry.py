"""
Tests for HarvesterRegistry and create_default_registry.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Optional
from datetime import datetime

from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_registry import HarvesterRegistry, create_default_registry
from shitposts.harvester_models import HarvesterConfig


# Minimal concrete implementation for registry tests
class FakeHarvesterA(SignalHarvester):
    def get_source_name(self):
        return "fake_a"
    async def _test_connection(self):
        pass
    async def _fetch_batch(self, cursor=None):
        return [], None
    def _extract_item_id(self, item):
        return item.get("id", "")
    def _extract_timestamp(self, item):
        return datetime(2024, 1, 1)
    def _extract_content_preview(self, item):
        return ""


class FakeHarvesterB(SignalHarvester):
    def get_source_name(self):
        return "fake_b"
    async def _test_connection(self):
        pass
    async def _fetch_batch(self, cursor=None):
        return [], None
    def _extract_item_id(self, item):
        return item.get("id", "")
    def _extract_timestamp(self, item):
        return datetime(2024, 1, 1)
    def _extract_content_preview(self, item):
        return ""


class TestHarvesterRegistry:
    """Tests for HarvesterRegistry."""

    def test_register_valid_class(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA)
        assert "fake_a" in registry.list_sources()

    def test_register_with_config(self):
        registry = HarvesterRegistry()
        config = HarvesterConfig(source_name="fake_a", enabled=False)
        registry.register("fake_a", FakeHarvesterA, config=config)
        assert registry.get_config("fake_a").enabled is False

    def test_register_without_config_creates_default(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA)
        config = registry.get_config("fake_a")
        assert config is not None
        assert config.source_name == "fake_a"
        assert config.enabled is True

    def test_register_invalid_class(self):
        registry = HarvesterRegistry()
        with pytest.raises(TypeError, match="must be a subclass of SignalHarvester"):
            registry.register("bad", dict)

    def test_register_overwrites_existing(self):
        registry = HarvesterRegistry()
        registry.register("source", FakeHarvesterA)
        registry.register("source", FakeHarvesterB)
        assert registry.get_class("source") is FakeHarvesterB

    def test_unregister(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA)
        registry.unregister("fake_a")
        assert "fake_a" not in registry.list_sources()

    def test_unregister_nonexistent(self):
        registry = HarvesterRegistry()
        # Should not raise
        registry.unregister("nonexistent")

    def test_get_class(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA)
        assert registry.get_class("fake_a") is FakeHarvesterA

    def test_get_class_unknown(self):
        registry = HarvesterRegistry()
        assert registry.get_class("unknown") is None

    def test_get_config(self):
        registry = HarvesterRegistry()
        config = HarvesterConfig(source_name="fake_a", limit=50)
        registry.register("fake_a", FakeHarvesterA, config=config)
        assert registry.get_config("fake_a").limit == 50

    def test_get_config_unknown(self):
        registry = HarvesterRegistry()
        assert registry.get_config("unknown") is None

    def test_list_sources(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA)
        registry.register("fake_b", FakeHarvesterB)
        sources = registry.list_sources()
        assert "fake_a" in sources
        assert "fake_b" in sources

    def test_list_sources_empty(self):
        registry = HarvesterRegistry()
        assert registry.list_sources() == []

    def test_list_enabled_sources(self):
        registry = HarvesterRegistry()
        registry.register("enabled", FakeHarvesterA, HarvesterConfig(source_name="enabled", enabled=True))
        registry.register("disabled", FakeHarvesterB, HarvesterConfig(source_name="disabled", enabled=False))
        enabled = registry.list_enabled_sources()
        assert "enabled" in enabled
        assert "disabled" not in enabled

    def test_create_harvester(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA)
        harvester = registry.create_harvester("fake_a", mode="backfill", limit=10)
        assert isinstance(harvester, FakeHarvesterA)
        assert harvester.mode == "backfill"
        assert harvester.limit == 10

    def test_create_harvester_unknown_source(self):
        registry = HarvesterRegistry()
        with pytest.raises(KeyError, match="Unknown source"):
            registry.create_harvester("nonexistent")

    def test_create_all_enabled(self):
        registry = HarvesterRegistry()
        registry.register("enabled", FakeHarvesterA, HarvesterConfig(source_name="enabled", enabled=True))
        registry.register("disabled", FakeHarvesterB, HarvesterConfig(source_name="disabled", enabled=False))

        harvesters = registry.create_all_enabled(mode="incremental")

        assert len(harvesters) == 1
        assert isinstance(harvesters[0], FakeHarvesterA)

    def test_create_all_enabled_empty(self):
        registry = HarvesterRegistry()
        assert registry.create_all_enabled() == []

    def test_create_all_enabled_passes_params(self):
        registry = HarvesterRegistry()
        registry.register("fake_a", FakeHarvesterA, HarvesterConfig(source_name="fake_a", enabled=True))

        harvesters = registry.create_all_enabled(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-12-31",
            limit=50,
        )

        assert len(harvesters) == 1
        h = harvesters[0]
        assert h.mode == "range"
        assert h.start_date == "2024-01-01"
        assert h.end_date == "2024-12-31"
        assert h.limit == 50


class TestCreateDefaultRegistry:
    """Tests for create_default_registry factory."""

    def test_includes_truth_social(self):
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            registry = create_default_registry()
            assert "truth_social" in registry.list_sources()

    def test_truth_social_is_enabled(self):
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            registry = create_default_registry()
            assert "truth_social" in registry.list_enabled_sources()

    def test_creates_truth_social_harvester(self):
        from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester
        with patch('shitposts.truth_social_s3_harvester.settings') as mock_settings:
            mock_settings.TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
            mock_settings.SCRAPECREATORS_API_KEY = "test_key"
            registry = create_default_registry()
            harvester = registry.create_harvester("truth_social")
            assert isinstance(harvester, TruthSocialS3Harvester)
