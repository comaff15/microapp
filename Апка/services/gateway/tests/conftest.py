import os
import sys

# Gateway is not packaged as app/* for imports; add app/ directly for importing main.py
_GATEWAY_APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if _GATEWAY_APP_DIR not in sys.path:
    sys.path.insert(0, _GATEWAY_APP_DIR)
