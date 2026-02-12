"""
CLI entry point for shitposts package.

Supports:
    python -m shitposts                          # Truth Social (default)
    python -m shitposts --source truth_social    # Explicit source
    python -m shitposts --source twitter         # Future: Twitter source
"""
import asyncio
from shitposts.truth_social_s3_harvester import main

if __name__ == "__main__":
    asyncio.run(main())
