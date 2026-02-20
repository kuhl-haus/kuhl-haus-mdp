"""Data models for market data analysis pipeline results and cache structures.

Provides dataclasses used across the MDP system for passing analyzed market data
between components (analyzers, cache, publishers). No business logic; pure data
containers with optional serialization helpers.
"""
