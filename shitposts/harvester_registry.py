"""
Harvester Registry
Config-driven discovery and management of signal harvesters.
"""

from typing import Dict, List, Optional, Type

from shit.logging import get_service_logger
from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_models import HarvesterConfig

logger = get_service_logger("harvester_registry")


class HarvesterRegistry:
    """Registry for signal harvesters.

    Usage:
        registry = HarvesterRegistry()
        registry.register("truth_social", TruthSocialS3Harvester)
        registry.register("twitter", TwitterHarvester)

        harvesters = registry.create_all_enabled(mode="incremental")
        for harvester in harvesters:
            await harvester.initialize()
            async for result in harvester.harvest():
                process(result)
    """

    def __init__(self):
        self._registry: Dict[str, Type[SignalHarvester]] = {}
        self._configs: Dict[str, HarvesterConfig] = {}

    def register(
        self,
        source_name: str,
        harvester_class: Type[SignalHarvester],
        config: Optional[HarvesterConfig] = None,
    ) -> None:
        """Register a harvester class for a source.

        Args:
            source_name: Unique source identifier (e.g., "truth_social")
            harvester_class: The harvester class (not an instance)
            config: Optional configuration override
        """
        if not issubclass(harvester_class, SignalHarvester):
            raise TypeError(
                f"{harvester_class.__name__} must be a subclass of SignalHarvester"
            )

        self._registry[source_name] = harvester_class
        if config:
            self._configs[source_name] = config
        else:
            self._configs[source_name] = HarvesterConfig(source_name=source_name)

        logger.info(f"Registered harvester: {source_name} -> {harvester_class.__name__}")

    def unregister(self, source_name: str) -> None:
        """Remove a harvester from the registry."""
        self._registry.pop(source_name, None)
        self._configs.pop(source_name, None)
        logger.info(f"Unregistered harvester: {source_name}")

    def get_class(self, source_name: str) -> Optional[Type[SignalHarvester]]:
        """Get the harvester class for a source."""
        return self._registry.get(source_name)

    def get_config(self, source_name: str) -> Optional[HarvesterConfig]:
        """Get the configuration for a source."""
        return self._configs.get(source_name)

    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self._registry.keys())

    def list_enabled_sources(self) -> List[str]:
        """List source names where the harvester is enabled."""
        return [
            name for name, config in self._configs.items()
            if config.enabled
        ]

    def create_harvester(
        self,
        source_name: str,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> SignalHarvester:
        """Create a harvester instance for a specific source.

        Args:
            source_name: Which source to create
            mode: Harvesting mode
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum items to harvest
            **kwargs: Source-specific arguments

        Returns:
            Configured harvester instance

        Raises:
            KeyError: If source_name is not registered
        """
        if source_name not in self._registry:
            raise KeyError(
                f"Unknown source: '{source_name}'. "
                f"Registered sources: {self.list_sources()}"
            )

        cls = self._registry[source_name]
        return cls(
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            **kwargs,
        )

    def create_all_enabled(
        self,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[SignalHarvester]:
        """Create harvester instances for all enabled sources.

        Args:
            mode: Harvesting mode (applied to all)
            start_date: Start date (applied to all)
            end_date: End date (applied to all)
            limit: Limit (applied to all)

        Returns:
            List of configured harvester instances
        """
        harvesters = []
        for source_name in self.list_enabled_sources():
            config = self._configs[source_name]
            extra_kwargs = config.extra if config.extra else {}

            harvester = self.create_harvester(
                source_name=source_name,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                **extra_kwargs,
            )
            harvesters.append(harvester)

        return harvesters


def create_default_registry() -> HarvesterRegistry:
    """Create the default registry with all known harvesters.

    This is the single place that wires up which sources are available.
    """
    from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester

    registry = HarvesterRegistry()

    # Register Truth Social (always enabled - it's the primary source)
    registry.register(
        "truth_social",
        TruthSocialS3Harvester,
        HarvesterConfig(source_name="truth_social", enabled=True),
    )

    # Future sources will be registered here:
    # registry.register("twitter", TwitterHarvester, HarvesterConfig(..., enabled=False))

    return registry
