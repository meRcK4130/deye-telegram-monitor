import hashlib
import json
import os
import requests

# Отримання параметрів із Secrets
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
DEYE_EMAIL = os.getenv("DEYE_EMAIL")
DEYE_PASSWORD = os.getenv("DEYE_PASSWORD")
DEVICE_SN = os.getenv("DEVICE_SN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "state.json"

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Помилка відправки в Telegram: {e}")

def get_deye_token():
    url = f"https://api.solarmanpv.com/account/v1.0/token?appId={APP_ID}&language=en"
    payload = {
        "appSecret": APP_SECRET,
        "email": DEYE_EMAIL,
        "password": get_password_hash(DEYE_PASSWORD)
    }
    res = requests.post(url, json=payload, timeout=15)
    data = res.json()
    if data.get("success"):
        return data.get("access_token")
    raise Exception(f"Помилка авторизації Deye: {data}")

def check_grid_status(token):
    url = f"https://api.solarmanpv.com/device/v1.0/currentData?appId={APP_ID}"
    headers = {"Authorization": f"bearer {token}"}
    payload = {"deviceSn": DEVICE_SN}
    
    res = requests.post(url, headers=headers, json=payload, timeout=15)
    data = res.json()
    
    grid_voltage = 0.0
    for item in data.get("dataList", []):
        key = item.get("key", "").lower()
        if "grid" in key and "volt" in key:
            try:
                grid_voltage = float(item.get("value", 0))
                break
            except ValueError:
                pass
                
    return grid_voltage > 50.0, grid_voltage

def main():
    last_state = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                last_state = json.load(f).get("grid_online")
        except Exception:
            last_state = None

    token = get_deye_token()
    is_online, voltage = check_grid_status(token)
    print(f"Поточний стан мережі: {'Є живлення' if is_online else 'Немає живлення'} ({voltage:.1f} V)")

    if last_state is not None:
        if last_state and not is_online:
            send_telegram("🔴 <b>Зникло зовнішнє живлення!</b>\nІнвертор перейшов на акумулятори.")
        elif not last_state and is_online:
            send_telegram(f"🟢 <b>Зовнішнє живлення відновлено!</b>\nПоточна напруга: {voltage:.1f} V")
    else:
        print("Перший запуск: стан ініціалізовано.")

    with open(STATE_FILE, "w") as f:
        json.dump({"grid_online": is_online}, f)

if __name__ == "__main__":
    main()
