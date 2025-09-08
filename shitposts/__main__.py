"""
CLI entry point for shitposts package.
"""
import asyncio
from shitposts.truth_social_s3_harvester import main

if __name__ == "__main__":
    asyncio.run(main())
