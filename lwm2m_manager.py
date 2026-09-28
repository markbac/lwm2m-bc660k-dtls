import time
import re
import os
import sys
import threading
import random
import subprocess
from typing import Dict, Any, List, Optional
import serial
import serial.tools.list_ports

from db_manager import DBManager
from xml_parser import LwM2MXMLParser
from pylogkit import setup_logging

__version__ = "1.2.0"
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "lwm2m_dtls.log")

class LwM2MManager:
    VERSION = __version__

    def __init__(self, file_logging_enabled: bool = True):
        self.ser: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.baudrate: int = 115200
        self.is_connected: bool = False
        self.is_demo: bool = False
        self.is_registered: bool = False

        self.lock = threading.Lock()
        self.running: bool = False
        self.callbacks = []
        self.db = DBManager()

        self.py_logger = setup_logging(
            name="LwM2M-DTLS",
            to_console=True,
            to_file=file_logging_enabled,
            file_path=LOG_FILE_PATH,
            level="DEBUG"
        )

        # Pre-seed database with default OMA XML sample objects
        self._seed_default_objects()

        self.dtls_config = self.db.get_active_dtls_config()

        # State Cache
        self.state = {
            "connected": False,
            "port": None,
            "baudrate": 115200,
            "mode": "DISCONNECTED",
            "dtls_status": "Not Configured",
            "registration_status": "Unregistered",
            "active_endpoint": self.dtls_config.get("endpoint_name", "bc660k-node-01"),
            "active_server": f"{self.dtls_config.get('server_url')}:{self.dtls_config.get('port')}",
            "objects": self.db.get_all_objects(),
            "notifications": self.db.get_notifications(limit=50),
            "logs": []
        }

    def _seed_default_objects(self):
        """Seed sample OMA XML objects into database if empty."""
        existing = self.db.get_all_objects()
        if not existing:
            samples_dir = os.path.join(os.path.dirname(__file__), "sample_objects")
            if os.path.exists(samples_dir):
                for f in os.listdir(samples_dir):
                    if f.endswith(".xml"):
                        path = os.path.join(samples_dir, f)
                        try:
                            parsed = LwM2MXMLParser.parse_xml_file(path)
                            self.db.save_object(parsed)
                            self.py_logger.info(f"Loaded XML Object Definition: {parsed['name']} (ID {parsed['object_id']})")
                        except Exception as e:
                            self.py_logger.error(f"Error parsing sample XML {f}: {e}")

    def register_callback(self, callback):
        self.callbacks.append(callback)

    def _notify(self, event_type: str, data: Any):
        for cb in self.callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass

    def log(self, text: str, direction: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        entry = {"timestamp": timestamp, "direction": direction, "text": text}
        self.state["logs"].append(entry)
        if len(self.state["logs"]) > 300:
            self.state["logs"].pop(0)

        if direction == "ERROR":
            self.py_logger.error(text)
        elif direction == "TX":
            self.py_logger.debug(f"TX> {text}")
        elif direction == "RX":
            self.py_logger.debug(f"RX< {text}")
        else:
            self.py_logger.info(text)

        self._notify("log", entry)

    def _reclaim_port(self, port: str):
        self.log(f"[WARNING] Port {port} is locked by another process! Attempting to free port handle (Tool v{self.VERSION})...", "WARNING")
        try:
            ps_script = f"Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -ne {os.getpid()} -and ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*server.py*') }} | Stop-Process -Force -ErrorAction SilentlyContinue"
            cmd = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "{ps_script}"'
            subprocess.run(cmd, shell=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.8)
        except Exception as e:
            self.log(f"[RECLAIM ERROR] Could not terminate locking process: {e}", "ERROR")

    @staticmethod
    def get_ports() -> List[Dict[str, str]]:
        ports = serial.tools.list_ports.comports()
        return [{"device": p.device, "description": p.description, "hardware_id": p.hwid} for p in ports]

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        self.disconnect()
        with self.lock:
            try:
                self.log(f"[SERIAL] Connecting to {port} @ {baudrate} baud (Tool v{self.VERSION})...", "INFO")
                try:
                    self.ser = serial.Serial(port, baudrate, timeout=1.5)
                except serial.SerialException as e:
                    if "PermissionError" in str(e) or "Access is denied" in str(e):
                        self._reclaim_port(port)
                        self.ser = serial.Serial(port, baudrate, timeout=1.5)
                    else:
                        raise e

                self.port = port
                self.baudrate = baudrate
                self.is_connected = True
                self.is_demo = False
                self.state["connected"] = True
                self.state["port"] = port
                self.state["mode"] = "REAL"
                self.running = True

                self._send_at_cmd_raw("AT\r\n")
                self.log(f"[SUCCESS] Connected to {port} for LwM2M operations.", "INFO")
                self._notify("state", self.state)
                return True
            except Exception as e:
                self.log(f"[ERROR] Could not open port {port} (Tool v{self.VERSION}): {e}", "ERROR")
                self.disconnect()
                return False

    def enable_demo_mode(self):
        self.disconnect()
        with self.lock:
            self.is_connected = True
            self.is_demo = True
            self.state["connected"] = True
            self.state["port"] = "DEMO-PORT (LwM2M DTLS Simulator)"
            self.state["mode"] = "DEMO"
            self.state["dtls_status"] = "DTLS PSK Configured (Simulated)"
            self.state["registration_status"] = "Registered (Leshan LwM2M Server)"
            self.is_registered = True
            self.running = True
            self.log("[DEMO MODE] Hardware simulator enabled for LwM2M DTLS testing.", "INFO")
            self._notify("state", self.state)
            return True

    def disconnect(self):
        self.running = False
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.is_connected = False
            self.is_demo = False
            self.is_registered = False
            self.state["connected"] = False
            self.state["mode"] = "DISCONNECTED"
            self.state["registration_status"] = "Unregistered"
            self.log("[SERIAL] Disconnected from serial port.", "INFO")
            self._notify("state", self.state)

    def configure_dtls(self, server_url: str, port: int, endpoint_name: str, psk_identity: str, psk_key: str) -> str:
        """
        Configures LwM2M Client over DTLS on Quectel BC660K.
        AT+QLWM2M="select",1
        AT+QLWM2M="endpoint","<endpoint>"
        AT+QLWM2M="server","<server>",<port>
        AT+QLWM2M="dtls",1,"<psk_id>","<psk_key>"
        """
        config = {
            "server_url": server_url,
            "port": port,
            "endpoint_name": endpoint_name,
            "security_mode": "PSK",
            "psk_identity": psk_identity,
            "psk_key": psk_key
        }
        self.db.save_dtls_config(config)
        self.dtls_config = config
        self.state["active_endpoint"] = endpoint_name
        self.state["active_server"] = f"{server_url}:{port}"

        self.log(f"[DTLS CONFIG] Configuring LwM2M DTLS PSK: Server={server_url}:{port}, EP='{endpoint_name}', PSK_ID='{psk_identity}'", "INFO")

        if self.is_demo:
            self.state["dtls_status"] = "DTLS PSK Active (Simulated)"
            self.log("[DTLS CONFIG] Simulated DTLS Security Handshake completed successfully.", "INFO")
            self._notify("state", self.state)
            return "OK"

        with self.lock:
            res1 = self._send_at_cmd_raw('AT+QLWM2M="select",1')
            res2 = self._send_at_cmd_raw(f'AT+QLWM2M="endpoint","{endpoint_name}"')
            res3 = self._send_at_cmd_raw(f'AT+QLWM2M="server","{server_url}",{port}')
            res4 = self._send_at_cmd_raw(f'AT+QLWM2M="dtls",1,"{psk_identity}","{psk_key}"')

            if "OK" in res4:
                self.state["dtls_status"] = f"DTLS PSK Enabled ({server_url}:{port})"
                self.log("[DTLS OK] DTLS Security Parameters successfully saved to Quectel module.", "INFO")
            else:
                self.state["dtls_status"] = "DTLS Config Error"

            self._notify("state", self.state)
            return f"{res1}\n{res2}\n{res3}\n{res4}"

    def register_lwm2m_client(self) -> str:
        """Triggers AT+QLWM2M="register" to perform DTLS Handshake & Registration."""
        self.log(f"[LwM2M REGISTRATION] Initiating DTLS Handshake with {self.state['active_server']}...", "INFO")

        if self.is_demo:
            time.sleep(1.0)
            self.is_registered = True
            self.state["registration_status"] = "Registered (Leshan LwM2M Server)"
            self.log("[LwM2M OK] Registered with LwM2M Server over DTLS PSK.", "INFO")
            self._notify("state", self.state)
            return "OK"

        with self.lock:
            resp = self._send_at_cmd_raw('AT+QLWM2M="register"', timeout_sec=15.0)
            if "OK" in resp or "+QLWM2M: 0" in resp:
                self.is_registered = True
                self.state["registration_status"] = "Registered"
                self.log("[LwM2M REGISTRATION SUCCESS] LwM2M Client registered over DTLS.", "INFO")
            else:
                self.state["registration_status"] = "Registration Failed"
                self.log("[LwM2M REGISTRATION ERROR] Registration failed or timed out.", "ERROR")

            self._notify("state", self.state)
            return resp

    def add_lwm2m_object_instance(self, object_id: int, instance_id: int = 0, resource_ids: Optional[List[int]] = None) -> str:
        """
        Adds LwM2M Object instance to Quectel stack.
        AT+QLWM2M="addobj",<obj_id>,<inst_id>,<count>,"<res_ids>"
        """
        if resource_ids is None:
            # Find resources from DB
            objs = self.db.get_all_objects()
            match = next((o for o in objs if o["object_id"] == object_id), None)
            if match:
                resource_ids = [r["id"] for r in match["resources"]]
            else:
                resource_ids = [0]

        res_str = ",".join(str(r) for r in resource_ids)
        count = len(resource_ids)
        cmd = f'AT+QLWM2M="addobj",{object_id},{instance_id},{count},"{res_str}"'

        self.log(f"[LwM2M OBJECT ADD] Registering Object {object_id}/{instance_id} ({count} resources)...", "INFO")

        if self.is_demo:
            self.log(f"[LwM2M OK] Added Object {object_id}/{instance_id} to LwM2M Client stack.", "INFO")
            return "OK"

        with self.lock:
            return self._send_at_cmd_raw(cmd)

    def notify_resource_value(self, object_id: int, instance_id: int, resource_id: int, value: Any, val_type: Optional[str] = None) -> str:
        """
        Sends DTLS LwM2M Resource Notification to LwM2M Server.
        AT+QLWM2M="notify",<obj_id>,<inst_id>,<res_id>,<type>,"<val>"
        Types: 1=String, 2=Integer, 3=Float, 4=Boolean, 5=Opaque
        """
        type_map = {"string": 1, "integer": 2, "float": 3, "boolean": 4, "opaque": 5}
        
        if not val_type:
            val_type = "string"
            # Deduce type from value if possible
            if isinstance(value, bool):
                val_type = "boolean"
            elif isinstance(value, int):
                val_type = "integer"
            elif isinstance(value, float):
                val_type = "float"

        type_code = type_map.get(str(val_type).lower(), 1)
        val_str = str(value)
        if isinstance(value, bool):
            val_str = "1" if value else "0"

        cmd = f'AT+QLWM2M="notify",{object_id},{instance_id},{resource_id},{type_code},"{val_str}"'
        self.log(f"[DTLS NOTIFY] Sending Notification: /{object_id}/{instance_id}/{resource_id} = '{val_str}' (Type {type_code})...", "INFO")

        if self.is_demo:
            time.sleep(0.3)
            self.db.log_notification(object_id, instance_id, resource_id, str(val_type), val_str, "DTLS_OK", "OK")
            self.state["notifications"] = self.db.get_notifications(limit=50)
            self.log(f"[DTLS NOTIFY SUCCESS] DTLS Packet delivered to LwM2M Server.", "INFO")
            self._notify("state", self.state)
            return "OK"

        with self.lock:
            resp = self._send_at_cmd_raw(cmd, timeout_sec=5.0)
            dtls_status = "DTLS_OK" if "OK" in resp else "DTLS_ERROR"
            self.db.log_notification(object_id, instance_id, resource_id, str(val_type), val_str, dtls_status, resp)
            self.state["notifications"] = self.db.get_notifications(limit=50)
            self._notify("state", self.state)
            return resp

    def import_xml_object(self, xml_content: str) -> Dict[str, Any]:
        """Imports custom OMA LwM2M XML definition string into database."""
        parsed = LwM2MXMLParser.parse_xml_string(xml_content)
        self.db.save_object(parsed)
        self.state["objects"] = self.db.get_all_objects()
        self.log(f"[XML IMPORT] Successfully imported Custom LwM2M Object: '{parsed['name']}' (ID {parsed['object_id']}) with {len(parsed['resources'])} resources.", "INFO")
        self._notify("state", self.state)
        return parsed

    def _send_at_cmd_raw(self, cmd: str, timeout_sec: float = 2.0) -> str:
        if not self.ser or not self.ser.is_open:
            return "ERROR: Port not open"

        if not cmd.endswith("\r\n"):
            cmd_str = cmd + "\r\n"
        else:
            cmd_str = cmd

        self.log(cmd.strip(), "TX")
        try:
            self.ser.write(cmd_str.encode("ascii", errors="ignore"))
            time.sleep(0.1)
            response = ""
            start = time.time()
            timed_out = True

            while time.time() - start < timeout_sec:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting).decode("ascii", errors="replace")
                    response += chunk
                    if "OK\r\n" in response or "ERROR\r\n" in response or "+QLWM2M:" in response:
                        timed_out = False
                        break
                time.sleep(0.04)

            if timed_out and not response:
                self.log(f"[TIMEOUT] No response for '{cmd.strip()}' after {timeout_sec}s.", "ERROR")
                return "ERROR: Timeout"

            self.log(response.strip(), "RX")
            return response
        except Exception as e:
            self.log(f"[SERIAL ERROR] TX/RX failure on {cmd.strip()}: {e}", "ERROR")
            return f"ERROR: {e}"

    def send_at_command(self, cmd: str) -> str:
        if self.is_demo:
            self.log(cmd.strip(), "TX")
            resp = "OK\r\n"
            self.log(resp.strip(), "RX")
            return resp

        with self.lock:
            return self._send_at_cmd_raw(cmd, timeout_sec=3.0)
