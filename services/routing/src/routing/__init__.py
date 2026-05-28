"""Variance-aware routing model.

Hierarchical Bayesian log-normal fit on journey data (typically from
``services/synth-events``), three routing policies that consume the
posterior, and a head-to-head simulation harness that measures lift.
"""

__version__ = "0.0.0"
