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
            #reader { width: 100%; min-height: 280px; border-radius: 8px; overflow: hidden; background: #000; }
            
            .last-code-box { background: #eef2f5; padding: 12px; border-radius: 6px; margin-top: 15px; text-align: center; border: 2px dashed #0066cc; }
            .last-code-title { font-size: 14px; color: #666; margin-bottom: 4px; }
            .last-code-value { font-size: 22px; font-weight: bold; color: #0066cc; word-break: break-all; }
            
            #status { margin-top: 10px; font-weight: bold; font-size: 16px; text-align: center; min-height: 25px; }
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
            
            <div class="last-code-box">
                <div class="last-code-title">Останній відсканований код:</div>
                <div id="lastCodeValue" class="last-code-value">—</div>
            </div>
            
            <div id="status">Запуск камери...</div>
        </div>

        <script>
            function speakText(text) {
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance(text);
                    utterance.lang = 'uk-UA';
                    utterance.rate = 1.1;
                    window.speechSynthesis.speak(utterance);
                }
            }

            // Професійний звук та вібрація (як у ТЗД)
            function playTsdSound(isSuccess) {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    
                    if (isSuccess) {
                        // Успіх: Короткий високий «Біп» + коротка вібрація
                        osc.type = 'sine';
                        osc.frequency.setValueAtTime(2000, ctx.currentTime); 
                        gain.gain.setValueAtTime(0.15, ctx.currentTime);
                        
                        osc.start();
                        osc.stop(ctx.currentTime + 0.08);

                        if ("vibrate" in navigator) {
                            navigator.vibrate(50);
                        }
                    } else {
                        // Помилка/Дублікат: Басовий «бузмер» + подвійна вібрація
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(220, ctx.currentTime);
                        osc.frequency.setValueAtTime(150, ctx.currentTime + 0.1);
                        gain.gain.setValueAtTime(0.2, ctx.currentTime);
                        
                        osc.start();
                        osc.stop(ctx.currentTime + 0.25);

                        if ("vibrate" in navigator) {
                            navigator.vibrate([100, 50, 100]);
                        }
                    }
                } catch(e) {}
            }

            let isScanningLocked = false;

            async function onScanSuccess(decodedText, decodedResult) {
                if (isScanningLocked) return;
                isScanningLocked = true;

                const status = document.getElementById('status');
                const lastCodeEl = document.getElementById('lastCodeValue');
                const isA6 = document.getElementById('isA6').checked;
                
                status.style.color = "#0066cc";
                status.innerText = "Обробка...";

                try {
                    const response = await fetch('/api-scan-text', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code: decodedText, is_a6: isA6 })
                    });
                    const result = await response.json();
                    
                    lastCodeEl.innerText = decodedText;

                    if (result.success) {
                        if (result.is_duplicate) {
                            playTsdSound(false);
                            speakText("Помилка");
                            status.style.color = "#d9534f";
                            status.innerText = "УВАГА: Повторне сканування!";
                        } else {
                            playTsdSound(true);
                            speakText("Проскановано");
                            status.style.color = "green";
                            status.innerText = "Успішно додано!";
                            document.getElementById('isA6').checked = false; 
                        }
                    } else {
                        playTsdSound(false);
                        speakText("Помилка");
                        status.style.color = "red";
                        status.innerText = "Помилка: " + result.error;
                    }
                } catch (err) {
                    playTsdSound(false);
                    speakText("Помилка");
                    status.style.color = "red";
                    status.innerText = "Помилка з'єднання.";
                }

                setTimeout(() => {
                    isScanningLocked = false;
                }, 1800);
            }

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
                    document.getElementById('status').innerText = "Немає доступу до камери.";
                });
            });
        </script>
    </body>
    </html>
    """

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
            .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
            .tab-btn { padding: 12px 24px; font-size: 18px; font-weight: bold; cursor: pointer; background: #ddd; border: none; border-radius: 6px; }
            .tab-btn.active { background: #0066cc; color: white; }
            .tab-content { display: none; }
            .tab-content.active { display: block; }
            
            .flex-grid { display: flex; gap: 20px; flex-wrap: wrap; }
            .col { flex: 1; min-width: 350px; }
            .item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; font-size: 18px; }
            .history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; font-size: 16px; }
            button { cursor: pointer; padding: 10px 16px; border-radius: 6px; border: none; background: #0066cc; color: white; font-weight: bold; font-size: 16px; }
            .btn-clear { background: #ff4d4d; margin-bottom: 10px; width: 100%; }
            .btn-download { background: #17a2b8; margin-bottom: 10px; width: 100%; }
            .btn-copy { background: #28a745; padding: 6px 12px; font-size: 14px; }
            code { background: #eef2f5; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
            .badge-dup { background: #ffdddd; color: #d9534f; padding: 3px 8px; border-radius: 4px; font-size: 14px; font-weight: bold; }
            .badge-new { background: #d4edda; color: #28a745; padding: 3px 8px; border-radius: 4px; font-size: 14px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Панель керування штрихкодами</h1>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('lists', this)">Актуальні списки</button>
            <button class="tab-btn" onclick="switchTab('history', this)">Історія сканувань</button>
        </div>

        <div id="listsTab" class="tab-content active">
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
        </div>

        <div id="historyTab" class="tab-content">
            <div class="card">
                <h3>Повна хронологія сканувань</h3>
                <button class="btn-clear" style="max-width: 300px;" onclick="clearHistory()">Очистити історію</button>
                <div id="historyList" style="margin-top: 15px;"></div>
            </div>
        </div>

        <script>
            function switchTab(tabName, btn) {
                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                
                if (tabName === 'lists') {
                    document.getElementById('listsTab').classList.add('active');
                } else {
                    document.getElementById('historyTab').classList.add('active');
                }
                btn.classList.add('active');
            }

            let cachedData = { regular: [], a6: [], history: [] };

            async function loadData() {
                try {
                    const res = await fetch('/all-data');
                    const data = await res.json();
                    cachedData = data;
                    
                    const renderList = (list, elementId, countId) => {
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
                    
                    renderList(data.regular, 'regularList', 'regCount');
                    renderList(data.a6, 'a6List', 'a6Count');

                    const historyContainer = document.getElementById('historyList');
                    if (!data.history || data.history.length === 0) {
                        historyContainer.innerHTML = '<p style="color: #888; text-align: center;">Історія порожня</p>';
                    } else {
                        historyContainer.innerHTML = data.history.map(h => `
                            <div class="history-item">
                                <div>
                                    <span style="color: #666; font-weight: bold; margin-right: 10px;">[${h.time}]</span>
                                    <code>${h.code}</code>
                                    <span style="font-size: 13px; color: #555; margin-left: 10px;">(${h.type === 'a6' ? 'А6' : 'Звичайний'})</span>
                                </div>
                                <div>
                                    ${h.status === 'duplicate' ? '<span class="badge-dup">Повтор</span>' : '<span class="badge-new">Новий</span>'}
                                </div>
                            </div>
                        `).join('');
                    }
                } catch (err) {
                    console.error("Помилка завантаження даних", err);
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
                    loadData();
                    alert("Список успішно очищено!");
                } else {
                    alert("Невірний PIN-код!");
                }
            }

            async function clearHistory() {
                const enteredPin = prompt("Введіть PIN-код для очищення історії:");
                if (!enteredPin) return;

                const response = await fetch(`/clear-history/${enteredPin}`, { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    loadData();
                    alert("Історію успішно очищено!");
                } else {
                    alert("Невірний PIN-код!");
                }
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
    try:
        barcode_data = data.get("code")
        is_a6 = data.get("is_a6", False)
        
        if not barcode_data:
            return {"success": False, "error": "Пустий код"}
            
        target_key = "a6" if is_a6 else "regular"
        target_list = scanned_codes[target_key]
        
        current_time = datetime.now().strftime("%H:%M:%S")
        is_dup = barcode_data in target_list
        
        if is_dup:
            target_list.remove(barcode_data)
            target_list.insert(0, barcode_data)
            status_type = "duplicate"
        else:
            target_list.insert(0, barcode_data)
            status_type = "new"
            
        scan_history.insert(0, {
            "code": barcode_data,
            "type": target_key,
            "time": current_time,
            "status": status_type
        })
        
        return {"success": True, "code": barcode_data, "is_duplicate": is_dup}
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
        target_key = "a6" if is_a6 else "regular"
        target_list = scanned_codes[target_key]
        
        current_time = datetime.now().strftime("%H:%M:%S")
        is_dup = barcode_data in target_list
        
        if is_dup:
            target_list.remove(barcode_data)
            
        target_list.insert(0, barcode_data)
        
        scan_history.insert(0, {
            "code": barcode_data,
            "type": target_key,
            "time": current_time,
            "status": "duplicate" if is_dup else "new"
        })
        
        return {"success": True, "code": barcode_data, "is_duplicate": is_dup}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/all-data")
async def get_all_data():
    return {
        "regular": scanned_codes["regular"],
        "a6": scanned_codes["a6"],
        "history": scan_history
    }
