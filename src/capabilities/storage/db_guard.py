#!/usr/bin/env python3
"""Database write guard: advisory lock + required-table preflight check."""

from __future__ import annotations

from modules.runtime.adapters.db import dsn_for, ensure_tables_exist, write_guard
