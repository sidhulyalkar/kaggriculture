"""Historical V1 execution controller compatibility layer.

The maintained mechanics controller now lives in `submission.base_controller`.
Keeping the import here preserves the V1 comparison API without duplicating a
large source file and lets engine fixes apply consistently to local baselines.
"""
from submission.base_controller import *  # noqa: F401,F403
