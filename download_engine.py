import os
import sys
import time
import threading
import subprocess
import shutil
from tkinter import messagebox, simpledialog
from urllib.parse import urlparse, parse_qs
import requests
from ytdlp_engine import _download_via_ytdlp
from history_manager import is_download_paused, update_download_data
from file_utils import _get_filename_from_response

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/octet-stream',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}


def _core_download_engine(app_instance, url, selected_quality=None):
    video_domains = ("youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com", "tiktok.com", "twitter.com", "x.com", "vimeo.com")
    is_platform_video = any(domain in url.lower() for domain in video_domains)
    if is_platform_video or (app_instance.is_video_url and app_instance.video_info is not None):
        _download_via_ytdlp(url, selected_quality, app_instance)
        return

    response_stream = None
    try:
        app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Connecting securely to server...", "text_color": "#a855f7"})
        
        start_time = time.time()
        
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

        if accept_ranges == 'bytes' and file_size > 1024:
            num_threads = app_instance.DEFAULT_THREADS
            app_instance._safe_ui_update(app_instance.lbl_threads, {"text": f"Connections allocated: {num_threads}", "text_color": "#10b981"})
            init_mb = file_size / (1024 * 1024)
            init_size_str = f"{init_mb / 1024:.2f} GB" if init_mb >= 1024 else f"{init_mb:.2f} MB"
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": f"Downloading: {init_size_str}...", "text_color": "#10b981"})

            response_stream.close()

            appdata_local = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
            temp_dir = os.path.join(appdata_local, "DwnlData", str(app_instance.download_id))
            os.makedirs(temp_dir, exist_ok=True)

            chunk_size = file_size // num_threads
            worker_threads = []
            
            temp_files = []
            bytes_already_downloaded = 0
            
            for i in range(num_threads):
                part_path = os.path.join(temp_dir, f"part_{i}.tmp")
                temp_files.append(part_path)
                if os.path.exists(part_path):
                    bytes_already_downloaded += os.path.getsize(part_path)

            bytes_downloaded = [bytes_already_downloaded]
            last_ui_update = [0.0]
            start_time = time.time()

            def worker(thread_idx, start, end):
                part_path = temp_files[thread_idx]
                downloaded_in_part = os.path.getsize(part_path) if os.path.exists(part_path) else 0
                actual_start = start + downloaded_in_part
                
                if actual_start >= end:
                    return
                    
                worker_headers = BROWSER_HEADERS.copy()
                worker_headers['Range'] = f'bytes={actual_start}-{end}'
                
                try:
                    res = requests.get(url, headers=worker_headers, stream=True, timeout=30)
                    with open(part_path, 'ab') as f_part:
                        for chunk in res.iter_content(chunk_size=64128):
                            if app_instance.is_cancelled: break

                            while app_instance.is_paused and app_instance.is_downloading:
                                if app_instance.is_cancelled: break
                                try:
                                    status = is_download_paused(app_instance.download_id)
                                    if status and "downloading" in status.lower():
                                        app_instance.root.after(0, app_instance._toggle_pause)
                                        break
                                except Exception as e:
                                    print(f"Error while checking completion: {e}")

                                time.sleep(0.8)
                            if app_instance.is_cancelled: break
                            if chunk:
                                status_now = is_download_paused(app_instance.download_id)
                                if status_now and "paused" in status_now.lower():
                                    app_instance.root.after(0, app_instance._toggle_pause)
                                    break
                                f_part.write(chunk)
                                chunk_len = len(chunk)

                            with app_instance.lock:
                                bytes_downloaded[0] += chunk_len
                                pct = (bytes_downloaded[0] / file_size) * 100
                                current_time = time.time()
                                
                                if current_time - last_ui_update[0] >= 0.3 or pct >= 99.9:
                                    last_ui_update[0] = current_time
                                    app_instance._safe_progress_update(pct)
                                    
                                    elapsed = current_time - start_time
                                    if elapsed > 0:
                                        actual_downloaded_now = bytes_downloaded[0] - bytes_already_downloaded
                                        if actual_downloaded_now <= 0:
                                            actual_downloaded_now = chunk_len
                                            
                                        speed = actual_downloaded_now / elapsed
                                        
                                        if speed < 1024 * 1024:
                                            speed_str = f"{speed / 1024:.2f} KB/s"
                                        else:
                                            speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
                                        
                                        remaining_bytes = file_size - bytes_downloaded[0]
                                        
                                        if speed > 100: 
                                            eta_seconds = remaining_bytes / speed
                                            if eta_seconds < 60:
                                                eta_str = f"{int(eta_seconds)}s"
                                            elif eta_seconds < 3600:
                                                eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                                            else:
                                                hours = int(eta_seconds // 3600)
                                                minutes = int((eta_seconds % 3600) // 60)
                                                seconds = int(eta_seconds % 60)
                                                eta_str = f"{hours}h {minutes}m {seconds}s"
                                        else:
                                            eta_str = "Calculating..."
                                        
                                        app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"ETA: {eta_str}", "text_color": "#94a3b8"})
                                        update_download_data(app_instance.download_id, time_left=f"{eta_str}")
                                        
                                        remaining_mb = remaining_bytes / (1024 * 1024)
                                        remaining_str = f"{remaining_mb / 1024:.2f} GB" if remaining_mb >= 1024 else f"{remaining_mb:.2f} MB"
                                            
                                        app_instance._safe_ui_update(app_instance.lbl_status, {
                                            "text": f"Downloading... Speed: {speed_str} | Remaining: {remaining_str}", 
                                            "text_color": "#10b981"
                                        })
                                        update_download_data(app_instance.download_id, status="Downloading")
                                        update_download_data(app_instance.download_id, speed=speed_str)                                                    
                except Exception as e:
                    print(f"Worker {thread_idx} error: {e}")

            for i in range(num_threads):
                start = i * chunk_size
                end = file_size - 1 if i == num_threads - 1 else (start + chunk_size - 1)
                t = threading.Thread(target=worker, args=(i, start, end))
                worker_threads.append(t)
                t.start()

            for t in worker_threads:
                t.join()

            if not app_instance.is_cancelled:
                app_instance._safe_ui_update(app_instance.lbl_status, {"text": "🧩 Assembling file parts, please wait...", "text_color": "#38bdf8"})
                try:
                    with open(save_path, 'wb') as f_final:
                        for part_path in temp_files:
                            if os.path.exists(part_path):
                                with open(part_path, 'rb') as f_part:
                                    f_final.write(f_part.read())
                    try: shutil.rmtree(temp_dir)
                    except: pass

                except Exception as merge_error:
                    raise Exception(f"Failed to assemble file parts: {merge_error}")
            else:
                update_download_data(app_instance.download_id, status="Paused")
                app_instance.root.destroy()

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
            
            response_stream = requests.get(url, allow_redirects=True, stream=True, timeout=30, headers=BROWSER_HEADERS)
            
            with open(save_path, 'wb') as f_out:
                for chunk in response_stream.iter_content(chunk_size=64128):
                    if app_instance.is_cancelled: break
                    while app_instance.is_paused and app_instance.is_downloading:
                        if app_instance.is_cancelled: break
                        time.sleep(0.2)
                        
                    if chunk:
                        f_out.write(chunk)
                        current_bytes += len(chunk)
                        
                        elapsed = time.time() - fallback_start_time
                        speed = current_bytes / elapsed if elapsed > 0 else 0
                        speed_mb = speed / (1024 * 1024)
                        
                        if file_size > 0:
                            pct = (current_bytes / file_size) * 100
                            app_instance._safe_progress_update(pct)
                            
                            remaining_bytes = file_size - current_bytes
                            remaining_mb = max(0, remaining_bytes / (1024 * 1024))
                            
                            eta_seconds = remaining_bytes / speed if speed > 0 else 0
                            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s" if eta_seconds > 0 else "Calculating..."
                            app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"ETA: {eta_str}", "text_color": "#94a3b8"})
                            update_download_data(app_instance.download_id, time_left=f"{eta_str}")
                            
                            app_instance._safe_ui_update(app_instance.lbl_status, {
                                "text": f"Downloading... Speed: {speed_mb:.2f} MB/s | Remaining: {remaining_mb:.2f} MB", 
                                "text_color": "#f59e0b"
                            })
                            update_download_data(app_instance.download_id, status="Downloading")
                            update_download_data(app_instance.download_id, speed=speed_mb)
                        else:
                            app_instance.root.after(0, lambda: app_instance.progress.set(0.5))
                            downloaded_mb = current_bytes / (1024 * 1024)
                            app_instance._safe_ui_update(app_instance.lbl_status, {
                                "text": f"Low-Speed Stream... Speed: {speed_mb:.2f} MB/s | Downloaded: {downloaded_mb:.2f} MB", 
                                "text_color": "#f59e0b"
                            })
                            update_download_data(app_instance.download_id, status="Downloading")
                            update_download_data(app_instance.download_id, speed=speed_mb)

        if app_instance.is_cancelled:
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Cancelled by User", "text_color": "#ef4444"})
            update_download_data(app_instance.download_id, status="Cancelled")
            app_instance.root.after(0, lambda: app_instance.progress.set(0))
        else:
            if os.path.exists(save_path) and os.path.getsize(save_path) < 5000 and file_size > 5000:
                raise Exception("Server returned a webpage instead of the file. Link might be expired.")
                    
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "✅ Download Complete!", "text_color": "#10b981"})
            update_download_data(app_instance.download_id, status="✅ Complete")
            app_instance._safe_progress_update(100.0)
            update_download_data(app_instance.download_id, progress="100%")
            answer = messagebox.askyesno("Success", f"File saved successfully:\n{save_path}\n\nDo you want to open the file?")
            if answer:
                try:
                    if sys.platform == "win32": os.startfile(save_path)
                    elif sys.platform == "darwin": subprocess.Popen(["open", save_path])
                    else: subprocess.Popen(["xdg-open", save_path])
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
            try: response_stream.close()
            except: pass
        app_instance._reset_ui()