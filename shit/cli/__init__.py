"""
Shared CLI utilities for Shitpost-Alpha.

Provides reusable argument definitions and validation logic used by
multiple CLI modules (shitpost_ai, shitposts, shitvault).
"""

from .shared_args import add_standard_arguments, validate_standard_args

__all__ = [
    "add_standard_arguments",
    "validate_standard_args",
]
