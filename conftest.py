"""
Root-level conftest.py for pytest plugin registration.

pytest_plugins must be declared in a root-level conftest.py (not in subdirectories).
This requirement was enforced starting in pytest 8.x.
"""

pytest_plugins = ['pytest_asyncio']
