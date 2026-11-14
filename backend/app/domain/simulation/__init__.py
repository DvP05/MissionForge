"""Deterministic mission simulation (M14, architecture 9).

A deterministic discrete-event run over mission phases with resource checkpoints read from
the engineering analysis: not orbital propagation. Pure: no wall clock, env, network or
unseeded randomness; the only randomness source is ``prng.make_rng``.
"""
