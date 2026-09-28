import sqlite3
import os
import json
import time
from typing import Dict, Any, List, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "lwm2m_dtls.db")

class DBManager:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # LwM2M Objects schema table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lwm2m_objects (
                    object_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    urn TEXT,
                    resources_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # DTLS Security Credentials
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dtls_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_url TEXT NOT NULL,
                    port INTEGER DEFAULT 5684,
                    endpoint_name TEXT NOT NULL,
                    security_mode TEXT DEFAULT 'PSK',
                    psk_identity TEXT,
                    psk_key TEXT,
                    is_active INTEGER DEFAULT 1,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # LwM2M Notifications log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lwm2m_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    object_id INTEGER,
                    instance_id INTEGER,
                    resource_id INTEGER,
                    val_type TEXT,
                    val_data TEXT,
                    dtls_status TEXT,
                    at_response TEXT
                )
            """)
            
            conn.commit()

    def save_object(self, obj_data: Dict[str, Any]):
        """Saves or updates an OMA LwM2M XML Object schema."""
        object_id = obj_data["object_id"]
        name = obj_data["name"]
        description = obj_data.get("description", "")
        urn = obj_data.get("urn", "")
        resources_json = json.dumps(obj_data.get("resources", []))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lwm2m_objects (object_id, name, description, urn, resources_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(object_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    urn=excluded.urn,
                    resources_json=excluded.resources_json
            """, (object_id, name, description, urn, resources_json))
            conn.commit()

    def get_all_objects(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lwm2m_objects ORDER BY object_id ASC")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "object_id": r["object_id"],
                    "name": r["name"],
                    "description": r["description"],
                    "urn": r["urn"],
                    "resources": json.loads(r["resources_json"]),
                    "created_at": r["created_at"]
                })
            return results

    def save_dtls_config(self, config: Dict[str, Any]):
        server_url = config.get("server_url", "leshan.eclipseprojects.io")
        port = config.get("port", 5684)
        endpoint_name = config.get("endpoint_name", "bc660k-lwm2m-client")
        security_mode = config.get("security_mode", "PSK")
        psk_identity = config.get("psk_identity", "bc660k_identity")
        psk_key = config.get("psk_key", "0102030405060708090a0b0c0d0e0f10")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE dtls_config SET is_active = 0")
            cursor.execute("""
                INSERT INTO dtls_config (server_url, port, endpoint_name, security_mode, psk_identity, psk_key, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (server_url, port, endpoint_name, security_mode, psk_identity, psk_key))
            conn.commit()

    def get_active_dtls_config(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dtls_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                "server_url": "leshan.eclipseprojects.io",
                "port": 5684,
                "endpoint_name": "bc660k-lwm2m-node",
                "security_mode": "PSK",
                "psk_identity": "bc660k_identity",
                "psk_key": "0102030405060708090a0b0c0d0e0f10",
                "is_active": 1
            }

    def log_notification(self, object_id: int, instance_id: int, resource_id: int, val_type: str, val_data: str, dtls_status: str, at_response: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lwm2m_notifications (object_id, instance_id, resource_id, val_type, val_data, dtls_status, at_response)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (object_id, instance_id, resource_id, val_type, val_data, dtls_status, at_response))
            conn.commit()

    def get_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lwm2m_notifications ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
