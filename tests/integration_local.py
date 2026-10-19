"""Real HTTP/PostgreSQL checks in a disposable database, never the journal DB."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import asyncpg


ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL = os.environ["DATABASE_URL"]
DB_NAME = "learningsteps_test_" + uuid4().hex
TEST_URL = urlunsplit(urlsplit(ADMIN_URL)._replace(path="/" + DB_NAME))
BASE = "http://127.0.0.1:8001"
RESULTS = []
BODY_MARKER = "PRIVATE_SYNTHETIC_BODY_" + uuid4().hex


def record(name, condition, actual=None):
    RESULTS.append({"test": name, "passed": bool(condition), "actual": actual})
    if not condition:
        raise AssertionError(name)


def request(method, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(BASE + path, data=body, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read())


async def create_database():
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        await conn.execute(f'CREATE DATABASE "{DB_NAME}"')
    finally:
        await conn.close()
    try:
        conn = await asyncpg.connect(TEST_URL)
        try:
            sql = "\n".join(line for line in (ROOT / "database_setup.sql").read_text().splitlines()
                            if not line.lstrip().startswith("\\"))
            await conn.execute(sql)
        finally:
            await conn.close()
    except Exception:
        await drop_database()
        raise


async def drop_database():
    # DB_NAME is generated here; this never targets the configured journal DB.
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        await conn.execute(f'DROP DATABASE "{DB_NAME}" WITH (FORCE)')
    finally:
        await conn.close()


def start_server(log):
    env = dict(os.environ, DATABASE_URL=TEST_URL)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd=ROOT / "api", env=env, stdout=log, stderr=log,
    )
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Isolated API process exited during startup")
        try:
            if request("GET", "/openapi.json")[0] == 200:
                return process
        except (URLError, TimeoutError):
            pass
        time.sleep(0.2)
    process.terminate()
    process.wait(timeout=15)
    raise RuntimeError("Isolated API startup timed out")


def stop_server(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=15)


def check_endpoints():
    status, listing = request("GET", "/entries")
    record("Isolated database initially empty", status == 200 and listing["count"] == 0)
    original = {"work": "  " + BODY_MARKER + "  ", "struggle": "Keep this field", "intention": "Keep this too"}
    status, result = request("POST", "/entries", original)
    record("Create entry", status == 200, status)
    entry = result["entry"]
    entry_id = entry["id"]
    record("Normalize surrounding whitespace", entry["work"] == BODY_MARKER)
    record("UTC creation timestamp", datetime.fromisoformat(entry["created_at"]).utcoffset().total_seconds() == 0)
    status, fetched = request("GET", "/entries/" + entry_id)
    record("Read single entry", status == 200 and fetched == entry, status)
    status, listing = request("GET", "/entries")
    record("List includes created entry", status == 200 and any(e["id"] == entry_id for e in listing["entries"]))
    status, updated = request("PATCH", "/entries/" + entry_id, {"work": "Updated work"})
    record("Patch changes supplied field", status == 200 and updated["work"] == "Updated work")
    record("Patch preserves omitted fields", updated["struggle"] == "Keep this field" and updated["intention"] == "Keep this too")
    record("Patch preserves identity and creation time", updated["id"] == entry_id and updated["created_at"] == entry["created_at"])
    record("Patch advances update time", datetime.fromisoformat(updated["updated_at"]) >= datetime.fromisoformat(entry["updated_at"]))
    status, fetched = request("GET", "/entries/" + entry_id)
    record("Patch response matches stored entry", status == 200 and fetched == updated)

    invalid_patches = [({}, "empty patch"), ({"work": None}, "null value"),
                       ({"work": " "}, "whitespace only"), ({"work": "x" * 257}, "too long"),
                       ({"work": 123}, "wrong type"), ({"id": str(uuid4())}, "immutable ID"),
                       ({"created_at": "2020-01-01T00:00:00Z"}, "immutable timestamp"),
                       ({"unknown": "field"}, "unknown field")]
    for payload, label in invalid_patches:
        status, _ = request("PATCH", "/entries/" + entry_id, payload)
        record("Reject " + label, status == 422, status)
    record("Invalid patches do not change data", request("GET", "/entries/" + entry_id)[1] == fetched)

    for payload, label in [({"work": "missing others"}, "missing fields"),
                           ({"work": "", "struggle": "a", "intention": "b"}, "empty field"),
                           ({"work": "a", "struggle": "b", "intention": "c", "id": "injected"}, "extra create field")]:
        status, _ = request("POST", "/entries", payload)
        record("Reject create with " + label, status == 422, status)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request, "PATCH", "/entries/" + entry_id, payload)
                   for payload in ({"struggle": "Concurrent struggle"}, {"intention": "Concurrent intention"})]
        record("Concurrent updates succeed", all(f.result()[0] == 200 for f in futures))
    persisted = request("GET", "/entries/" + entry_id)[1]
    record("Concurrent updates preserve both fields", persisted["struggle"] == "Concurrent struggle" and persisted["intention"] == "Concurrent intention")

    missing = str(uuid4())
    for method, payload in [("GET", None), ("PATCH", {"work": "missing"}), ("DELETE", None)]:
        status, _ = request(method, "/entries/" + missing, payload)
        record(method + " unknown ID returns 404", status == 404, status)
    for method, payload in [("GET", None), ("PATCH", {"work": "bad ID"}), ("DELETE", None)]:
        status, _ = request(method, "/entries/not-a-uuid", payload)
        record(method + " invalid ID returns 422", status == 422, status)
    status, _ = request("DELETE", "/entries/" + entry_id)
    record("Delete single entry", status == 200, status)
    record("Deleted entry no longer readable", request("GET", "/entries/" + entry_id)[0] == 404)
    record("Repeat delete returns 404", request("DELETE", "/entries/" + entry_id)[0] == 404)

    status, result = request("POST", "/entries", {"work": "Restart probe", "struggle": "None", "intention": "Persist"})
    record("Create restart probe", status == 200)
    return result["entry"]


def main():
    process = None
    created = False
    failure = None
    cleanup_ok = False
    with tempfile.TemporaryFile(mode="w+") as log:
        try:
            asyncio.run(create_database())
            created = True
            process = start_server(log)
            probe = check_endpoints()
            stop_server(process)
            process = start_server(log)
            status, fetched = request("GET", "/entries/" + probe["id"])
            record("Persistence after API process restart", status == 200 and fetched == probe)
            request("POST", "/entries", {"work": "Delete-all probe", "struggle": "None", "intention": "Test"})
            record("Delete-all test has multiple rows", request("GET", "/entries")[1]["count"] >= 2)
            status, _ = request("DELETE", "/entries")
            record("Delete all in isolated database", status == 200 and request("GET", "/entries")[1]["count"] == 0)
            stop_server(process)
            log.seek(0)
            logs = log.read()
            record("Startup message logged", "LearningSteps API started" in logs)
            record("Shutdown message logged", "LearningSteps API stopped" in logs)
            record("Journal payload absent from logs", BODY_MARKER not in logs)
        except Exception as error:
            failure = type(error).__name__ + ": " + str(error)
        finally:
            stop_server(process)
            if created:
                asyncio.run(drop_database())
                cleanup_ok = True
    report = {"time_utc": datetime.now(timezone.utc).isoformat(), "environment": "LOCAL_ISOLATED_TEST_DATABASE_NOT_AZURE",
              "results": RESULTS, "passed": sum(r["passed"] for r in RESULTS), "total": len(RESULTS),
              "test_database_removed": cleanup_ok, "error": failure}
    print(json.dumps(report, indent=2))
    return 1 if failure else 0


if __name__ == "__main__":
    sys.exit(main())
