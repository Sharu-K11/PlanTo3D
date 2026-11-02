"""Shared test bootstrap. Import this before any `app.*` module."""

import os

# Keep app startup fast and independent of torch/weights; model tests opt in explicitly.
os.environ["SEGMENTATION_ENABLED"] = "false"
