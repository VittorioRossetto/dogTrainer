"""Write events to InfluxDB (v2 with token preferred, fallback to v1).

Usage:
- Configure `src/config.py` with INFLUX_URL and either INFLUX_TOKEN/ORG/BUCKET
  (for InfluxDB v2) or INFLUX_DB (for InfluxDB v1).
- The module exposes `write_event(envelope)` where `envelope` is the message
  dict produced by `host_comms.send_event` (keys: type,event,timestamp,payload).

The writer will try to import `influxdb_client` first (v2). If unavailable
or no token is configured it will attempt to use `influxdb` (v1) client.
"""
from typing import Any, Dict
import time
import json
import traceback
import config
import requests

_client_v2 = None
_write_api = None
_client_v1 = None

try:
    # Try InfluxDB v2 client
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    _HAS_V2 = True
except Exception:
    InfluxDBClient = None
    Point = None
    WritePrecision = None
    SYNCHRONOUS = None
    _HAS_V2 = False

if not _HAS_V2:
    try:
        # Try InfluxDB v1 client
        from influxdb import InfluxDBClient as InfluxDBClientV1
        _HAS_V1 = True
    except Exception:
        InfluxDBClientV1 = None
        _HAS_V1 = False
else:
    _HAS_V1 = False


def _setup_v2():
    global _client_v2, _write_api
    if _client_v2 is not None:
        return True
    url = getattr(config, "INFLUX_URL", "http://localhost:8086")
    token = getattr(config, "INFLUX_TOKEN", "")
    org = getattr(config, "INFLUX_ORG", "")
    bucket = getattr(config, "INFLUX_BUCKET", "dog_training")
    if not token:
        return False
    try:
        _client_v2 = InfluxDBClient(url=url, token=token, org=org)
        _write_api = _client_v2.write_api(write_options=SYNCHRONOUS)
        return True
    except Exception:
        traceback.print_exc()
        _client_v2 = None
        _write_api = None
        return False


def _setup_v1():
    global _client_v1
    if _client_v1 is not None:
        return True
    try:
        url = getattr(config, "INFLUX_URL", "http://localhost:8086")
        # influxdb v1 client expects host/port/db separately
        # parse URL like http://host:8086
        import urllib.parse as _up
        p = _up.urlparse(url)
        host = p.hostname or "localhost"
        port = p.port or 8086
        username = getattr(config, "INFLUX_USER", "")
        password = getattr(config, "INFLUX_PASS", "")
        db = getattr(config, "INFLUX_DB", "dog_training")
        _client_v1 = InfluxDBClientV1(host=host, port=port, username=username, password=password, database=db)
        return True
    except Exception:
        traceback.print_exc()
        _client_v1 = None
        return False


def _flatten_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert payload into flat key->value suitable for Influx fields.

    - Numeric and boolean values are preserved
    - Strings are preserved but large nested structures are JSON-encoded
    - Nested dicts are JSON-encoded under their top-level key
    """
    out = {}
    for k, v in (payload or {}).items():
        if v is None:
            continue
        if isinstance(v, (int, float, bool, str)):
            out[k] = v
        else:
            try:
                out[k] = json.dumps(v)
            except Exception:
                out[k] = str(v)
    return out


def write_event(envelope: Dict[str, Any]):
    """Write an event envelope to InfluxDB.

    `envelope` expected shape:
      {"type":"event","event":"pose_transition","timestamp":<float>,"payload":{...}}
    """
    try:
        # decide which client to use
        event_type = envelope.get("event")
        ts = envelope.get("timestamp") or time.time()
        payload = envelope.get("payload") or {}

        # Map event types to measurements, tags and fields
        def _build_record(event_type, payload):
            tags = {}
            fields = {}

            if event_type == "pose_transition":
                # tags: from,to ; fields: confidence
                tags["from"] = payload.get("from") or "unknown"
                tags["to"] = payload.get("to") or "unknown"
                if "confidence" in payload:
                    try:
                        fields["confidence"] = float(payload.get("confidence"))
                    except Exception:
                        fields["confidence"] = None
                measurement = "pose_transition"

            elif event_type == "servo_action":
                tags["action"] = payload.get("action") or "unknown"
                if "angle" in payload:
                    try:
                        fields["angle"] = float(payload.get("angle"))
                    except Exception:
                        fields["angle"] = None
                measurement = "servo_action"

            elif event_type == "treat_given":
                tags["reason"] = payload.get("reason") or "unknown"
                measurement = "treat_given"

            elif event_type == "audio_playback":
                fields["text"] = payload.get("text") or ""
                fields["length"] = len(fields["text"]) if fields["text"] else 0
                measurement = "audio_playback"

            elif event_type == "mode_changed" or event_type == "mode_change":
                tags["mode"] = payload.get("mode") or "unknown"
                measurement = "mode_change"

            elif event_type == "status":
                # payload may contain mode,dog_detected,pose,pose_confidence,stage
                fields.update(_flatten_payload(payload))
                measurement = "status"

            else:
                # generic fallback: store payload as fields and event tag
                fields.update(_flatten_payload(payload))
                tags["event"] = event_type or "unknown"
                fields.setdefault("event", event_type)
                measurement = event_type or "events"

            # remove None fields
            fields = {k: v for k, v in fields.items() if v is not None}
            return measurement, tags, fields

        measurement, tags, fields = _build_record(event_type, payload)

        # prefer v2
        if _HAS_V2 and _setup_v2():
            bucket = getattr(config, "INFLUX_BUCKET", "dog_training")
            org = getattr(config, "INFLUX_ORG", "")
            p = Point(measurement)
            for k, v in tags.items():
                p = p.tag(k, str(v))
            for k, v in fields.items():
                if isinstance(v, bool):
                    p = p.field(k, v)
                elif isinstance(v, (int, float)):
                    p = p.field(k, v)
                else:
                    p = p.field(k, str(v))
            # write point
            try:
                _write_api.write(bucket=bucket, org=org, record=p, write_precision=WritePrecision.S)
            except TypeError:
                _write_api.write(bucket=bucket, org=org, record=p)
            return True

        # fallback to v1
        if _HAS_V1 and _setup_v1():
            db = getattr(config, "INFLUX_DB", "dog_training")
            point = {
                "measurement": measurement,
                "tags": {k: str(v) for k, v in tags.items()},
                "time": int(ts * 1e9),  # nanoseconds
                "fields": fields,
            }
            _client_v1.write_points([point])
            return True

        # no client library available — try HTTP write to InfluxDB v1 `/write` endpoint
        db = getattr(config, "INFLUX_DB", "dog_training")
        url = getattr(config, "INFLUX_URL", "http://localhost:8086").rstrip("/")

        # build line protocol
        def _escape_tag(v: str) -> str:
            return str(v).replace("=", "\\=").replace(",", "\\,").replace(" ", "\\ ")

        def _format_field_value(v):
            if isinstance(v, bool):
                return "true" if v else "false"
            if isinstance(v, int) and not isinstance(v, bool):
                return str(v)
            if isinstance(v, float):
                # Influx accepts floats with decimal
                return repr(v)
            # string -> quoted
            s = str(v).replace('"', '\\"')
            return f'"{s}"'

        # tags ordered
        tag_parts = []
        for k in sorted(tags.keys()):
            tag_parts.append(f"{_escape_tag(k)}={_escape_tag(tags[k])}")

        field_parts = []
        for k in sorted(fields.keys()):
            field_parts.append(f"{k}={_format_field_value(fields[k])}")

        line = measurement
        if tag_parts:
            line += "," + ",".join(tag_parts)
        if field_parts:
            line += " " + ",".join(field_parts)
        # timestamp in nanoseconds
        ts_ns = int(ts * 1e9)
        line += f" {ts_ns}"

        write_url = url + "/write"
        params = {"db": db}
        try:
            resp = requests.post(write_url, params=params, data=line.encode("utf-8"), headers={"Content-Type": "text/plain"}, timeout=3)
            if resp.status_code in (200, 204):
                return True
            else:
                print(f"[INFLUX] HTTP write failed: {resp.status_code} {resp.text}")
                return False
        except Exception:
            print("[INFLUX] HTTP write error:")
            traceback.print_exc()
            return False

    except Exception:
        print("[INFLUX] Failed to write event:")
        traceback.print_exc()
        return False