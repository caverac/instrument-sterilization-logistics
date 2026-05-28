"""Synthetic journey generator.

Produces parquet rows that look like what the projector would emit if it
were running against a real event stream. Used as the input data set for
modeling work (variance-aware routing, preference-card learning) before
real client data is available.
"""

__version__ = "0.0.0"
