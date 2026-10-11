"""Electron-owned JSON-lines sidecar; stdout is reserved for protocol messages."""
import argparse
import json
from pathlib import Path
import sys
import threading
import traceback
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.service import Service

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--resources", required=True)
    args = parser.parse_args()
    output_lock = threading.Lock()
    def emit(value):
        with output_lock:
            print(json.dumps(value, ensure_ascii=True), flush=True)
    service = Service(args.data, args.resources, emit)
    emit({"event": "ready", "data": service.state()})
    try:
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                result = service.call(request["method"], request.get("params") or {})
                emit({"id": request["id"], "result": result})
            except Exception as exc:
                emit({"id": request.get("id"), "error": str(exc)})
    finally:
        service.close()

if __name__ == "__main__":
    main()
