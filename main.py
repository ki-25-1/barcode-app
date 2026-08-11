from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from PIL import Image
from pyzbar.pyzbar import decode
import io

app = FastAPI()

# База даних у пам'яті для зберігання списків штрихкодів
scanned_codes = {
    "regular": [],
    "a6": []
}

@app.post("/clear/{list_type}")
async def clear_list(list_type: str):
    if list_type in scanned_codes:
        scanned_codes[list_type] = []
    return {"success": True}

@app.get("/", response_class=HTMLResponse)
async def main_page():
    return """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Сканер штрихкодів</title>
        <style>
            body { font-family: sans-serif; padding: 20px; background: #f4f6f8; max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .flex-grid { display: flex; gap: 20px; flex-wrap: wrap; }
            .col { flex: 1; min-width: 300px; }
            .item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; font-size: 18px; }
            button { cursor: pointer; padding: 10px 16px; border-radius: 6px; border: none; background: #0066cc; color: white; font-weight: bold; font-size: 16px; }
            .btn-clear { background: #ff4d4d; margin-bottom: 10px; width: 100%; }
            .btn-copy { background: #28a745; padding: 6px 12px; font-size: 14px; }
            input[type="file"] { width: 100%; padding: 10px; box-sizing: border-box; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 6px; background: #fff; }
            .checkbox-label { font-size: 18px; display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 15px; }
            .checkbox-label input { width: 22px; height: 22px; }
            code { background: #eef2f5; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Робочий сканер цінників</h1>
        
        <div class="card">
            <h2>Додати штрихкод з телефону</h2>
            <form id="uploadForm">
                <label class="checkbox-label">
                    <input type="checkbox" id="isA6"> 
                    <span>Цінник А6</span>
                </label>
                <input type="file" id="photoInput" accept="image/*" capture="environment" required>
                <button type="submit" style="width: 100%;">Надіслати фото</button>
            </form>
            <div id="status" style="margin-top: 10px; font-weight: bold; color: #0066cc;"></div>
        </div>

        <div class="flex-grid">
            <div class="col card">
                <h3>Звичайні цінники (Кількість: <span id="regCount">0</span>)</h3>
                <button class="btn-clear" onclick="clearList('regular')">Очистити звичайний список</button>
                <div id="regularList"></div>
            </div>
            
            <div class="col card">
                <h3>Цінники А6 (Кількість: <span id="a6Count">0</span>)</h3>
                <button class="btn-clear" onclick="clearList('a6')">Очистити список А6</button>
                <div id="a6List"></div>
            </div>
        </div>

        <script>
            async function loadCodes() {
                try {
                    const res = await fetch('/codes');
                    const data = await res.json();
                    
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

            // Функція для шифрування введеного PIN-коду (SHA-256)
            async function sha256(message) {
                const msgBuffer = new TextEncoder().encode(message);
                const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
                const hashArray = Array.from(new Uint8Array(hashBuffer));
                return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            }

            async function clearList(type) {
                const enteredPin = prompt("Введіть захищений PIN-код для очищення списку:");
                if (!enteredPin) return; // Якщо натиснули "Скасувати"

                // Зашифрований хенш від пін-коду '5141'
                const targetHash = "216c561b36997d9e4ea20f86641215bb4b87cbba86b4fc487eec8d9cfb87e2b6";
                const hashedInput = await sha256(enteredPin);

                if (hashedInput === targetHash) {
                    await fetch('/clear/' + type, { method: 'POST' });
                    loadCodes();
                    alert("Список успішно очищено!");
                } else {
                    alert("Невірний PIN-код! Очищення скасовано.");
                }
            }

            document.getElementById('uploadForm').onsubmit = async (e) => {
                e.preventDefault();
                const status = document.getElementById('status');
                status.innerText = "Обробка фото та пошук штрихкоду...";
                
                const formData = new FormData();
                const fileInput = document.getElementById('photoInput');
                const isA6 = document.getElementById('isA6').checked;
                
                formData.append('file', fileInput.files[0]);
                formData.append('is_a6', isA6);
                
                try {
                    const response = await fetch('/scan', { method: 'POST', body: formData });
                    const result = await response.json();
                    
                    if (result.success) {
                        status.style.color = "green";
                        status.innerText = "Успішно розпізнано: " + result.code;
                        fileInput.value = "";
                        loadCodes();
                    } else {
                        status.style.color = "red";
                        status.innerText = "Помилка: " + result.error;
                    }
                } catch (err) {
                    status.style.color = "red";
                    status.innerText = "Помилка з'єднання з сервером.";
                }
            };

            setInterval(loadCodes, 2000);
            loadCodes();
        </script>
    </body>
    </html>
    """

@app.post("/scan")
async def scan_barcode(file: UploadFile = File(...), is_a6: bool = Form(False)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        decoded = decode(image)
        if not decoded:
            return {"success": False, "error": "Штрихкод на фото не знайдено. Зробіть чіткіший знімок."}
        
        barcode_data = decoded[0].data.decode('utf-8')
        
        if is_a6:
            scanned_codes["a6"].insert(0, barcode_data)
        else:
            scanned_codes["regular"].insert(0, barcode_data)
            
        return {"success": True, "code": barcode_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/codes")
async def get_codes():
    return scanned_codes
