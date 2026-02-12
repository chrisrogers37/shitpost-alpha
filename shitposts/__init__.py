"""
Shitposts Package
Signal harvesting from multiple data sources.
"""

from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_registry import HarvesterRegistry, create_default_registry
from shitposts.harvester_models import HarvestResult, HarvestSummary, HarvesterConfig

__all__ = [
    "SignalHarvester",
    "HarvesterRegistry",
    "create_default_registry",
    "HarvestResult",
    "HarvestSummary",
    "HarvesterConfig",
]
