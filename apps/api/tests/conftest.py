import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))          # apps/api
sys.path.insert(0, str(HERE.parents[3]))          # repo root
os.environ.setdefault("DATABASE_URL", f"sqlite:///{HERE.parent / '.test.db'}")
