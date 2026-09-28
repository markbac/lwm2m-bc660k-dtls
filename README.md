# Quectel BC660K LwM2M DTLS Client & Custom XML Studio

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Modem](https://img.shields.io/badge/Quectel-BC660K--GL-orange.svg)
![Security](https://img.shields.io/badge/DTLS-PSK%20%28AES--128--CCM%29-green.svg)

An end-to-end Lightweight M2M (LwM2M) telemetry suite and visual studio for the **Quectel BC660K-GL LTE Cat NB2 modem**. Features native DTLS Pre-Shared Key (PSK) security configuration, dynamic OMA LwM2M XML schema importing, resource telemetry notifications, Py-LogKit serial logging, and a web dashboard on port `8081`.

---

## 🌟 Key Features

1. **Native Quectel BC660K LwM2M Stack Integration**:
   - Executes AT commands for selecting LwM2M stack, setting endpoints, configuring DTLS security parameters, and handshaking with LwM2M servers (e.g. Eclipse Leshan LwM2M server on port `5684`).
2. **DTLS PSK (Pre-Shared Key) Security**:
   - Full configuration of PSK Identity and PSK Hex/Secret Keys (`AT+QLWM2M="dtls",1,"<psk_id>","<psk_key>"`).
3. **Dynamic Custom OMA LwM2M XML Schema Parser**:
   - Drag-and-drop or paste standard OMA LwM2M XML object definitions (Objects 0 to 65535).
   - Pre-loaded sample objects:
     - `3_Device.xml` (OMA Device Object 3)
     - `3303_Temperature.xml` (IPSO Temperature Object 3303)
     - `10241_CustomSensor.xml` (Custom Industrial Sensor 10241)
4. **LwM2M Studio Web Dashboard**:
   - Modern dark-themed dashboard running on **http://localhost:8081**.
   - Live LwM2M object tree browser with resource lookup and type casting (Float, String, Integer, Boolean, Opaque).
   - Instant resource telemetry transmitter (`AT+QLWM2M="notify"`).
   - Historical transmission log stored in SQLite (`lwm2m_dtls.db`).
5. **Py-LogKit Serial Logging & Console**:
   - Real-time color-coded serial log output (`pylogkit`) with file-logging option (`lwm2m_dtls.log`).
6. **Hardware & Demo Mode**:
   - `--demo` mode simulates full LwM2M handshake, DTLS PSK exchange, and telemetry notifications without physical hardware attached.

---

## 🛰️ Quectel BC660K LwM2M AT Commands Reference

| AT Command | Function / Usage |
|---|---|
| `AT+QLWM2M="select",1` | Select native LwM2M stack protocol |
| `AT+QLWM2M="endpoint","<ep_name>"` | Set LwM2M client endpoint URN name |
| `AT+QLWM2M="server","<url>",<port>` | Set LwM2M bootstrap/registration server (e.g., `leshan.eclipseprojects.io:5684`) |
| `AT+QLWM2M="dtls",1,"<psk_id>","<psk_key>"` | Enable DTLS mode (1=PSK) with PSK Identity & Hex Key |
| `AT+QLWM2M="addobj",<obj_id>,<inst_id>,...` | Register LwM2M object instance & resources with modem |
| `AT+QLWM2M="register"` | Send LwM2M DTLS registration request to server |
| `AT+QLWM2M="update"` | Update active LwM2M registration registration lifetime |
| `AT+QLWM2M="notify",1,1,<obj>,<inst>,<res>,<type>,<val>` | Transmit resource telemetry value over DTLS link |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Quectel BC660K-GL board connected over USB-to-UART (Default: `COM3` @ `115200` baud)

### Installation

```bash
git clone https://github.com/markbac/lwm2m-bc660k-dtls.git
cd lwm2m-bc660k-dtls
pip install -r requirements.txt
```

### Running the Studio

#### Hardware Mode (Connected modem on COM3)
```bash
python server.py --port COM3 --baud 115200
```

#### Demo Mode (Simulated LwM2M hardware)
```bash
python server.py --demo
```

Open **http://localhost:8081** in your web browser.

---

## 📁 Repository Structure

```
lwm2m-bc660k-dtls/
├── server.py              # FastAPI server on port 8081 & WebSockets
├── lwm2m_manager.py       # BC660K LwM2M & DTLS AT Command Engine
├── xml_parser.py          # OMA LwM2M XML Schema Parser
├── db_manager.py          # SQLite database storage (lwm2m_dtls.db)
├── pylogkit/              # Py-LogKit serial logging framework
├── sample_objects/        # Standard & Custom OMA LwM2M XML definitions
│   ├── 3_Device.xml
│   ├── 3303_Temperature.xml
│   └── 10241_CustomSensor.xml
├── static/
│   ├── index.html         # LwM2M Studio Web Dashboard
│   ├── css/style.css      # Dark telemetry theme styling
│   └── js/app.js          # REST & WebSocket client interface
├── requirements.txt       # Project dependencies
└── README.md              # Documentation
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
