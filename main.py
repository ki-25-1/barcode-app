from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from PIL import Image
from zxingcpp import read_barcode
from datetime import datetime
import io

app = FastAPI()

scanned_codes = {"regular": [], "a6": []}
scan_history = []

# CSS та JS для красивих повідомлень
UI_INJECTS = """
    <style>
        #toast { visibility: hidden; min-width: 250px; background: #333; color: #fff; text-align: center; border-radius: 8px; padding: 16px; position: fixed; z-index: 9999; left: 50%; bottom: 30px; transform: translateX(-50%); font-size: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }
        #toast.show { visibility: visible; animation: fadein 0.5s, fadeout 0.5s 1.5s; }
        @keyframes fadein { from {bottom: 0; opacity: 0;} to {bottom: 30px; opacity: 1;} }
        @keyframes fadeout { from {bottom: 30px; opacity: 1;} to {bottom: 0; opacity: 0;} }
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 10000; justify-content: center; align-items: center; }
        .modal { background: var(--card-bg); padding: 25px; border-radius: 12px; width: 280px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .modal input { width: 90%; padding: 12px; margin: 15px 0; border: 2px solid #ccc; border-radius: 6px; font-size: 18px; text-align: center; box-sizing: border-box; }
        .modal button { width: 100%; padding: 12px; border: none; border-radius: 6px; background: #0066cc; color: white; font-weight: bold; cursor: pointer; }
        .highlight { background-color: #d4edda !important; transition: background-color 0.5s; }
    </style>
    <div id="toast"></div>
    <div id="pinModal" class="modal-overlay">
        <div class="modal">
            <h3>Введіть PIN-код</h3>
            <input type="password" id="pinInput" maxlength="4" inputmode="numeric">
            <button onclick="confirmPin()">Підтвердити</button>
        </div>
    </div>
    <script>
        function showToast(msg) { const t = document.getElementById('toast'); t.innerText = msg; t.className = 'show'; setTimeout(() => { t.className = ''; }, 2000); }
        let pinCb = null;
        function askPin(cb) { pinCb = cb; document.getElementById('pinModal').style.display = 'flex'; document.getElementById('pinInput').focus(); }
        function confirmPin() { const val = document.getElementById('pinInput').value; document.getElementById('pinInput').value = ''; document.getElementById('pinModal').style.display = 'none'; if(pinCb) pinCb(val); }
        function copyToClipboard(text, btn) { navigator.clipboard.writeText(text); showToast("Скопійовано!"); const row = btn.closest('.item') || btn.closest('.history-item'); row.classList.add('highlight'); setTimeout(() => row.classList.remove('highlight'), 1000); }
    </script>
"""

@app.post("/clear/{list_type}/{pin}")
async def clear_list(list_type: str, pin: str):
    if pin != "5141": return {"success": False, "error": "Невірний пін-код"}
    if list_type in scanned_codes: scanned_codes[list_type] = []
    return {"success": True}

@app.post("/clear-history/{pin}")
async def clear_history(pin: str):
    if pin != "5141": return {"success": False, "error": "Невірний пін-код"}
    global scan_history
    scan_history = []
    return {"success": True}

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile = any(m in user_agent for m in ["iphone", "android", "mobile"])

    if is_mobile:
        return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://unpkg.com/html5-qrcode"></script>{UI_INJECTS}</head>
        <body data-theme="light"><div class="card"><h2>Сканер</h2><input type="checkbox" id="isA6"> Цінник А6<div id="reader"></div><button id="torchBtn" class="btn-torch" onclick="toggleTorch()">🔦 Ліхтарик</button><div id="status">Запуск...</div></div>
        <script>
            let html5QrCode = new Html5Qrcode("reader"); let torchOn = false;
            html5QrCode.start({{ facingMode: "environment" }}, {{ fps: 15, qrbox: 200 }}, async (text) => {{
                const res = await fetch('/api-scan-text', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{code: text, is_a6: document.getElementById('isA6').checked}}) }});
                showToast("Додано!");
            }}).then(() => document.getElementById('torchBtn').style.display = 'block');
            async function toggleTorch() {{ torchOn = !torchOn; await html5QrCode.applyVideoConstraints({{ advanced: [{{ torch: torchOn }}] }}); }}
        </script></body></html>"""
    
    return f"""<!DOCTYPE html><html><head>{UI_INJECTS}</head><body>
        <h1>Панель керування</h1>
        <div id="regularList"></div>
        <script>
            async function clearList(type) {{ askPin(async (pin) => {{ const res = await fetch(`/clear/${{type}}/${{pin}}`, {{ method: 'POST' }}); if ((await res.json()).success) {{ showToast("Очищено"); loadData(); }} else showToast("Невірний PIN"); }}); }}
            // ... (остальна логіка desktop)
        </script></body></html>"""

@app.post("/api-scan-text")
async def scan_text(data: dict):
    # Логіка обробки...
    return {"success": True}

# ... (інші ваші ендпоінти залишаються без змін)
