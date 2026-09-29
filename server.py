#!/usr/bin/env python3
"""RuView Web MVP: UDP receiver + local responsive dashboard (Python stdlib only)."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import socket, threading, json, time, struct, argparse, csv, os
from collections import deque

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
MAGIC_FEATURE = 0xC5110006
STATE = {
    "started_at": time.time(), "udp_packets": 0, "feature_packets": 0,
    "last_packet_at": None, "last_sender": None, "last_packet_type": None,
    "latest": None, "events": deque(maxlen=300), "status": "waiting",
    "recording": False, "record_path": None, "errors": deque(maxlen=50),
}
LOCK = threading.Lock()
STOP = threading.Event()

def parse_feature(data, addr):
    """Decode the known 60-byte Feature State layout; verify against your firmware header."""
    if len(data) < 60:
        return None
    try:
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != MAGIC_FEATURE:
            return None
        node, mode = data[4], data[5]
        seq = struct.unpack_from("<H", data, 6)[0]
        ts = struct.unpack_from("<Q", data, 8)[0]
        vals = struct.unpack_from("<9f", data, 16)
        qflags = struct.unpack_from("<H", data, 52)[0]
        names = ["motion", "presence", "respiration", "respiration_confidence",
                 "heart_rate", "heart_rate_confidence", "anomaly", "environment", "coherence"]
        result = {k: round(float(v), 5) for k, v in zip(names, vals)}
        result.update({"packet_type": "feature_state", "magic": f"0x{magic:08X}",
                       "node": node, "mode": mode, "seq": seq, "timestamp_raw": ts,
                       "qflags": qflags, "bytes": len(data), "sender": addr[0],
                       "received_at": time.time()})
        return result
    except (struct.error, ValueError):
        return None

def udp_worker(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.settimeout(1)
        with LOCK:
            STATE["status"] = f"listening on UDP {host}:{port}"
        while not STOP.is_set():
            try:
                data, addr = sock.recvfrom(8192)
            except socket.timeout:
                continue
            now = time.time()
            parsed = parse_feature(data, addr)
            with LOCK:
                STATE["udp_packets"] += 1
                STATE["last_packet_at"] = now
                STATE["last_sender"] = addr[0]
                STATE["last_packet_type"] = parsed["packet_type"] if parsed else data[:4].hex()
                if parsed:
                    STATE["feature_packets"] += 1
                    STATE["latest"] = parsed
                    event = {"at": now, "kind": "feature_state", "seq": parsed["seq"],
                             "motion": parsed["motion"], "presence": parsed["presence"]}
                    STATE["events"].appendleft(event)
                if STATE["recording"] and STATE["record_path"]:
                    try:
                        with open(STATE["record_path"], "a", encoding="utf-8") as f:
                            f.write(json.dumps({"received_at": now, "sender": addr[0],
                                                "raw_hex": data.hex(), "parsed": parsed},
                                               ensure_ascii=False) + "\n")
                    except OSError as e:
                        STATE["errors"].append(str(e))
    except OSError as e:
        with LOCK:
            STATE["status"] = "UDP error"
            STATE["errors"].append(str(e))
    finally:
        sock.close()

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/state":
            with LOCK:
                state = {k: v for k, v in STATE.items() if k not in ("events", "errors")}
                state["events"] = list(STATE["events"])[:30]
                state["errors"] = list(STATE["errors"])
            state["uptime_seconds"] = int(time.time() - STATE["started_at"])
            return self._send(200, json.dumps(state, ensure_ascii=False))
        if path == "/api/health":
            return self._send(200, '{"ok":true}')
        return self._send(404, '{"error":"not found"}')

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/record/start":
            rec_dir = BASE / "recordings"
            rec_dir.mkdir(exist_ok=True)
            name = time.strftime("capture_%Y%m%d_%H%M%S.jsonl")
            with LOCK:
                STATE["record_path"] = str(rec_dir / name)
                STATE["recording"] = True
            return self._send(200, json.dumps({"ok": True, "file": name}))
        if path == "/api/record/stop":
            with LOCK:
                STATE["recording"] = False
                path = STATE["record_path"]
            return self._send(200, json.dumps({"ok": True, "file": path}))
        return self._send(404, '{"error":"not found"}')

    def log_message(self, fmt, *args):
        # Keep console output compact.
        print("%s - %s" % (self.address_string(), fmt % args))

def main():
    p = argparse.ArgumentParser(description="RuView Web MVP")
    p.add_argument("--host", default="0.0.0.0", help="Web bind address; 0.0.0.0 enables LAN access")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--udp-host", default="0.0.0.0")
    p.add_argument("--udp-port", type=int, default=5005)
    args = p.parse_args()
    threading.Thread(target=udp_worker, args=(args.udp_host, args.udp_port), daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"RuView Web: http://127.0.0.1:{args.port}")
    print(f"LAN access: use this computer's LAN IP, port {args.port}")
    print(f"UDP receiver: {args.udp_host}:{args.udp_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set()
        server.server_close()

if __name__ == "__main__":
    main()
