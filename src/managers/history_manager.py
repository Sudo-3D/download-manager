import os
import time
import json
import threading

file_lock = threading.Lock()

appdata_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
if not os.path.exists(appdata_dir):
    os.makedirs(appdata_dir)

DOWNLOADS_FILE = os.path.join(appdata_dir, "downloads_history.json")
if not os.path.exists(DOWNLOADS_FILE):
    with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)


import os
import time
import json
import threading  # 👈 أضف هذا الاستيراد

# 👈 قم بإنشاء قفل عالمي خاص بالملف بالأسفل
file_lock = threading.Lock()

appdata_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
if not os.path.exists(appdata_dir):
    os.makedirs(appdata_dir)

DOWNLOADS_FILE = os.path.join(appdata_dir, "downloads_history.json")
if not os.path.exists(DOWNLOADS_FILE):
    with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)


def update_download_data(download_id, **kwargs):
    # استخدام القفل هنا لمنع أي خيط آخر من الدخول حتى تنتهي العملية تماماً
    with file_lock: 
        for attempt in range(10):
            try:
                if not os.path.exists(DOWNLOADS_FILE):
                    return False

                with open(DOWNLOADS_FILE, "r", encoding="utf-8") as f:
                    downloads = json.load(f)

                updated = False
                for item in downloads:
                    if item.get("id") == download_id:
                        item.update(kwargs)
                        updated = True
                        break

                if updated:
                    temp_file = DOWNLOADS_FILE + ".tmp"
                    
                    with open(temp_file, "w", encoding="utf-8") as f:
                        json.dump(downloads, f, ensure_ascii=False, indent=4)
                    
                    if os.path.exists(temp_file):
                        os.replace(temp_file, DOWNLOADS_FILE)
                
                return updated

            except (PermissionError, json.JSONDecodeError) as e:
                print(f"File busy or locked, retrying ({attempt + 1}/5)... Error: {e}")
                time.sleep(0.02)
            except Exception as e:
                print(f"Critical Update JSON Error: {e}")
                return False
                
        return False

def add_download(url, name):
    with file_lock:
        try:
            if not os.path.exists(DOWNLOADS_FILE):
                with open(DOWNLOADS_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=4)

            with open(DOWNLOADS_FILE, "r", encoding="utf-8") as f:
                downloads = json.load(f)
            # إنشاء id جديد
            new_id = max((item["id"] for item in downloads), default=0) + 1

            downloads.append({
                "id": new_id,
                "name": name,
                "status": "في الانتظار",
                "size": "0 MB",
                "progress": "0%",
                "speed": "0 KB/s",
                "time_left": "--",
                "url": url
            })

            with open(DOWNLOADS_FILE, "w", encoding="utf-8") as f:
                json.dump(downloads, f, ensure_ascii=False, indent=4)

            return new_id

        except Exception as e:
            print(f"Add Download Error: {e}")
            return None
    
def find_download_by_name(file_name):
    with file_lock:
        try:
            if not os.path.exists(DOWNLOADS_FILE):
                return None

            with open(DOWNLOADS_FILE, "r", encoding="utf-8") as f:
                downloads = json.load(f)

            for item in downloads:
                if item.get("name") == file_name:
                    return item["id"]

            return None

        except Exception as e:
            print(f"Find Download Error: {e}")
            return None
    
def is_download_paused(file_id):
    with file_lock:
        if os.path.exists(DOWNLOADS_FILE):
            try:
                with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
                    downloads = json.load(f)
                for item in downloads:
                    if str(item.get("id")) == str(file_id):
                        return item.get("status")
            except Exception:
                return False
        return False

def get_download_by_id(download_id):
    with file_lock:
        try:
            if not os.path.exists(DOWNLOADS_FILE):
                return None

            with open(DOWNLOADS_FILE, "r", encoding="utf-8") as f:
                downloads = json.load(f)
                
            if download_id is None or str(download_id).strip() == "":
                print("Warning: update_download_status received an empty or None download_id")
                return False
            
            for item in downloads:
                if item.get("id") == int(download_id):
                    return item

            return False

        except Exception as e:
            print(f"Get Download Error: {e}")
            return False
    
    
def show_data(app_instance, download_id):
    try:
        download = get_download_by_id(download_id)

        if not download:
            return False

        # استخدام .get() مع وضع قيم افتراضية آمنة لمنع الـ KeyError نهائياً
        filename = download.get("name", "Unknown File")
        size = download.get("size", "Unknown")
        status = download.get("status", "Idle")
        progress = download.get("progress", "0%")
        speed = download.get("speed", "0 KB/s")
        time_left = download.get("time_left", "--:--:--")

        # تحديث اسم الملف
        app_instance._safe_ui_update(
            app_instance.lbl_file_name,
            {"text": f"File Name: {filename}", "text_color": "#2c3e50"}
        )

        # تحديث الحجم
        app_instance._safe_ui_update(
            app_instance.lbl_size,
            {"text": f"Size: {size}", "text_color": "#2c3e50"}
        )

        # تحديث الحالة (يمكنك تغيير اللون بناءً على الحالة إن أردت)
        app_instance._safe_ui_update(
            app_instance.lbl_status,
            {"text": f"Status: {status}", "text_color": "green" if "مكتمل" in status or "Ready" in status else "orange"}
        )
        
        # تصحيح تحديث النسبة المئوية الفعلي
        app_instance._safe_ui_update(
            app_instance.lbl_percentage, 
            {"text": progress}
        )

        # لو عندك الليبلات دي

        # app_instance._safe_ui_update(app_instance.lbl_progress, {"text": f"Progress: {progress}"})

        # app_instance._safe_ui_update(app_instance.lbl_speed, {"text": f"Speed: {speed}"})

        # app_instance._safe_ui_update(app_instance.lbl_time_left, {"text": f"Time Left: {time_left}"})
        return True

    except Exception as e:
        print(f"Show Data Error: {e}")
        return False