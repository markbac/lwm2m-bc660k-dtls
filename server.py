import os
import sys
import time
import signal
import asyncio
import json
import argparse
import threading
import webbrowser
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

from lwm2m_manager import LwM2MManager

# Parse Command Line Arguments
parser = argparse.ArgumentParser(description="Quectel BC660K LwM2M DTLS Client & Custom XML Studio")
parser.add_argument("--demo", "-d", action="store_true", help="Start studio in simulated LwM2M DTLS demo mode")
parser.add_argument("--port", "-p", type=str, default="COM3", help="Initial COM port to connect on startup (default: COM3)")
parser.add_argument("--baud", "-b", type=int, default=115200, help="Initial baud rate (default: 115200)")
parser.add_argument("--no-file-log", action="store_true", help="Disable writing serial logs to disk file")
args, _ = parser.parse_known_args()

app = FastAPI(title="Quectel BC660K LwM2M DTLS Client Studio")
manager = LwM2MManager(file_logging_enabled=not args.no_file_log)

active_connections: List[WebSocket] = []
loop = None

def broadcast(event_type: str, data: Any):
    if not active_connections:
        return
    message = json.dumps({"type": event_type, "data": data})
    if loop and loop.is_running():
        for connection in list(active_connections):
            asyncio.run_coroutine_threadsafe(connection.send_text(message), loop)

manager.register_callback(broadcast)

# --- Pydantic Models ---
class ConnectRequest(BaseModel):
    port: str
    baudrate: int = 115200

class DTLSConfigRequest(BaseModel):
    server_url: str
    port: int = 5684
    endpoint_name: str
    psk_identity: str
    psk_key: str

class NotifyRequest(BaseModel):
    object_id: int
    instance_id: int = 0
    resource_id: int
    value: Any
    val_type: Optional[str] = "string"

class AddObjectRequest(BaseModel):
    object_id: int
    instance_id: int = 0
    resource_ids: Optional[List[int]] = None

class XMLImportRequest(BaseModel):
    xml_content: str

class SendATRequest(BaseModel):
    command: str

# --- REST Endpoints ---
@app.get("/api/ports")
def get_ports():
    return {"ports": manager.get_ports()}

@app.get("/api/state")
def get_state():
    return manager.state

@app.post("/api/connect")
def connect_port(req: ConnectRequest):
    success = manager.connect(req.port, req.baudrate)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not connect to {req.port}")
    return {"status": "ok", "state": manager.state}

@app.post("/api/disconnect")
def disconnect_port():
    manager.disconnect()
    return {"status": "ok", "state": manager.state}

@app.post("/api/dtls/config")
def config_dtls(req: DTLSConfigRequest):
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Serial port not connected")
    res = manager.configure_dtls(req.server_url, req.port, req.endpoint_name, req.psk_identity, req.psk_key)
    return {"status": "ok", "response": res, "state": manager.state}

@app.post("/api/dtls/register")
def register_lwm2m():
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Serial port not connected")
    res = manager.register_lwm2m_client()
    return {"status": "ok", "response": res, "state": manager.state}

@app.get("/api/objects")
def get_objects():
    return {"objects": manager.db.get_all_objects()}

@app.post("/api/objects/import")
def import_xml(req: XMLImportRequest):
    try:
        parsed = manager.import_xml_object(req.xml_content)
        return {"status": "ok", "object": parsed, "objects": manager.db.get_all_objects()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"XML Parse Error: {e}")

@app.post("/api/objects/upload_xml")
async def upload_xml_file(file: UploadFile = File(...)):
    try:
        content = (await file.read()).decode("utf-8")
        parsed = manager.import_xml_object(content)
        return {"status": "ok", "object": parsed, "objects": manager.db.get_all_objects()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"XML Upload Error: {e}")

@app.post("/api/objects/add")
def add_object_instance(req: AddObjectRequest):
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Serial port not connected")
    res = manager.add_lwm2m_object_instance(req.object_id, req.instance_id, req.resource_ids)
    return {"status": "ok", "response": res}

@app.post("/api/notify")
def notify_resource(req: NotifyRequest):
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Serial port not connected")
    res = manager.notify_resource_value(req.object_id, req.instance_id, req.resource_id, req.value, req.val_type)
    return {"status": "ok", "response": res, "notifications": manager.db.get_notifications(limit=50)}

@app.get("/api/notifications")
def get_notifications():
    return {"notifications": manager.db.get_notifications(limit=100)}

@app.post("/api/send_at")
def send_at(req: SendATRequest):
    if not manager.is_connected:
        raise HTTPException(status_code=400, detail="Serial port not connected")
    resp = manager.send_at_command(req.command)
    return {"command": req.command, "response": resp}

@app.post("/api/shutdown")
def shutdown_server():
    print("\n[SYSTEM] Exit requested via Web UI. Shutting down cleanly...")
    manager.disconnect()

    def delayed_exit():
        time.sleep(0.5)
        print("[SYSTEM] Goodbye!")
        os._exit(0)

    threading.Thread(target=delayed_exit, daemon=True).start()
    return {"status": "ok", "message": "Server shutting down cleanly..."}

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    await websocket.send_text(json.dumps({"type": "state", "data": manager.state}))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)

# Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>LwM2M DTLS Studio loading...</h1>")

def setup_signal_handlers():
    def handle_signal(sig, frame):
        print(f"\n[SYSTEM] Signal {sig} received (Ctrl+C / Terminal Interrupt). Shutting down...")
        manager.disconnect()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except Exception as e:
        print(f"[SYSTEM] Signal handler notice: {e}")

if __name__ == "__main__":
    setup_signal_handlers()

    if args.demo:
        print("[STARTUP] Demo mode CLI flag '--demo' enabled. Starting simulator...")
        manager.enable_demo_mode()
    elif args.port:
        print(f"[STARTUP] Connecting to serial port {args.port} @ {args.baud} baud...")
        manager.connect(args.port, args.baud)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    port_num = 8081  # Port 8081 for new LwM2M project
    url = f"http://localhost:{port_num}"
    print(f"\n=======================================================")
    print(f"Quectel BC660K LwM2M DTLS Studio v{manager.VERSION} running at: {url}")
    print(f"Baud Rate: {args.baud}")
    print(f"Mode: {'SIMULATED DEMO (--demo)' if args.demo else 'REAL HARDWARE'}")
    print(f"Py-LogKit File Logging: {'ENABLED (lwm2m_dtls.log)' if not args.no_file_log else 'DISABLED'}")
    print(f"Press Ctrl+C in terminal or click Exit in Web UI to stop")
    print(f"=======================================================\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port_num, loop="asyncio")
    server = uvicorn.Server(config)
    try:
        loop.run_until_complete(server.serve())
    except (KeyboardInterrupt, SystemExit):
        print("\n[SYSTEM] Server process terminated.")
        manager.disconnect()
