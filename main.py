import os
import sys

# Ensure src/ package is on python path for cloud deployers
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from voice_call_agent.main import app  # noqa: F401
