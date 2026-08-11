from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from PIL import Image
from zxingcpp import read_barcode
from datetime import datetime
import io

app = FastAPI()

scanned_codes = {"regular": [], "a6": []}
scan_history = []

# --- Загальні HTML стилі та компоненти ---
COMMON_HTML_COMPONENTS = """
    <style>
        #toast { visibility: hidden; min-width: 250px; background-color: #333; color: #fff; text-align: center; border-radius: 8px; padding: 16px; position: fixed; z-index: 999; left: 50%; bottom: 30px; transform: translateX(-50%); font-size: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }
        #toast.show { visibility: visible; animation: fadein 0.5s, fadeout 0.5s 1.5s; }
        @keyframes fadein { from {bottom: 0; opacity: 0;} to {bottom: 30px; opacity: 1;} }
        @keyframes fadeout { from {bottom: 30px; opacity: 1;} to {bottom: 0; opacity: 0;} }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 1000; justify-content: center; align-items: center; }
        .modal { background: var(--card-bg); padding: 25px; border-radius: 12px; width: 280px; text-align: center; box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .modal input { width: 90%; padding: 12px; margin: 15px 0; border: 2px solid #ccc; border-radius: 6px; font-size: 18px; text-align: center; box-sizing: border-box; }
        .modal button { width: 100%; padding: 12px; border: none; border-radius: 6px; background: #0066cc; color: white; font-weight: bold; cursor: pointer; font-size: 16px; }
    </style>
    
    <div id="toast"></div>
    <div id="pinModal" class="modal-overlay">
        <div class="modal">
            <h3>Введіть PIN-код</h3>
            <input type="password" id="pinInput" maxlength="4" inputmode="numeric" pattern="\\d*">
            <button onclick="confirmPin()">Підтвердити</button>
        </div>
    </div>

    <script>
        function showToast(message) {
            const t = document.getElementById('toast');
            t.innerText = message;
            t.className = 'show';
            setTimeout(() => { t.className = t.className.replace('show', ''); }, 2000);
        }

        let pinCallback = null;
        function askPin(callback) {
            document.getElementById('pinModal').style.display = 'flex';
            document.getElementById('pinInput').focus();
            pinCallback = callback;
        }

        function confirmPin() {
            const val = document.getElementById('pinInput').value;
            document.getElementById('pinInput').value = '';
            document.getElementById('pinModal').style.display = 'none';
            if (pinCallback) pinCallback(val);
        }
    </script>
"""

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile = any(m in user_agent for m in ["iphone", "android", "mobile"])

    if is_mobile:
        return f"""
        <!DOCTYPE html>
        <html lang="uk"><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Сканер</title>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <style>
            body {{ font-family: sans-serif; padding: 10px; background: #f4f6f8; }}
            .card {{ background: #fff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            #reader {{ width: 100%; min-height: 250px; background: #000; }}
            .btn-torch {{ width: 100%; background: #f0ad4e; color: white; padding: 12px; border: none; border-radius: 6px; margin-top: 10px; display: none; }}
        </style></head>
        <body>
            <div class="card">
                <h2>Сканування</h2>
                <input type="checkbox" id="isA6"> Цінник А6
                <div id="reader"></div>
                <button id="torchBtn" class="btn-torch" onclick="toggleTorch()">🔦 Ліхтарик</button>
                <p>Останній: <b id="lastCode">—</b></p>
            </div>
            {COMMON_HTML_COMPONENTS}
            <script>
                let html5QrCode = new Html5Qrcode("reader");
                let torchOn = false;
                html5QrCode.start({{ facingMode: "environment" }}, {{ fps: 10, qrbox: 200 }}, (text) => {{
                    document.getElementById('lastCode').innerText = text;
                    fetch('/api-scan-text', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{code: text, is_a6: document.getElementById('isA6').checked}}) }})
                    .then(() => showToast("Додано!"));
                }}).then(() => document.getElementById('torchBtn').style.display = 'block');
                
                async function toggleTorch() {{
                    torchOn = !torchOn;
                    await html5QrCode.applyVideoConstraints({{ advanced: [{{ torch: torchOn }}] }});
                }}
            </script>
        </body></html>"""
    else:
        # Для desktop версії додайте COMMON_HTML_COMPONENTS у відповідне місце в HTML
        return "Desktop interface (оновіть відповідний блок HTML у вашому коді аналогічно мобільному)."

# --- API ендпоінти ---
@app.post("/clear/{list_type}/{pin}")
async def clear_list(list_type: str, pin: str):
    if pin != "5141": return {"success": False}
    if list_type in scanned_codes: scanned_codes[list_type] = []
    return {"success": True}

@app.post("/api-scan-text")
async def scan_text(data: dict):
    # Логіка обробки коду...
    return {"success": True}
