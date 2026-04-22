#!/usr/bin/env python3
"""Shared database guard adapter for module-layer code.

This keeps most of the codebase from importing legacy db_guard directly.
"""

from __future__ import annotations

from capabilities.storage.db_guard import dsn_for, write_guard

__all__ = ["dsn_for", "write_guard"]
