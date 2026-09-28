// Quectel BC660K LwM2M DTLS Studio App JS

document.addEventListener('DOMContentLoaded', () => {
    // --- State & Variables ---
    let ws = null;
    let isConnected = false;
    let registeredObjects = [];

    // --- DOM Elements ---
    const portSelect = document.getElementById('portSelect');
    const baudSelect = document.getElementById('baudSelect');
    const refreshPortsBtn = document.getElementById('refreshPortsBtn');
    const connectBtn = document.getElementById('connectBtn');
    const exitBtn = document.getElementById('exitBtn');
    const connectionStatus = document.getElementById('connectionStatus');
    const statusText = document.getElementById('statusText');

    // DTLS Controls
    const dtlsServerInput = document.getElementById('dtlsServerInput');
    const dtlsPortInput = document.getElementById('dtlsPortInput');
    const endpointInput = document.getElementById('endpointInput');
    const pskIdInput = document.getElementById('pskIdInput');
    const pskKeyInput = document.getElementById('pskKeyInput');
    const saveDtlsBtn = document.getElementById('saveDtlsBtn');
    const registerBtn = document.getElementById('registerBtn');
    const dtlsStatusBadge = document.getElementById('dtlsStatusBadge');

    // Reg State Info
    const activeEpVal = document.getElementById('activeEpVal');
    const activeServerVal = document.getElementById('activeServerVal');
    const regStatusVal = document.getElementById('regStatusVal');
    const dtlsModeVal = document.getElementById('dtlsModeVal');

    // XML Import Controls
    const xmlFileInput = document.getElementById('xmlFileInput');
    const uploadDropzone = document.querySelector('.upload-dropzone');
    const xmlPasteArea = document.getElementById('xmlPasteArea');
    const importPasteBtn = document.getElementById('importPasteBtn');

    // LwM2M Objects Tree
    const objectsTree = document.getElementById('objectsTree');
    const objectCountBadge = document.getElementById('objectCountBadge');
    const selectedObjectBadge = document.getElementById('selectedObjectBadge');

    // Resource Notifier
    const notifyObjId = document.getElementById('notifyObjId');
    const notifyInstId = document.getElementById('notifyInstId');
    const notifyResId = document.getElementById('notifyResId');
    const notifyType = document.getElementById('notifyType');
    const notifyValue = document.getElementById('notifyValue');
    const sendNotifyBtn = document.getElementById('sendNotifyBtn');

    // Notifications Log Table
    const notificationsTableBody = document.getElementById('notificationsTableBody');

    // Console
    const logConsole = document.getElementById('logConsole');
    const atInput = document.getElementById('atInput');
    const sendAtBtn = document.getElementById('sendAtBtn');
    const clearLogBtn = document.getElementById('clearLogBtn');

    // --- WebSocket Connection ---
    function initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            appendLog('[SYSTEM] WebSocket connected to LwM2M Studio server.', 'info');
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWebSocketMessage(msg);
            } catch (err) {
                console.error('Error parsing WebSocket message:', err);
            }
        };

        ws.onclose = () => {
            appendLog('[SYSTEM] WebSocket connection closed. Retrying in 3 seconds...', 'error');
            setTimeout(initWebSocket, 3000);
        };
    }

    function handleWebSocketMessage(msg) {
        if (msg.type === 'state') {
            updateStateUI(msg.data);
        } else if (msg.type === 'log') {
            const data = msg.data;
            const text = typeof data === 'string' ? data : (data.line || JSON.stringify(data));
            const level = typeof data === 'object' && data.level ? data.level.toLowerCase() : 'info';
            appendLog(text, level);
        } else if (msg.type === 'object_added') {
            loadObjects();
        } else if (msg.type === 'notification') {
            addNotificationRow(msg.data);
        }
    }

    // --- UI Update Helpers ---
    function updateStateUI(state) {
        if (!state) return;
        
        isConnected = state.is_connected;
        const isDemo = state.is_demo;

        if (isConnected) {
            connectionStatus.className = 'status-badge ' + (isDemo ? 'demo' : 'connected');
            statusText.textContent = isDemo ? 'Demo (Simulated)' : `Connected (${state.port})`;
            connectBtn.innerHTML = '<i class="fa-solid fa-unlink"></i> Disconnect';
            connectBtn.className = 'btn btn-secondary';
        } else {
            connectionStatus.className = 'status-badge disconnected';
            statusText.textContent = 'Disconnected';
            connectBtn.innerHTML = '<i class="fa-solid fa-link"></i> Connect';
            connectBtn.className = 'btn btn-primary';
        }

        if (state.dtls_config) {
            dtlsStatusBadge.textContent = 'Configured';
            dtlsStatusBadge.className = 'badge badge-good';
            activeEpVal.textContent = state.dtls_config.endpoint_name || 'N/A';
            activeServerVal.textContent = `${state.dtls_config.server_url}:${state.dtls_config.port || 5684}`;
        } else {
            dtlsStatusBadge.textContent = 'Not Configured';
            dtlsStatusBadge.className = 'badge badge-warning';
        }

        if (state.is_registered) {
            regStatusVal.textContent = 'Registered (Active)';
            regStatusVal.className = 'info-val text-success';
        } else {
            regStatusVal.textContent = 'Unregistered';
            regStatusVal.className = 'info-val';
        }
    }

    function appendLog(text, level = 'info') {
        const line = document.createElement('div');
        let cssClass = 'log-info';

        if (level === 'tx' || text.startsWith('>>') || text.startsWith('AT>')) {
            cssClass = 'log-tx';
        } else if (level === 'rx' || text.startsWith('<<') || text.includes('OK') || text.includes('SEND OK')) {
            cssClass = 'log-rx';
        } else if (level === 'error' || text.includes('ERROR') || text.includes('FAIL')) {
            cssClass = 'log-error';
        } else if (level === 'debug') {
            cssClass = 'log-debug';
        }

        line.className = `log-line ${cssClass}`;
        line.textContent = text;
        logConsole.appendChild(line);

        // Limit lines
        while (logConsole.childNodes.length > 500) {
            logConsole.removeChild(logConsole.firstChild);
        }

        logConsole.scrollTop = logConsole.scrollHeight;
    }

    // --- API Interactions ---
    async function loadPorts() {
        try {
            const res = await fetch('/api/ports');
            const data = await res.json();
            portSelect.innerHTML = '';

            if (data.ports && data.ports.length > 0) {
                data.ports.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.textContent = p;
                    if (p === 'COM3') opt.selected = true;
                    portSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = 'COM3';
                opt.textContent = 'COM3 (Default)';
                portSelect.appendChild(opt);
            }
        } catch (err) {
            console.error('Error fetching serial ports:', err);
        }
    }

    async function toggleConnect() {
        if (isConnected) {
            try {
                const res = await fetch('/api/disconnect', { method: 'POST' });
                const data = await res.json();
                updateStateUI(data.state);
                appendLog('[SYSTEM] Disconnected from serial port.', 'info');
            } catch (err) {
                appendLog(`[ERROR] Disconnect failed: ${err}`, 'error');
            }
        } else {
            const port = portSelect.value || 'COM3';
            const baud = parseInt(baudSelect.value) || 115200;
            try {
                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ port: port, baudrate: baud })
                });
                const data = await res.json();
                if (res.ok) {
                    updateStateUI(data.state);
                    appendLog(`[SYSTEM] Connected to ${port} @ ${baud} baud.`, 'rx');
                } else {
                    appendLog(`[ERROR] Connection failed: ${data.detail}`, 'error');
                }
            } catch (err) {
                appendLog(`[ERROR] Connect error: ${err}`, 'error');
            }
        }
    }

    async function saveDtlsConfig() {
        const payload = {
            server_url: dtlsServerInput.value.trim(),
            port: parseInt(dtlsPortInput.value) || 5684,
            endpoint_name: endpointInput.value.trim(),
            psk_identity: pskIdInput.value.trim(),
            psk_key: pskKeyInput.value.trim()
        };

        try {
            const res = await fetch('/api/dtls/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                appendLog(`[DTLS] Config saved successfully! Mode: PSK, Endpoint: ${payload.endpoint_name}`, 'rx');
                updateStateUI(data.state);
            } else {
                appendLog(`[ERROR] DTLS Config failed: ${data.detail}`, 'error');
            }
        } catch (err) {
            appendLog(`[ERROR] ${err}`, 'error');
        }
    }

    async function registerLwM2M() {
        try {
            appendLog('[LWM2M] Initiating AT+QLWM2M="register"...', 'tx');
            const res = await fetch('/api/dtls/register', { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                appendLog(`[LWM2M] Registration response:\n${data.response}`, 'rx');
                updateStateUI(data.state);
            } else {
                appendLog(`[ERROR] Registration failed: ${data.detail}`, 'error');
            }
        } catch (err) {
            appendLog(`[ERROR] ${err}`, 'error');
        }
    }

    async function loadObjects() {
        try {
            const res = await fetch('/api/objects');
            const data = await res.json();
            registeredObjects = data.objects || [];
            renderObjectsTree(registeredObjects);
        } catch (err) {
            console.error('Error fetching objects:', err);
        }
    }

    function renderObjectsTree(objects) {
        objectCountBadge.textContent = `${objects.length} Objects`;
        objectsTree.innerHTML = '';

        if (!objects || objects.length === 0) {
            objectsTree.innerHTML = '<div class="empty-state">No objects imported yet.</div>';
            return;
        }

        objects.forEach(obj => {
            const card = document.createElement('div');
            card.className = 'object-card-item';

            const header = document.createElement('div');
            header.className = 'object-header';
            header.innerHTML = `
                <div class="object-title-text">
                    <i class="fa-solid fa-cube"></i>
                    <span>Object ${obj.object_id}: ${obj.name}</span>
                </div>
                <span class="badge badge-primary">${obj.resources ? obj.resources.length : 0} Res</span>
            `;

            const resList = document.createElement('div');
            resList.className = 'resource-list';

            if (obj.resources && obj.resources.length > 0) {
                obj.resources.forEach(res => {
                    const item = document.createElement('div');
                    item.className = 'resource-item';
                    item.innerHTML = `
                        <div>
                            <span class="resource-tag">/${obj.object_id}/0/${res.id}</span>
                            <span class="resource-desc">${res.name}</span>
                        </div>
                        <span class="badge badge-secondary">${res.type}</span>
                    `;
                    item.addEventListener('click', () => {
                        selectResourceForNotify(obj.object_id, res.id, res.name, res.type);
                    });
                    resList.appendChild(item);
                });
            } else {
                resList.innerHTML = '<div class="empty-state">No resources defined</div>';
            }

            header.addEventListener('click', () => {
                resList.style.display = resList.style.display === 'none' ? 'flex' : 'none';
            });

            card.appendChild(header);
            card.appendChild(resList);
            objectsTree.appendChild(card);
        });
    }

    function selectResourceForNotify(objId, resId, resName, resType) {
        notifyObjId.value = objId;
        notifyResId.value = resId;
        selectedObjectBadge.textContent = `/${objId}/0/${resId} (${resName})`;

        // Map type
        const typeLower = (resType || '').toLowerCase();
        if (typeLower.includes('float') || typeLower.includes('double')) {
            notifyType.value = 'float';
        } else if (typeLower.includes('int')) {
            notifyType.value = 'integer';
        } else if (typeLower.includes('bool')) {
            notifyType.value = 'boolean';
        } else if (typeLower.includes('opaque')) {
            notifyType.value = 'opaque';
        } else {
            notifyType.value = 'string';
        }
    }

    async function sendNotification() {
        const payload = {
            object_id: parseInt(notifyObjId.value) || 3303,
            instance_id: parseInt(notifyInstId.value) || 0,
            resource_id: parseInt(notifyResId.value) || 5700,
            val_type: notifyType.value,
            value: notifyValue.value.trim()
        };

        try {
            appendLog(`[DTLS TELEMETRY] Transmitting AT+QLWM2M="notify",1,1,${payload.object_id},${payload.instance_id},${payload.resource_id}...`, 'tx');
            const res = await fetch('/api/notify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                appendLog(`[DTLS TELEMETRY] Response: ${data.response}`, 'rx');
                loadNotifications();
            } else {
                appendLog(`[ERROR] Notification failed: ${data.detail}`, 'error');
            }
        } catch (err) {
            appendLog(`[ERROR] ${err}`, 'error');
        }
    }

    async function loadNotifications() {
        try {
            const res = await fetch('/api/notifications');
            const data = await res.json();
            renderNotificationsTable(data.notifications || []);
        } catch (err) {
            console.error('Error fetching notifications:', err);
        }
    }

    function renderNotificationsTable(list) {
        notificationsTableBody.innerHTML = '';
        if (!list || list.length === 0) {
            notificationsTableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No LwM2M notifications transmitted yet</td></tr>';
            return;
        }

        list.forEach(item => {
            const tr = document.createElement('tr');
            const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'Just now';
            tr.innerHTML = `
                <td>${timeStr}</td>
                <td class="font-mono highlight">/${item.object_id}/${item.instance_id}/${item.resource_id}</td>
                <td><span class="badge badge-secondary">${item.val_type}</span></td>
                <td class="font-mono">${item.value}</td>
                <td><span class="badge badge-good"><i class="fa-solid fa-shield-check"></i> Encrypted (DTLS)</span></td>
            `;
            notificationsTableBody.appendChild(tr);
        });
    }

    // --- XML Import Handling ---
    async function uploadXmlFile(file) {
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);

        try {
            appendLog(`[XML] Uploading custom OMA XML file: ${file.name}...`, 'tx');
            const res = await fetch('/api/objects/upload_xml', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                appendLog(`[XML] Successfully imported Object ${data.object.object_id}: ${data.object.name}`, 'rx');
                loadObjects();
            } else {
                appendLog(`[ERROR] XML Upload failed: ${data.detail}`, 'error');
            }
        } catch (err) {
            appendLog(`[ERROR] XML upload error: ${err}`, 'error');
        }
    }

    async function importXmlPaste() {
        const content = xmlPasteArea.value.trim();
        if (!content) {
            alert('Please paste XML schema content first.');
            return;
        }

        try {
            appendLog('[XML] Parsing pasted XML schema...', 'tx');
            const res = await fetch('/api/objects/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ xml_content: content })
            });
            const data = await res.json();
            if (res.ok) {
                appendLog(`[XML] Parsed and saved Object ${data.object.object_id}: ${data.object.name}`, 'rx');
                xmlPasteArea.value = '';
                loadObjects();
            } else {
                appendLog(`[ERROR] XML Parse failed: ${data.detail}`, 'error');
            }
        } catch (err) {
            appendLog(`[ERROR] XML parse error: ${err}`, 'error');
        }
    }

    // Drag & Drop
    if (uploadDropzone) {
        ['dragenter', 'dragover'].forEach(evt => {
            uploadDropzone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadDropzone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            uploadDropzone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                uploadDropzone.classList.remove('dragover');
            });
        });

        uploadDropzone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                uploadXmlFile(files[0]);
            }
        });
    }

    if (xmlFileInput) {
        xmlFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                uploadXmlFile(e.target.files[0]);
            }
        });
    }

    // --- AT Commands ---
    async function sendATCommand(cmd) {
        if (!cmd) return;
        appendLog(`>> ${cmd}`, 'tx');
        try {
            const res = await fetch('/api/send_at', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd })
            });
            const data = await res.json();
            if (res.ok) {
                appendLog(`<< ${data.response}`, 'rx');
            } else {
                appendLog(`[ERROR] AT Command failed: ${data.detail}`, 'error');
            }
        } catch (err) {
            appendLog(`[ERROR] ${err}`, 'error');
        }
    }

    async function exitServer() {
        if (confirm('Are you sure you want to stop the LwM2M Studio server?')) {
            try {
                await fetch('/api/shutdown', { method: 'POST' });
                appendLog('[SYSTEM] Server stopping... You can close this window.', 'warning');
            } catch (err) {
                appendLog('[SYSTEM] Server stopped.', 'warning');
            }
        }
    }

    // Event Listeners
    refreshPortsBtn.addEventListener('click', loadPorts);
    connectBtn.addEventListener('click', toggleConnect);
    saveDtlsBtn.addEventListener('click', saveDtlsConfig);
    registerBtn.addEventListener('click', registerLwM2M);
    importPasteBtn.addEventListener('click', importXmlPaste);
    sendNotifyBtn.addEventListener('click', sendNotification);
    exitBtn.addEventListener('click', exitServer);

    sendAtBtn.addEventListener('click', () => {
        const cmd = atInput.value.trim();
        if (cmd) {
            sendATCommand(cmd);
            atInput.value = '';
        }
    });

    atInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const cmd = atInput.value.trim();
            if (cmd) {
                sendATCommand(cmd);
                atInput.value = '';
            }
        }
    });

    clearLogBtn.addEventListener('click', () => {
        logConsole.innerHTML = '';
        appendLog('[SYSTEM] Log console cleared.', 'info');
    });

    document.querySelectorAll('.cmd-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const cmd = btn.getAttribute('data-cmd');
            if (cmd) sendATCommand(cmd);
        });
    });

    // --- Initialization ---
    initWebSocket();
    loadPorts();
    loadObjects();
    loadNotifications();
});
