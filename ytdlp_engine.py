import os
import sys
import re
import subprocess
from tkinter import messagebox
import yt_dlp
from history_manager import find_download_by_name, add_download, update_download_data
from file_utils import _clean_ansi_codes
from Control_fn import _get_unique_filepath

def _get_playlist_item_key(info_dict):
    playlist_index = info_dict.get("playlist_index")
    if playlist_index is not None:
        return f"playlist:{playlist_index}"

    for candidate_key in ("id", "url", "title"):
        value = info_dict.get(candidate_key)
        if value:
            return f"{candidate_key}:{value}"

    return "playlist:unknown"


def _download_via_ytdlp(url, selected_quality, app_instance):
    current_download_dir = app_instance.default_downloads_dir
    if app_instance.is_playlist:
        current_download_dir = os.path.join(current_download_dir, app_instance.title)
        os.makedirs(current_download_dir, exist_ok=True)

    if not hasattr(app_instance, '_finished_filepaths'):
        app_instance._finished_filepaths = set()
    if not hasattr(app_instance, '_processed_playlist_indices'):
        app_instance._processed_playlist_indices = set()
        
    app_instance.accumulated_past_sizes = 0
    app_instance.current_video_total_size = 0

    stream_progress = {}
    stream_sizes = {}

    def ytdlp_hook(d):
        if d['status'] == 'downloading':
            downloaded_bytes = d.get('downloaded_bytes', 0)
            current_filename = d.get('filename', '') or d.get('filepath', '')

            info_dict = d.get('info_dict', {})
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or info_dict.get('filesize') or info_dict.get('filesize_approx') or 0

            if total_bytes > 0:
                overall_percent = (downloaded_bytes / total_bytes) * 100
                overall_percent = min(overall_percent, 99.9)

                total_size_mb = total_bytes / (1024 * 1024)
                downloaded_mb = downloaded_bytes / (1024 * 1024)

                app_instance._safe_ui_update(app_instance.lbl_status, {"text": f"Downloading: {downloaded_mb:.2f} MB / {total_size_mb:.2f} MB", "text_color": "#10b981"})
                app_instance._safe_ui_update(app_instance.lbl_size, {"text": f"Total Size: {total_size_mb:.2f} MB", "text_color": "#94a3b8"})
                update_download_data(app_instance.download_id, size=round(total_size_mb, 2))
                app_instance._safe_progress_update(overall_percent)
                update_download_data(app_instance.download_id, status="Downloading")

            raw_eta = d.get('_eta_str', '--')
            raw_speed = d.get('_speed_str', '--')
            clean_eta = _clean_ansi_codes(app_instance, raw_eta)
            clean_speed = _clean_ansi_codes(app_instance, raw_speed)
            app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"ETA: {clean_eta} ({clean_speed})", "text_color": "#94a3b8"})
            update_download_data(app_instance.download_id, time_left=f"{clean_eta}")
            update_download_data(app_instance.download_id, speed=clean_speed)

            if app_instance.is_cancelled:
                raise Exception("Download cancelled by user")

        elif d['status'] == 'finished':
            info_dict = d.get('info_dict', {})
            current_filename = d.get('filename', '')

            # تحديث اسم الملف الظاهر فور اكتمال الفيديو الحالي
            if current_filename:
                file_basename = os.path.basename(current_filename)
                app_instance._safe_ui_update(app_instance.lbl_file_name, {"text": f"File Name: {file_basename}", "text_color": "#cbd5e1"})

            if current_filename in app_instance._finished_filepaths:
                return
            app_instance._finished_filepaths.add(current_filename)

            if app_instance.is_playlist:
                playlist_key = _get_playlist_item_key(info_dict)
                if playlist_key not in app_instance._processed_playlist_indices:
                    app_instance._processed_playlist_indices.add(playlist_key)
                    if app_instance.remaining_videos > 0:
                        app_instance.remaining_videos -= 1
                        app_instance._safe_ui_update(app_instance.lbl_num_video, {"text": f"Remaining: {app_instance.remaining_videos} video", "text_color": "#10b981"})
                        update_download_data(app_instance.download_id, num_video=app_instance.remaining_videos)
            
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Merging video and audio via FFmpeg... Please wait.", "text_color": "#f59e0b"})
            app_instance._safe_progress_update(100)
    
    default_quality = app_instance.user_settings.get("default_quality", "Best Quality")

    general_quality_map = {
        "Best Quality": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "1440p": "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "Audio Only (MP3)": "bestaudio[ext=mp3]/bestaudio",
        "Audio Only (m4a)": "bestaudio[ext=m4a]/bestaudio",
    }

    target_quality = selected_quality if selected_quality else default_quality
    format_opt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    if app_instance.is_playlist:
        if target_quality in general_quality_map:
            format_opt = general_quality_map[target_quality]
        else:
            height_match = re.findall(r'\d+p', target_quality)
            if height_match:
                h = height_match[0].replace('p', '')
                format_opt = f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            else:
                format_opt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        if target_quality == "Best Quality":
            format_opt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif hasattr(app_instance, 'quality_map') and target_quality in app_instance.quality_map:
            fmt_data = app_instance.quality_map[target_quality]
            if isinstance(fmt_data, dict):
                format_id = fmt_data.get("format_id")
                format_opt = f"{format_id}+bestaudio[ext=m4a]/best[ext=mp4]/best"
            else:
                format_opt = f"{fmt_data}+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif target_quality in general_quality_map:
            format_opt = general_quality_map[target_quality]

    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(os.path.abspath(sys.executable)) 
    else: 
        current_dir = os.path.dirname(os.path.abspath(__file__))

    FFMPEG_DIR = os.path.join(current_dir, 'ffmpeg')
    FFMPEG_PATH = os.path.join(FFMPEG_DIR, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    if not os.path.exists(FFMPEG_PATH):
        FFMPEG_PATH = FFMPEG_DIR

    video_title = app_instance.title if hasattr(app_instance, 'title') else 'Playlist'
    safe_title = re.sub(r'[\\/*?:"<>|]', "", video_title)

    Download_ID = find_download_by_name(safe_title)
    if not Download_ID:
        app_instance.download_id = add_download(url, safe_title)
    else: 
        app_instance.download_id = Download_ID

    appdatalocal = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "DM_Temp")
    temp_video_dir = os.path.join(appdatalocal, "DwnlData", str(app_instance.download_id))
    os.makedirs(temp_video_dir, exist_ok=True)

    # نموذج تسمية الملفات بناءً على ما إذا كانت بلايليست أو فيديو منفرد
    if app_instance.is_playlist:
        outtmpl_pattern = '%(playlist_index)s - %(title)s.%(ext)s'
    else:
        outtmpl_pattern = '%(title)s.%(ext)s'

    ydl_opts = {
        'format': format_opt,
        'outtmpl': outtmpl_pattern,
        'progress_hooks': [ytdlp_hook],
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': FFMPEG_PATH,
        'merge_output_format': 'mp4',
        'concurrent_fragment_downloads': 8,
        'buffersize': 1024 * 256,            
        'retries': 15,                     
        'fragment_retries': 15,  
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        },
        'paths': {
            'home': current_download_dir, 
            'temp': temp_video_dir,      
        },
        'keepvideo': False
    }

    is_audio_only = "Audio Only" in target_quality or target_quality in ["Audio Only (MP3)", "Audio Only (m4a)"]

    if is_audio_only:
        ydl_opts['format'] = 'bestaudio/best'
        if "MP3" in target_quality:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
    else:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]

    try:
        app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Extracting video metadata...", "text_color": "#a855f7"})
        app_instance._safe_ui_update(app_instance.lbl_threads, {"text": "Connections allocated: yt-dlp Engine", "text_color": "#94a3b8"})
        
        app_instance.root.after(0, lambda: app_instance.btn_download.configure(state="disabled"))
        app_instance.root.after(0, lambda: app_instance.btn_pause.configure(state="disabled", text="Use 'Cancel' to Stop", fg_color="#313244"))
        app_instance.final_save_path = current_download_dir

        app_instance._safe_ui_update(app_instance.lbl_path, {"text": f"Save Path: {current_download_dir}", "text_color": "#94a3b8"})
        app_instance.root.after(0, lambda: app_instance.btn_open_folder.configure(state="normal"))
        
        # بدء عملية التحميل المباشرة
        with yt_dlp.YoutubeDL(ydl_opts) as ydl_executor:
            ydl_executor.download([url])
        
        if os.path.exists(temp_video_dir):
            try:
                os.rmdir(temp_video_dir)
            except OSError:
                pass

        app_instance._safe_ui_update(app_instance.lbl_status, {"text": "✅ Download Complete!", "text_color": "#10b981"})
        update_download_data(app_instance.download_id, status="✅ Complete")
        app_instance._safe_progress_update(100.0)
        update_download_data(app_instance.download_id, progress="100%")
        
        answer = messagebox.askyesno("Success", f"All files saved successfully to:\n{current_download_dir}\n\nDo you want to open the folder?")
        if answer:
            try:
                absolute_path = os.path.abspath(current_download_dir)
                if sys.platform == "win32":
                    os.startfile(absolute_path) 
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", absolute_path]) 
                else:
                    subprocess.Popen(["xdg-open", absolute_path]) 
            except Exception as open_error:
                messagebox.showerror("Error", f"Could not open folder:\n{open_error}")

        app_instance.root.after(0, app_instance.root.destroy)

    except Exception as e: 
        if app_instance.is_cancelled:
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Cancelled by User", "text_color": "#ef4444"})
            update_download_data(app_instance.download_id, status="Paused")
            app_instance.root.after(0, lambda: app_instance.progress.set(0))
        else:
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "❌ Download Failed", "text_color": "#ef4444"})
            update_download_data(app_instance.download_id, status="Failed") 
            messagebox.showerror("Download Error", f"yt-dlp encountered an error:\n{e}")
    finally:
        app_instance._reset_ui()