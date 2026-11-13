import os
import sys
import time
import threading
import subprocess
import shutil
from tkinter import messagebox, simpledialog
from urllib.parse import urlparse, parse_qs
import requests
from src.core.ytdlp_engine import _download_via_ytdlp
from src.managers.history_manager import is_download_paused, update_download_data
from src.utils.file_utils import _get_filename_from_response

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'identity',
    'Connection': 'keep-alive',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
}


def _format_eta(eta_seconds):
    if eta_seconds <= 0:
        return "Calculating..."
    if eta_seconds < 60:
        return f"{int(eta_seconds)}s"
    if eta_seconds < 3600:
        return f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
    hours = int(eta_seconds // 3600)
    minutes = int((eta_seconds % 3600) // 60)
    seconds = int(eta_seconds % 60)
    return f"{hours}h {minutes}m {seconds}s"


def _core_download_engine(app_instance, url, selected_quality=None):
    video_domains = (
        "youtube.com", "youtu.be", "facebook.com", "fb.watch",
        "instagram.com", "tiktok.com", "twitter.com", "x.com", "vimeo.com"
    )
    is_platform_video = any(domain in url.lower() for domain in video_domains)
    if is_platform_video or (app_instance.is_video_url and app_instance.video_info is not None):
        _download_via_ytdlp(url, selected_quality, app_instance)
        return

    response_stream = None
    try:
        app_instance._safe_ui_update(
            app_instance.lbl_status,
            {"text": "Connecting securely to server...", "text_color": "#a855f7"}
        )

        response_stream = requests.get(url, allow_redirects=True, stream=True, timeout=15, headers=BROWSER_HEADERS)
        content_type = response_stream.headers.get('content-type', '').lower()

        if 'text/html' in content_type or response_stream.status_code in [403, 410, 401]:
            response_stream.close()

            appdata_local = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
            temp_dir = os.path.join(appdata_local, "DwnlData", str(app_instance.download_id))

            if os.path.exists(temp_dir) and os.listdir(temp_dir):
                new_url = simpledialog.askstring(
                    "Link Expired (IDM Style)",
                    "The current download link expired or server returned an error.\n\n"
                    "Please refresh the link in your browser and paste the new URL here:",
                    parent=app_instance.root
                )

                if new_url and new_url.strip().startswith(("http://", "https://")):
                    url = new_url.strip()
                    update_download_data(app_instance.download_id, url=url)
                    app_instance.url_var.set(url)
                    response_stream = requests.get(url, allow_redirects=True, stream=True, timeout=15, headers=BROWSER_HEADERS)
                else:
                    app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Blocked: Link Expired", "text_color": "#ef4444"})
                    update_download_data(app_instance.download_id, status="Failed")
                    app_instance._reset_ui()
                    return
            else:
                app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Blocked: HTML Webpage", "text_color": "#ef4444"})
                update_download_data(app_instance.download_id, status="Failed")
                messagebox.showerror("Download Error", "Critical: Server responded with an HTML webpage instead of the file.")
                app_instance._reset_ui()
                return

        original_filename = _get_filename_from_response(app_instance, response_stream)
        save_path = os.path.join(app_instance.default_downloads_dir, original_filename)

        app_instance.final_save_path = save_path
        filename_only = os.path.basename(save_path)
        folder_only = os.path.dirname(save_path)
        app_instance._safe_ui_update(app_instance.lbl_mode_title, {"text": "Download Mode: Normal", "text_color": "#64748b"})
        app_instance._safe_ui_update(app_instance.lbl_file_name, {"text": f"File Name: {filename_only}", "text_color": "#cbd5e1"})
        app_instance._safe_ui_update(app_instance.lbl_path, {"text": f"Save Path: {folder_only}", "text_color": "#94a3b8"})
        app_instance.root.after(0, lambda: app_instance.btn_open_folder.configure(state="normal"))

        file_size = int(response_stream.headers.get('content-length', 0))
        content_type = response_stream.headers.get('content-type', '').lower()

        if 'text/html' in content_type or file_size < 1024:
            queries = parse_qs(urlparse(url).query)
            if 'fsize' in queries:
                file_size = int(queries['fsize'][0])

        accept_ranges = response_stream.headers.get('accept-ranges', 'none').lower()
        if 'text/html' in content_type:
            accept_ranges = 'none'

        # إغلاق الاتصال المبدئي بعد قراءة الـ Headers
        response_stream.close()
        response_stream = None

        # =========================================================
        # 1. وضع التحميل متعدد الاتصالات (Multi-Threaded)
        # =========================================================
        if accept_ranges == 'bytes' and file_size > 1024:
            num_threads = app_instance.DEFAULT_THREADS
            app_instance._safe_ui_update(app_instance.lbl_threads, {"text": f"Connections allocated: {num_threads}", "text_color": "#10b981"})
            init_mb = file_size / (1024 * 1024)
            init_size_str = f"{init_mb / 1024:.2f} GB" if init_mb >= 1024 else f"{init_mb:.2f} MB"
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": f"Downloading: {init_size_str}...", "text_color": "#10b981"})

            appdata_local = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
            temp_dir = os.path.join(appdata_local, "DwnlData", str(app_instance.download_id))
            os.makedirs(temp_dir, exist_ok=True)

            chunk_size = file_size // num_threads
            worker_threads = []
            worker_errors = []
            temp_files = []
            bytes_already_downloaded = 0

            for i in range(num_threads):
                part_path = os.path.join(temp_dir, f"part_{i}.tmp")
                temp_files.append(part_path)
                expected_part_size = (file_size - (i * chunk_size)) if i == num_threads - 1 else chunk_size
                if os.path.exists(part_path):
                    existing_size = os.path.getsize(part_path)
                    # إذا كان الجزء تالفاً وحجمه أكبر من المتوقع يتم تصفيره
                    if existing_size > expected_part_size:
                        os.remove(part_path)
                    else:
                        bytes_already_downloaded += existing_size

            bytes_downloaded = [bytes_already_downloaded]
            last_ui_update = [0.0]
            start_time = time.time()

            def worker(thread_idx, start, end):
                part_path = temp_files[thread_idx]
                max_retries = 5
                attempt = 0

                while attempt < max_retries and not app_instance.is_cancelled:
                    downloaded_in_part = os.path.getsize(part_path) if os.path.exists(part_path) else 0
                    actual_start = start + downloaded_in_part

                    if actual_start > end:
                        return  # الجزء مكتمل بالكامل

                    worker_headers = BROWSER_HEADERS.copy()
                    worker_headers['Range'] = f'bytes={actual_start}-{end}'

                    try:
                        with requests.get(url, headers=worker_headers, stream=True, timeout=30) as res:
                            if res.status_code != 206:
                                raise Exception(f"Server returned HTTP {res.status_code} instead of 206 Partial Content")

                            with open(part_path, 'ab') as f_part:
                                for chunk in res.iter_content(chunk_size=131072):  # 128KB
                                    if app_instance.is_cancelled:
                                        return

                                    while app_instance.is_paused and app_instance.is_downloading:
                                        if app_instance.is_cancelled:
                                            return
                                        try:
                                            status = is_download_paused(app_instance.download_id)
                                            if status and "downloading" in status.lower():
                                                app_instance.root.after(0, app_instance._toggle_pause)
                                                break
                                        except Exception:
                                            pass
                                        time.sleep(0.5)

                                    if app_instance.is_cancelled:
                                        return
                                    if not chunk:
                                        continue

                                    f_part.write(chunk)
                                    chunk_len = len(chunk)

                                    with app_instance.lock:
                                        bytes_downloaded[0] += chunk_len
                                        current_time = time.time()

                                        if current_time - last_ui_update[0] >= 0.5 or bytes_downloaded[0] >= file_size:
                                            last_ui_update[0] = current_time

                                            # التحقق من حالة الإيقاف من الداتابيز مرة واحدة كل 0.5 ثانية فقط
                                            status_now = is_download_paused(app_instance.download_id)
                                            if status_now and "paused" in status_now.lower() and not app_instance.is_paused:
                                                app_instance.root.after(0, app_instance._toggle_pause)

                                            pct = min(100.0, (bytes_downloaded[0] / file_size) * 100)
                                            app_instance._safe_progress_update(pct)

                                            elapsed = current_time - start_time
                                            if elapsed > 0:
                                                actual_downloaded_now = max(chunk_len, bytes_downloaded[0] - bytes_already_downloaded)
                                                speed = actual_downloaded_now / elapsed

                                                if speed < 1024 * 1024:
                                                    speed_str = f"{speed / 1024:.2f} KB/s"
                                                else:
                                                    speed_str = f"{speed / (1024 * 1024):.2f} MB/s"

                                                remaining_bytes = max(0, file_size - bytes_downloaded[0])
                                                eta_str = _format_eta(remaining_bytes / speed) if speed > 100 else "Calculating..."

                                                remaining_mb = remaining_bytes / (1024 * 1024)
                                                remaining_str = f"{remaining_mb / 1024:.2f} GB" if remaining_mb >= 1024 else f"{remaining_mb:.2f} MB"

                                                app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"ETA: {eta_str}", "text_color": "#94a3b8"})
                                                app_instance._safe_ui_update(app_instance.lbl_status, {
                                                    "text": f"Downloading... Speed: {speed_str} | Remaining: {remaining_str}",
                                                    "text_color": "#10b981"
                                                })
                                                update_download_data(
                                                    app_instance.download_id,
                                                    status="Downloading",
                                                    speed=speed_str,
                                                    time_left=eta_str
                                                )
                        return  # اكتمل الجزء بنجاح

                    except Exception as e:
                        attempt += 1
                        print(f"Worker {thread_idx} retry {attempt}/{max_retries}: {e}")
                        time.sleep(2 * attempt)

                with app_instance.lock:
                    worker_errors.append(f"Part {thread_idx} failed after {max_retries} retries.")

            for i in range(num_threads):
                start = i * chunk_size
                end = file_size - 1 if i == num_threads - 1 else (start + chunk_size - 1)
                t = threading.Thread(target=worker, args=(i, start, end))
                worker_threads.append(t)
                t.start()

            for t in worker_threads:
                t.join()

            if not app_instance.is_cancelled:
                if worker_errors:
                    raise Exception("Download incomplete due to connection drops:\n" + "\n".join(worker_errors))

                app_instance._safe_ui_update(app_instance.lbl_status, {"text": "🧩 Assembling file parts, please wait...", "text_color": "#38bdf8"})
                try:
                    with open(save_path, 'wb') as f_final:
                        for part_path in temp_files:
                            if not os.path.exists(part_path):
                                raise Exception(f"Missing temporary part: {os.path.basename(part_path)}")
                            with open(part_path, 'rb') as f_part:
                                shutil.copyfileobj(f_part, f_final, length=1024 * 1024)  # 1MB buffer

                    final_size = os.path.getsize(save_path)
                    if final_size != file_size:
                        raise Exception(f"File verification failed: expected {file_size} bytes, got {final_size} bytes.")

                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass

                except Exception as merge_error:
                    raise Exception(f"Failed to assemble file parts: {merge_error}")
            else:
                update_download_data(app_instance.download_id, status="Paused")
                app_instance.root.destroy()
                return

        # =========================================================
        # 2. وضع الاتصال الواحد (Single Stream Fallback)
        # =========================================================
        else:
            app_instance._safe_ui_update(app_instance.lbl_threads, {"text": "Connections allocated: 1 (Single Stream Fallback)", "text_color": "#f59e0b"})
            app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": "ETA: Calculating...", "text_color": "#94a3b8"})

            firewall_warning_msg = (
                "Notice: This server does not support multi-threading, or your Firewall/Antivirus "
                "is blocking additional connections.\n\n"
                "The download will proceed in single-connection mode, which might be significantly slower "
                "or show 'Unknown Size'.\n\n"
                "💡 What to check:\n"
                "- Verify if your Antivirus/Firewall is blocking Python network traffic.\n"
                "- Some servers strictly limit downloading to 1 connection per IP."
            )
            messagebox.showwarning("Download Manager - Connection Warning", firewall_warning_msg)

            current_bytes = 0
            fallback_start_time = time.time()
            last_fallback_ui_update = 0.0

            with requests.get(url, allow_redirects=True, stream=True, timeout=30, headers=BROWSER_HEADERS) as stream_res:
                if stream_res.status_code not in (200, 206):
                    raise Exception(f"Server returned unexpected HTTP status: {stream_res.status_code}")

                with open(save_path, 'wb') as f_out:
                    for chunk in stream_res.iter_content(chunk_size=131072):  # 128KB
                        if app_instance.is_cancelled:
                            break
                        while app_instance.is_paused and app_instance.is_downloading:
                            if app_instance.is_cancelled:
                                break
                            time.sleep(0.3)

                        if app_instance.is_cancelled:
                            break
                        if not chunk:
                            continue

                        f_out.write(chunk)
                        current_bytes += len(chunk)

                        now = time.time()
                        if now - last_fallback_ui_update >= 0.5 or (file_size > 0 and current_bytes >= file_size):
                            last_fallback_ui_update = now
                            elapsed = now - fallback_start_time
                            speed = current_bytes / elapsed if elapsed > 0 else 0
                            speed_mb = speed / (1024 * 1024)

                            if file_size > 0:
                                pct = min(100.0, (current_bytes / file_size) * 100)
                                app_instance._safe_progress_update(pct)

                                remaining_bytes = max(0, file_size - current_bytes)
                                remaining_mb = remaining_bytes / (1024 * 1024)
                                eta_str = _format_eta(remaining_bytes / speed) if speed > 100 else "Calculating..."

                                app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"ETA: {eta_str}", "text_color": "#94a3b8"})
                                app_instance._safe_ui_update(app_instance.lbl_status, {
                                    "text": f"Downloading... Speed: {speed_mb:.2f} MB/s | Remaining: {remaining_mb:.2f} MB",
                                    "text_color": "#f59e0b"
                                })
                                update_download_data(
                                    app_instance.download_id,
                                    status="Downloading",
                                    speed=f"{speed_mb:.2f} MB/s",
                                    time_left=eta_str
                                )
                            else:
                                app_instance.root.after(0, lambda: app_instance.progress.set(0.5))
                                downloaded_mb = current_bytes / (1024 * 1024)
                                app_instance._safe_ui_update(app_instance.lbl_status, {
                                    "text": f"Low-Speed Stream... Speed: {speed_mb:.2f} MB/s | Downloaded: {downloaded_mb:.2f} MB",
                                    "text_color": "#f59e0b"
                                })
                                update_download_data(
                                    app_instance.download_id,
                                    status="Downloading",
                                    speed=f"{speed_mb:.2f} MB/s"
                                )

            if not app_instance.is_cancelled and file_size > 0:
                final_size = os.path.getsize(save_path)
                if final_size != file_size:
                    raise Exception(f"Incomplete stream: expected {file_size} bytes, got {final_size} bytes.")

        # =========================================================
        # 3. إنهاء التحميل والتحقق النهائي
        # =========================================================
        if app_instance.is_cancelled:
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Cancelled by User", "text_color": "#ef4444"})
            update_download_data(app_instance.download_id, status="Cancelled")
            app_instance.root.after(0, lambda: app_instance.progress.set(0))
        else:
            if os.path.exists(save_path) and os.path.getsize(save_path) < 5000 and file_size > 5000:
                raise Exception("Server returned a webpage instead of the file. Link might be expired.")

            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "✅ Download Complete!", "text_color": "#10b981"})
            update_download_data(app_instance.download_id, status="✅ Complete", progress="100%")
            app_instance._safe_progress_update(100.0)
            answer = messagebox.askyesno("Success", f"File saved successfully:\n{save_path}\n\nDo you want to open the file?")
            if answer:
                try:
                    if sys.platform == "win32":
                        os.startfile(save_path)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", save_path])
                    else:
                        subprocess.Popen(["xdg-open", save_path])
                except Exception as open_error:
                    messagebox.showerror("Error", f"Could not open file:\n{open_error}")
            app_instance.root.after(0, app_instance.root.destroy)

    except Exception as e:
        app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Failed", "text_color": "#ef4444"})
        update_download_data(app_instance.download_id, status="Faild")
        messagebox.showerror("Download Error", f"Something went wrong:\n{e}")
        app_instance.ent_url.configure(state="normal", fg_color="#1e1e2e")
    finally:
        if response_stream:
            try:
                response_stream.close()
            except Exception:
                pass
        app_instance._reset_ui()