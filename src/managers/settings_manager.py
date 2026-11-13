import os
import json

appdata_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
SETTINGS_FILE = os.path.join(appdata_dir, "settings.json")

def load_settings():
    default_settings = {
        "download_dir": os.path.expanduser('~'),
        "default_quality": "Best Quality"
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_settings
    return default_settings

def save_settings(**kwargs):
    current_settings = load_settings()
    current_settings.update(kwargs)

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current_settings, f, indent=4, ensure_ascii=False)
        print(" [Settings] Updated successfully!") 
    except Exception as e:
        print(f" [Settings] Error saving settings: {e}")

