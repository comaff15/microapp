import os
import sys


def activate_service_app(service_root: str) -> None:
    service_root = os.path.abspath(service_root)

    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]

    if service_root in sys.path:
        sys.path.remove(service_root)
    sys.path.insert(0, service_root)
