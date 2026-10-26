"""NeighborHealth 2.0 API."""
import sys
from pathlib import Path

# Make the repo-level packages (pipeline/, ml/) importable when running from apps/api.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
