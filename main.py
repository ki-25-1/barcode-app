from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from PIL import Image
from zxingcpp import read_barcode
import io

app = FastAPI()

# База даних у пам'яті для зберігання списків штрихкодів
scanned_codes = {
    "regular": [],
    "a6": []
}

@app.post("/clear/{list_type}/{pin}")
async def clear_list(list_type: str, pin: str):
    if pin != "5141":
        return {"success": False, "error": "Невірний пін-код"}
    
    if list_type in scanned_codes:
        scanned_codes[list_type] = []
    return {"success": True}

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile = any(m in user_agent for m in ["iphone", "android", "blackberry", "ipod", "opera mini", "iemobile", "mobile"])

    # HTML для мобільних телефонів (з виправленим відображенням камери)
    mobile_html = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Живий сканер цінників</title>
        <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
        <style>
            body { font-family: sans-serif; padding: 10px; background: #f4f6f8; max-width: 600px; margin: 0 auto; }
            .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 15px; }
            .checkbox-label { font-size: 18px; display: flex; align-items: center; gap: 12px; cursor: pointer; margin-bottom: 12px; font-weight: bold; }
            .checkbox-label input { width: 24px; height: 24px; }
            h2 { margin-top: 0; color: #333; font-size: 20px; text-align: center; }
            #reader { width: 100%; min-height: 300px; border-radius: 8px; overflow: hidden; background: #000; }
            #status { margin-top: 15px; font-weight: bold; font-size: 18px; text-align: center; min-height: 30px; }
            /* Ховаємо зайві елементи бібліотеки для зручності */
            #reader__dashboard_section_csr button { padding: 10px 15px; background: #0066cc; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Сканування цінника</h2>
            <label class="checkbox-label">
                <input type="checkbox" id="isA6"> 
                <span>Цінник А6</span>
            </label>
            <div id="reader"></div>
            <div id="status">Запуск камери...</div>
        </div>

        <script>
            function playSound(isSuccess) {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    
                    if (isSuccess) {
                        osc.frequency.setValueAtTime(600, ctx.currentTime);
                        osc.frequency.exponentialRampToValueAtTime(900, ctx.currentTime + 0.15);
                    } else {
                        osc.frequency.setValueAtTime(300, ctx.currentTime);
                        osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.2);
                    }
                    
                    osc.start();
                    osc.stop(ctx.currentTime + 0.2);
                } catch(e) {}
            }

            let isScanningLocked = false;

            async function onScanSuccess(decodedText, decodedResult) {
                if (isScanningLocked) return;
                isScanningLocked = true;

                const status = document.getElementById('status');
                const isA6 = document.getElementById('isA6').checked;
                
                status.style.color = "#0066cc";
                status.innerText = "Зчитано: " + decodedText;

                try {
                    const response = await fetch('/api-scan-text', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code: decodedText, is_a6: isA6 })
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        playSound(true);
                        status.style.color = "green";
                        status.innerText = result.message || ("Успішно додано: " + decodedText);
                        document.getElementById('isA6').checked = false; 
                    } else {
                        playSound(false);
                        status.style.color = "red";
                        status.innerText = "Помилка: " + result.error;
                    }
                } catch (err) {
                    playSound(false);
                    status.style.color = "red";
                    status.innerText = "Помилка з'єднання.";
                }

                setTimeout(() => {
                    isScanningLocked = false;
                    status.innerText = "Наведіть камеру на наступний штрихкод...";
                }, 1500);
            }

            // Запускаємо сканер після завантаження сторінки
            window.addEventListener('load', function () {
                const html5QrCode = new Html5Qrcode("reader");
                html5QrCode.start(
                    { facingMode: "environment" }, 
                    {
                        fps: 15,
                        qrbox: { width: 280, height: 160 }
                    },
                    onScanSuccess
                ).then(() => {
                    document.getElementById('status').innerText = "Наведіть камеру на штрихкод...";
                }).catch(err => {
                    document.getElementById('status').style.color = "red";
                    document.getElementById('status').innerText = "Немає доступу до камери. Дозвольте доступ у браузері.";
                });
            });
        </script>
    </body>
    </html>
    """

    # HTML для комп'ютерів
    desktop_html = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Панель керування штрихкодами</title>
        <style>
            body { font-family: sans-serif; padding: 20px; background: #f4f6f8; max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .flex-grid { display: flex; gap: 20px; flex-wrap: wrap; }
            .col { flex: 1; min-width: 350px; }
            .item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; font-size: 18px; }
            button { cursor: pointer; padding: 10px 16px; border-radius: 6px; border: none; background: #0066cc; color: white; font-weight: bold; font-size: 16px; }
            .btn-clear { background: #ff4d4d; margin-bottom: 10px; width: 100%; }
            .btn-download { background: #17a2b8; margin-bottom: 10px; width: 100%; }
            .btn-copy { background: #28a745; padding: 6px 12px; font-size: 14px; }
            code { background: #eef2f5; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Панель керування списком штрихкодів</h1>

        <div class="flex-grid">
            <div class="col card">
                <h3>Звичайні цінники (Кількість: <span id="regCount">0</span>)</h3>
                <button class="btn-download" onclick="downloadTxt('regular')">Скачати список (TXT)</button>
                <button class="btn-clear" onclick="clearList('regular')">Очистити звичайний список</button>
                <div id="regularList"></div>
            </div>
            
            <div class="col card">
                <h3>Цінники А6 (Кількість: <span id="a6Count">0</span>)</h3>
                <button class="btn-download" onclick="downloadTxt('a6')">Скачати список (TXT)</button>
                <button class="btn-clear" onclick="clearList('a6')">Очистити список А6</button>
                <div id="a6List"></div>
            </div>
        </div>

        <script>
            let cachedData = { regular: [], a6: [] };

            async function loadCodes() {
                try {
                    const res = await fetch('/codes');
                    const data = await res.json();
                    cachedData = data;
                    
                    const render = (list, elementId, countId) => {
                        document.getElementById(countId).innerText = list.length;
                        const container = document.getElementById(elementId);
                        if (list.length === 0) {
                            container.innerHTML = '<p style="color: #888; text-align: center;">Список порожній</p>';
                            return;
                        }
                        container.innerHTML = list.map(c => `
                            <div class="item">
                                <code>${c}</code>
                                <button class="btn-copy" onclick="copyToClipboard('${c}')">Копіювати</button>
                            </div>
                        `).join('');
                    };
                    
                    render(data.regular, 'regularList', 'regCount');
                    render(data.a6, 'a6List', 'a6Count');
                } catch (err) {
                    console.error("Помилка завантаження списків", err);
                }
            }

            function copyToClipboard(text) {
                navigator.clipboard.writeText(text);
                alert("Скопійовано в буфер: " + text);
            }

            function downloadTxt(type) {
                const list = cachedData[type];
                if (!list || list.length === 0) {
                    alert("Список порожній!");
                    return;
                }
                const blob = new Blob([list.join('\\n')], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `barcodes_${type}.txt`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }

            async function clearList(type) {
                const enteredPin = prompt("Введіть PIN-код для очищення списку:");
                if (!enteredPin) return;

                const response = await fetch(`/clear/${type}/${enteredPin}`, { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    loadCodes();
                    alert("Список успішно очищено!");
                } else {
                    alert("Невірний PIN-код! Очищення скасовано.");
                }
            }

            setInterval(loadCodes, 2000);
            loadCodes();
        </script>
    </body>
    </html>
    """

    return mobile_html if is_mobile else desktop_html

@app.post("/api-scan-text")
async def scan_text(data: dict):
    try:
        barcode_data = data.get("code")
        is_a6 = data.get("is_a6", False)
        
        if not barcode_data:
            return {"success": False, "error": "Пустий код"}
            
        target_list = scanned_codes["a6"] if is_a6 else scanned_codes["regular"]
        
        if barcode_data in target_list:
            target_list.remove(barcode_data)
            target_list.insert(0, barcode_data)
            return {"success": True, "code": barcode_data, "message": f"Вже у списку! Піднято вгору: {barcode_data}"}
        
        target_list.insert(0, barcode_data)
        return {"success": True, "code": barcode_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/scan")
async def scan_barcode(file: UploadFile = File(...), is_a6: bool = Form(False)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        result = read_barcode(image)
        if not result:
            return {"success": False, "error": "Штрихкод на фото не знайдено."}
        barcode_data = result.text
        target_list = scanned_codes["a6"] if is_a6 else scanned_codes["regular"]
        if barcode_data in target_list:
            target_list.remove(barcode_data)
        target_list.insert(0, barcode_data)
        return {"success": True, "code": barcode_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/codes")
async def get_codes():
    return scanned_codes
