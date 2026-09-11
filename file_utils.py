import re
import os
import mimetypes
from urllib.parse import parse_qs
from tkinter import messagebox
import requests
from email.message import Message
from urllib.parse import unquote, urlparse

from history_manager import find_download_by_name, update_download_data, show_data, add_download


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


def _fetch_file_size(app_instance, url):
    """Fetches file size and name via GET session safely supporting ModDB tokens."""
    if show_data(app_instance, app_instance.download_id):
        app_instance.root.after(100, app_instance._start_download_thread)
        return
    try:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        
        response = session.get(url, allow_redirects=True, stream=True, timeout=12)
        app_instance.current_url = response.url
        
        filename = _get_filename_from_response(app_instance, response)
        app_instance._safe_ui_update(app_instance.lbl_file_name, {"text": f"File Name: {filename}", "text_color": "#cbd5e1"})
        app_instance._safe_ui_update(
            app_instance.lbl_mode_title,
            {"text": "Download Mode: Normal", "text_color": "#64748b"}
        )

        file_size = int(response.headers.get('content-length', 0))
        content_type = response.headers.get('content-type', '').lower()

        if 'text/html' in content_type or file_size < 1024:
            parsed_url = urlparse(url)
            queries = parse_qs(parsed_url.query)
            if 'fsize' in queries:
                file_size = int(queries['fsize'][0])
                if file_size > 1024:
                    content_type = 'application/octet-stream'

        if file_size > 0 and 'text/html' not in content_type:
            if file_size:
                size_in_mb = file_size / (1024 * 1024)
                if size_in_mb >= 1024:
                    size_text = f"Size: {size_in_mb / 1024:.2f} GB"
                else:
                    size_text = f"Size: {size_in_mb:.2f} MB"
                    
                app_instance._safe_ui_update(app_instance.lbl_size, {"text": size_text, "text_color": "#10b981"})
                size = re.search(r"[\d.]+", size_text).group()

                Download_ID = find_download_by_name(filename)
                if not Download_ID:
                    app_instance.download_id = add_download(url, filename)
                else:
                    app_instance.download_id = Download_ID
                update_download_data(app_instance.download_id, size=size)

                app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Direct link locked & ready", "text_color": "#10b981"})
                app_instance._safe_ui_update(app_instance.btn_download, {"state": "normal"})
                app_instance.ent_url.configure(state="normal", fg_color="#1e1e2e")
        else:
            app_instance._safe_ui_update(app_instance.lbl_size, {"text": "Size: Blocked / Unknown", "text_color": "#ef4444"})
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Download Blocked: Server returned a webpage", "text_color": "#ef4444"})
            update_download_data(app_instance.download_id, status="Faild")
            app_instance.root.after(0, lambda: app_instance.btn_download.configure(state="disabled"))
            
            unknown_size_warning = (
                "Error: Cannot download this file (Link Expired / Webpage Error).\n\n"
                "The server responded with an HTML webpage instead of the actual file.\n\n"
                "🔒 Downloading has been completely blocked to prevent saving corrupted files.\n\n"
                "💡 How to fix:\n"
                "Go back to your browser, refresh the page, and click download again to get a fresh link."
            )
            messagebox.showerror("Download Manager - Blocked", unknown_size_warning)
            app_instance._reset_ui()
            raise Exception("Blocked: Server returned HTML instead of the actual file.")

    except Exception as e:
        print(f"Error in size fetching: {e}")
        if "Blocked:" not in str(e):
            update_download_data(app_instance.download_id, status="Faild")
            app_instance._safe_ui_update(app_instance.lbl_file_name, {"text": "Error fetching file details", "text_color": "#ef4444"})
            app_instance._safe_ui_update(app_instance.lbl_size, {"text": "Size: Error", "text_color": "#ef4444"})
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Connection failed", "text_color": "#ef4444"})
            app_instance.ent_url.configure(state="normal", fg_color="#1e1e2e")


def _get_filename_from_response(app_instance, response):
    headers = response.headers

    cd = headers.get("Content-Disposition") or headers.get("content-disposition")
    if cd:
        try:
            m = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, re.IGNORECASE)
            if m:
                filename = unquote(m.group(1))
                return _sanitize_filename(app_instance, _decode_filename(app_instance, filename))
            msg = Message()
            msg["Content-Disposition"] = cd
            filename = msg.get_filename()
            if filename:
                filename = _decode_filename(app_instance, filename)
                return _sanitize_filename(app_instance, filename)
        except Exception:
            pass

    try:
        path = urlparse(response.url).path
        filename = os.path.basename(path)
        if filename:
            filename = _decode_filename(app_instance, filename)
            bad_names = {"", "download", "file", "get", "view", "attachment"}
            if filename.lower() not in bad_names:
                return _add_extension_if_needed(app_instance, filename, headers.get("Content-Type", ""))
    except Exception:
        pass

    content_type = headers.get("Content-Type", "").split(";")[0].lower().strip()
    ext = {
        "video/mp4": ".mp4",
        "video/x-matroska": ".mkv",
        "video/x-msvideo": ".avi",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "video/x-flv": ".flv",
        "video/mpeg": ".mpeg",
        "video/3gpp": ".3gp",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/aac": ".aac",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/flac": ".flac",
        "audio/x-m4a": ".m4a",
        "audio/mp4": ".m4a",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/x-rar-compressed": ".rar",
        "application/x-7z-compressed": ".7z"
    }.get(content_type)

    if not ext:
        ext = mimetypes.guess_extension(content_type)

    return f"downloaded_file{ext or '.bin'}"

def _decode_filename(app_instance, filename):
    if not filename:
        return filename
    try:
        filename = unquote(filename)
    except Exception:
        pass
    try:
        if any(c in filename for c in "ØÙÃÂ"):
            filename = filename.encode("latin1").decode("utf-8")
    except Exception:
        pass

    return filename.strip().strip('"')

def _add_extension_if_needed(app_instance, filename, content_type):
    if "." in os.path.basename(filename):
        return _sanitize_filename(app_instance, filename)

    ext = mimetypes.guess_extension(content_type.split(";")[0])
    if ext:
        filename += ext
    return _sanitize_filename(app_instance, filename)

def _sanitize_filename(app_instance, name):
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    return name

def _clean_ansi_codes(app_instance, text):
    if not text:
        return "--"
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text).strip()