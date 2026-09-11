import sys
import json
import struct
import subprocess
import os

def get_message():
    """Safely read the incoming message from the browser channel"""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if not raw_length or len(raw_length) < 4:
            return None
        message_length = struct.unpack('I', raw_length)[0]
        message = sys.stdin.buffer.read(message_length).decode('utf-8')
        return json.loads(message)
    except Exception:
        return None

def send_reply_to_browser(response_dict):
    """Send a correctly formatted JSON response back to the browser"""
    try:
        reply_data = json.dumps(response_dict).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('I', len(reply_data)))
        sys.stdout.buffer.write(reply_data)
        sys.stdout.buffer.flush()
    except Exception:
        pass

if __name__ == '__main__':
    # تحديد مسار المجلد بناءً على مكان السكربت الحالي بشكل قاطع
    current_dir = os.path.dirname(os.path.abspath(__file__))

    while True:
        msg = get_message()
        
        if msg is None:
            sys.exit(0)
            
        if 'url' in msg:
            download_url = msg['url']
            
            # ---------------------------------------------------------
            # --- مرحلة تنظيف ومعالجة الرابط قبل إرساله للسكريبت الأساسي ---
            # ---------------------------------------------------------
            if isinstance(download_url, str):
                # 1. تنظيف الرابط من أي مسافات زائدة في البداية والنهاية
                download_url = download_url.strip()

                # 2. فحص لو الرابط مبعوث كـ JSON string (محتمل من الإكستنشن)
                if download_url.startswith("{") and "url" in download_url:
                    try:
                        data = json.loads(download_url)
                        download_url = data.get("url", download_url).strip()
                    except Exception:
                        pass

                # 3. فحص بروتوكول الإكستنشن المخصص وتعديله لبروتوكول ويب حقيقي
                if download_url.startswith("mydl://"):
                    download_url = download_url.replace("mydl://", "https://")
            # ---------------------------------------------------------

            main_exe_path = os.path.join(current_dir, 'main.exe')
            main_py_path = os.path.join(current_dir, 'main.py')
            
            try:
                if os.path.exists(main_exe_path):
                    subprocess.Popen(
                        [main_exe_path, download_url],
                        cwd=current_dir, # تحديد مجلد العمل للبرنامج المنبثق
                        creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0
                    )
                    send_reply_to_browser({"status": "success", "message": "Launched main.exe successfully"})
                    
                elif os.path.exists(main_py_path):
                    python_executable = sys.executable if sys.executable else "python"
                    subprocess.Popen(
                        [python_executable, main_py_path, download_url],
                        cwd=current_dir, # تحديد مجلد العمل للبرنامج المنبثق
                        creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0
                    )
                    send_reply_to_browser({"status": "success", "message": "Launched main.py successfully"})
                else:
                    send_reply_to_browser({"status": "error", "message": f"Neither main.exe nor main.py was found in {current_dir}"})
            
            except Exception as e:
                send_reply_to_browser({"status": "error", "message": str(e)})
        else:
            send_reply_to_browser({"status": "ignored", "message": "No URL found in message"})