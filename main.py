from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from PIL import Image
from zxingcpp import read_barcode
from datetime import datetime
import io

app = FastAPI()

scanned_codes = {
    "regular": [],
    "a6": []
}

scan_history = []

@app.post("/clear/{list_type}/{pin}")
async def clear_list(list_type: str, pin: str):
    if pin != "5141":
        return {"success": False, "error": "Невірний пін-код"}
    if list_type in scanned_codes:
        scanned_codes[list_type] = []
    return {"success": True}

@app.post("/clear-history/{pin}")
async def clear_history(pin: str):
    if pin != "5141":
        return {"success": False, "error": "Невірний пін-код"}
    global scan_history
    scan_history = []
    return {"success": True}

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile = any(m in user_agent for m in ["iphone", "android", "blackberry", "ipod", "opera mini", "iemobile", "mobile"])

    # Mobile version (залишаємо без змін)
    mobile_html = """
    <!DOCTYPE html>
    <html lang="uk">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Сканер</title>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <style>body{font-family:sans-serif;padding:10px;background:#f4f6f8;}</style></head>
    <body><div class="card"><h2>Сканування цінника</h2><div id="reader"></div></div></body>
    </html>
    """

    # Desktop version
    desktop_html = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <title>Панель керування</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            :root { --bg-color: #f4f6f8; --card-bg: #ffffff; --text-color: #333; }
            body { font-family: sans-serif; padding: 20px; background: var(--bg-color); color: var(--text-color); }
            .card { background: var(--card-bg); padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .item { display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee; }
            .highlight { background-color: #d4edda !important; }
            .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 10000; justify-content: center; align-items: center; }
            .modal { background: white; padding: 25px; border-radius: 12px; width: 300px; text-align: center; }
            .pin-input { width: 80%; padding: 10px; margin: 15px 0; border: 1px solid #ccc; border-radius: 6px; }
            button { cursor: pointer; padding: 10px 16px; border-radius: 6px; border: none; background: #0066cc; color: white; font-weight: bold; }
        </style>
    </head>
    <body>
        <div id="toast" style="visibility:hidden; position:fixed; bottom:30px; left:50%; transform:translateX(-50%); background:#333; color:#fff; padding:15px; border-radius:8px;"></div>
        
        <div id="pinModal" class="modal-overlay">
            <div class="modal">
                <h3>Введіть PIN-код</h3>
                <input type="password" id="pinInputCode" class="pin-input" autofocus>
                <div>
                    <button onclick="document.getElementById('pinModal').style.display='none'">Скасувати</button>
                    <button onclick="submitPinModal()">Підтвердити</button>
                </div>
            </div>
        </div>

        <div class="flex-grid">
            <div class="col card">
                <h3>Звичайні: <span id="regCount">0</span></h3>
                <button class="btn-clear" onclick="requestPin('regular')">Очистити</button>
                <div id="regularList"></div>
            </div>
            <div class="col card">
                <h3>А6: <span id="a6Count">0</span></h3>
                <button class="btn-clear" onclick="requestPin('a6')">Очистити</button>
                <div id="a6List"></div>
            </div>
        </div>

        <script>
            let lastCopied = null;
            let currentPinAction = null;

            function showToast(msg) {
                const toast = document.getElementById('toast');
                toast.innerText = msg;
                toast.style.visibility = 'visible';
                setTimeout(() => toast.style.visibility = 'hidden', 2000);
            }

            function requestPin(type) {
                currentPinAction = type;
                document.getElementById('pinModal').style.display = 'flex';
                document.getElementById('pinInputCode').value = '';
            }

            async function submitPinModal() {
                const pin = document.getElementById('pinInputCode').value;
                document.getElementById('pinModal').style.display = 'none';
                const res = await fetch(`/clear/${currentPinAction}/${pin}`, { method: 'POST' });
                if ((await res.json()).success) {
                    showToast("Очищено!");
                    loadData();
                } else {
                    showToast("Помилка PIN!");
                }
            }

            function copyToClipboard(text, btn) {
                navigator.clipboard.writeText(text);
                lastCopied = text;
                showToast("Скопійовано: " + text);
                loadData();
            }

            async function loadData() {
                const res = await fetch('/all-data');
                const data = await res.json();
                
                const render = (list, id, countId) => {
                    document.getElementById(countId).innerText = list.length;
                    document.getElementById(id).innerHTML = list.map(c => `
                        <div class="item ${lastCopied === c ? 'highlight' : ''}">
                            <code>${c}</code>
                            <button onclick="copyToClipboard('${c}', this)">Копіювати</button>
                        </div>
                    `).join('');
                };
                render(data.regular, 'regularList', 'regCount');
                render(data.a6, 'a6List', 'a6Count');
            }

            setInterval(loadData, 2000);
            loadData();
        </script>
    </body>
    </html>
    """
    return mobile_html if is_mobile else desktop_html

@app.post("/api-scan-text")
async def scan_text(data: dict):
    code = data.get("code")
    is_a6 = data.get("is_a6", False)
    target = scanned_codes["a6" if is_a6 else "regular"]
    if code in target: target.remove(code)
    target.insert(0, code)
    return {"success": True}

@app.get("/all-data")
async def get_all_data():
    return {"regular": scanned_codes["regular"], "a6": scanned_codes["a6"], "history": scan_history}
