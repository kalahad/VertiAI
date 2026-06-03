# -*- coding: utf-8 -*-
"""
VertiAI - Data Layer (Session 3 + Session 5 + Session 9)
SQLite cache + region thresholds + last_upload + delete_cache
"""

import os
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "VERTIAI_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vertiai.db"),
)
_DATA_DIR = os.path.dirname(DB_PATH)


def _connect():
    if _DATA_DIR:
        os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS soundings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                station       TEXT NOT NULL,
                datetime_utc  TEXT NOT NULL,
                raw           TEXT,
                indices_json  TEXT,
                created_at    TEXT NOT NULL,
                UNIQUE(station, datetime_utc)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_dt ON soundings(station, datetime_utc)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS region_thresholds (
                region      TEXT PRIMARY KEY,
                payload     TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS last_upload (
                id       INTEGER PRIMARY KEY CHECK(id=1),
                payload  TEXT NOT NULL,
                saved_at TEXT NOT NULL
            )
        """)


def make_key(station, year, month, day, hour):
    dt = datetime(int(year), int(month), int(day), int(hour), tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:00:00Z")


# ==================== Sounding Cache ====================

def get_cached(station, datetime_utc):
    with _connect() as conn:
        row = conn.execute(
            "SELECT raw, indices_json, created_at FROM soundings "
            "WHERE station = ? AND datetime_utc = ?",
            (str(station), datetime_utc),
        ).fetchone()
    if row is None:
        return None
    return {
        "raw": row["raw"],
        "result": json.loads(row["indices_json"]) if row["indices_json"] else None,
        "created_at": row["created_at"],
    }


def save_cache(station, datetime_utc, raw, result):
    payload = json.dumps(result, ensure_ascii=False)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO soundings (station, datetime_utc, raw, indices_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(station, datetime_utc)
            DO UPDATE SET raw=excluded.raw,
                          indices_json=excluded.indices_json,
                          created_at=excluded.created_at
        """, (str(station), datetime_utc, raw, payload, now))


def delete_cache(datetime_utc, station=None):
    """ลบ cache entry ตาม datetime_utc + station (Session 9)"""
    if station:
        sql = "DELETE FROM soundings WHERE datetime_utc = ? AND station = ?"
        params = (str(datetime_utc), str(station))
    else:
        sql = "DELETE FROM soundings WHERE datetime_utc = ?"
        params = (str(datetime_utc),)
    with _connect() as conn:
        conn.execute(sql, params)


def list_history(station=None, year=None):
    sql = "SELECT station, datetime_utc, created_at FROM soundings WHERE 1=1"
    params = []
    if station:
        sql += " AND station = ?"
        params.append(str(station))
    if year:
        sql += " AND substr(datetime_utc, 1, 4) = ?"
        params.append(str(int(year)))
    sql += " ORDER BY datetime_utc DESC LIMIT 500"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ==================== Region Thresholds ====================

def get_region_threshold(region):
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM region_thresholds WHERE region = ?", (str(region),)
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def get_all_region_thresholds():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT region, payload FROM region_thresholds"
        ).fetchall()
    return {r["region"]: json.loads(r["payload"]) for r in rows}


def save_region_threshold(region, payload):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps(payload, ensure_ascii=False)
    with _connect() as conn:
        conn.execute("""
            INSERT INTO region_thresholds (region, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(region) DO UPDATE SET
                payload=excluded.payload, updated_at=excluded.updated_at
        """, (str(region), body, now))


def delete_region_threshold(region):
    with _connect() as conn:
        conn.execute("DELETE FROM region_thresholds WHERE region = ?", (str(region),))


# ==================== Last Upload (Session 8) ====================

def save_last_upload(result: dict):
    """บันทึกผลอัปโหลดล่าสุด (1 แถวเสมอ — UPSERT id=1)"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = json.dumps(result, ensure_ascii=False, default=lambda o: None)
    with _connect() as conn:
        conn.execute("""
            INSERT INTO last_upload (id, payload, saved_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, saved_at=excluded.saved_at
        """, (payload, now))


def get_last_upload():
    """คืน dict ผลอัปโหลดล่าสุด หรือ None"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM last_upload WHERE id = 1"
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except Exception:
        return None
