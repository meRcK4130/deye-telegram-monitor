import hashlib
import json
import os
import requests

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
DEYE_EMAIL = os.getenv("DEYE_EMAIL")
DEYE_PASSWORD = os.getenv("DEYE_PASSWORD")
DEVICE_SN = os.getenv("DEVICE_SN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "state.json"
BASE_URL = "https://eu1-developer.deyecloud.com"

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest().lower()

def send_telegram(message: str):
    # Розбиваємо рядок із Chat ID за комою
    chat_ids = [cid.strip() for cid in CHAT_ID.split(",") if cid.strip()]
    
    for cid in chat_ids:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            print(f"-> Надіслано до {cid}: {res.status_code}")
        except Exception as e:
            print(f"Помилка відправки для {cid}: {e}")
            
def get_deye_token():
    url = f"{BASE_URL}/v1.0/account/token?appId={APP_ID}"
    headers = {"Content-Type": "application/json"}
    
    # Спроба 1: з SHA-256 хешем
    payload_hash = {
        "appSecret": APP_SECRET.strip(),
        "email": DEYE_EMAIL.strip(),
        "password": get_password_hash(DEYE_PASSWORD.strip())
    }
    res = requests.post(url, headers=headers, json=payload_hash, timeout=15)
    data = res.json()
    if data.get("success") or data.get("code") == "1000000":
        return data.get("accessToken") or data.get("access_token")

    # Спроба 2: plain text
    payload_plain = {
        "appSecret": APP_SECRET.strip(),
        "email": DEYE_EMAIL.strip(),
        "password": DEYE_PASSWORD.strip()
    }
    res = requests.post(url, headers=headers, json=payload_plain, timeout=15)
    data = res.json()
    if data.get("success") or data.get("code") == "1000000":
        return data.get("accessToken") or data.get("access_token")

    raise Exception(f"Помилка авторизації Deye: {data}")

def check_grid_status(token):
    url = f"{BASE_URL}/v1.0/device/latest"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"bearer {token}"
    }
    payload = {
        "deviceList": [DEVICE_SN.strip()]
    }
    
    res = requests.post(url, headers=headers, json=payload, timeout=15)
    data = res.json()
    print(f"-> Відповідь Deye Data: {data}")
    
    grid_voltage = 0.0
    device_data = data.get("deviceDataList", [])
    if not device_data:
        device_data = data.get("dataList", [])
        
    for item in device_data:
        if str(item.get("deviceSn")) == str(DEVICE_SN.strip()):
            for point in item.get("dataList", []):
                key = str(point.get("key", "")).lower()
                if "grid" in key and "volt" in key:
                    try:
                        grid_voltage = float(point.get("value", 0))
                        break
                    except (ValueError, TypeError):
                        pass

    is_online = grid_voltage > 50.0
    return is_online, grid_voltage

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
    print(f"Стан: {'Є живлення' if is_online else 'Немає живлення'} ({voltage:.1f} V)")

    # Надсилаємо сповіщення ТІЛЬКИ при зміні стану:
    if last_state is not None:
        if last_state and not is_online:
            send_telegram("🔴 <b>Зникло зовнішнє живлення!</b>\nІнвертор перейшов на акумулятори.")
        elif not last_state and is_online:
            send_telegram(f"🟢 <b>Зовнішнє живлення відновлено!</b>\nПоточна напруга: {voltage:.1f} V")
    else:
        print("Перший запуск: початковий стан успішно збережено в пам'ять.")

    with open(STATE_FILE, "w") as f:
        json.dump({"grid_online": is_online}, f)

if __name__ == "__main__":
    main()
