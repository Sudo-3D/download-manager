import re
import os
import threading
import requests
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from history_manager import find_download_by_name, update_download_data, get_download_by_id
from file_utils import _fetch_file_size

def _analyze_url(url, app_instance):
    app_instance._safe_ui_update(app_instance.btn_download, {"state": "disabled"})
    app_instance.is_playlist = False
    try:
        lower_url = url.lower().split('?')[0]
        direct_file_extensions = (
            '.zip', '.rar', '.7z', '.tar', '.gz', 
            '.exe', '.msi', '.pdf', '.docx', '.xlsx', 
            '.jpg', '.jpeg', '.png', '.gif', '.mp3', '.wav'
        )
        if lower_url.endswith(direct_file_extensions):
            return False, None

        # --- تصحيح الشرط ليشمل جميع أنماط يوتيوب والـ Playlists بشكل مضمون ---
        video_domains = ("youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com", "tiktok.com", "twitter.com", "x.com", "vimeo.com")
        lower_full_url = url.lower()
        
        is_known_video_platform = any(domain in lower_full_url for domain in video_domains)

        if not is_known_video_platform:
            playlist_markers = ("/playlist", "list=", "/watch?v=", "/shorts/", "/live/")
            is_known_video_platform = any(marker in lower_full_url for marker in playlist_markers)

        # إذا كان الرابط يخص يوتيوب أو بلايليست، نجبر البرنامج على استخدام yt-dlp ومطالعة البيانات فوراً
        if is_known_video_platform:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'skip_download': True,
                'check_formats': False,
                'socket_timeout': 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if info and (info.get('_type') == 'playlist' or 'entries' in info or 'list=' in lower_full_url):
                app_instance.is_playlist = True
                entries = info.get('entries', [])
                app_instance.title = info.get("title", "Playlist")
                app_instance.playlist_entries = len(entries)
                app_instance.remaining_videos = app_instance.playlist_entries
                
                app_instance._safe_ui_update(
                    app_instance.lbl_file_name,
                    {"text": f"File Name: {app_instance.title}", "text_color": "#cbd5e1"}
                )
                app_instance._safe_ui_update(
                    app_instance.lbl_mode_title,
                    {"text": "Download Mode: Playlist", "text_color": "#64748b"}
                )
                if app_instance.is_playlist and find_download_by_name(app_instance.title):
                    data = get_download_by_id(app_instance.download_id)
                    num_video = data.get("num_video", app_instance.playlist_entries) if data else app_instance.playlist_entries
                    app_instance.playlist_entries = num_video
                    update_download_data(app_instance.download_id, num_video=app_instance.playlist_entries)
                else:
                    update_download_data(app_instance.download_id, num_video=app_instance.playlist_entries)

                app_instance._safe_ui_update(
                    app_instance.lbl_num_video,
                    {"text": f"Remaining: {app_instance.playlist_entries} video", "text_color": "#10b981"}
                )
            return True, info

        # إذا لم يكن رابط فيديو أو بلايليست، يتم فحص نوع المحتوى عادي
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=3, stream=True)
            content_type = response.headers.get('Content-Type', '').lower()
            response.close()

            is_direct_media_or_file = (
                ('application/' in content_type or 'audio/' in content_type or 'video/' in content_type)
                and 'text/html' not in content_type
            )
            if is_direct_media_or_file:
                return False, None

        except Exception as e:
            print(f"HEAD/GET stream error: {e}")

        return False, None

    except Exception as e:
        print(f"Error analyzing URL: {e}")
        return False, None


def _update_url_information(url, app_instance):
    app_instance.ent_url.configure(state="disabled", fg_color="#181825")

    app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Analyzing URL rapidly...", "text_color": "#a855f7"})

    is_video, info = _analyze_url(url, app_instance)
    app_instance.current_url = url

    if is_video and info:
        app_instance.video_info = info
        app_instance.quality_map.clear()
        qualities = []

        if info.get('_type') == 'playlist' or 'entries' in info:
            app_instance.is_playlist = True
            flat_entries = [e for e in info.get('entries', []) if e]
            
            app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"Videos: {len(flat_entries)}", "text_color": "#94a3b8"})
            app_instance._safe_ui_update(app_instance.btn_download, {"state": "normal"})

            # === الجزء المضاف إظهار الجودات والصوت فوراً لقوائم التشغيل ===
            playlist_qualities = ["Best Quality", "1080p", "720p", "480p", "360p", "Audio Only (MP3)"]
            for q in playlist_qualities:
                app_instance.quality_map[q] = {
                    "format_id": "bestaudio[ext=mp3]/bestaudio" if q == "Audio Only (MP3)" else "bestvideo+bestaudio/best",
                    "is_playlist_preset": True,
                    "estimated_size_mb": 0.0,
                    "is_audio_only": (q == "Audio Only (MP3)")
                }

            app_instance.root.after(0, lambda: app_instance.cmb_quality.configure(values=playlist_qualities))
            user_quality = app_instance.user_settings.get("default_quality", "Best Quality")
            app_instance.root.after(0, lambda: app_instance.cmb_quality.set(user_quality))
            app_instance.root.after(0, lambda: app_instance.quality_frame.grid(row=6, column=1, padx=20, pady=2, sticky="w"))
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Playlist analyzed successfully", "text_color": "#10b981"})
            # ==========================================================

            def on_deep_analyze_click():
                app_instance._safe_ui_update(app_instance.btn_download, {"state": "disabled"})
                app_instance._safe_ui_update(app_instance.btn_analyze_playlist, {"state": "disabled", "text": "Checking sizes..."})
                app_instance._safe_ui_update(app_instance.lbl_size, {"text": "Calculating sizes for qualities...", "text_color": "#38bdf8"})
                threading.Thread(target=_deep_playlist_analyze, args=(app_instance, flat_entries), daemon=True).start()

            if not hasattr(app_instance, 'btn_analyze_playlist'):
                import customtkinter as ctk
                font_bold = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
                app_instance.btn_analyze_playlist = ctk.CTkButton(
                    app_instance.root, 
                    text="Analyze Sizes",
                    width=100,
                    height=36,
                    corner_radius=8,
                    font=font_bold,
                    command=on_deep_analyze_click,
                    fg_color="#2b2d42",
                    hover_color="#3d405b",
                    text_color="#ffffff"
                )
            
            app_instance.root.after(0, lambda: app_instance.btn_analyze_playlist.configure(
                state="normal", 
                text="Analyze Sizes", 
                fg_color="#2b2d42", 
                hover_color="#3d405b", 
                text_color="#ffffff", 
                command=on_deep_analyze_click
            ))

            app_instance.root.after(0, lambda: app_instance.btn_analyze_playlist.pack(side="left", padx=4))

        else:
            app_instance.is_playlist = False
            app_instance._safe_ui_update(app_instance.lbl_mode_title, {"text": "Download Mode: Single Video", "text_color": "#64748b"})
            app_instance._safe_ui_update(app_instance.lbl_num_video, {"text": ""})
            
            best_audio_size = 0
            audio_formats = [f for f in info.get("formats", []) if f.get("vcodec") == "none" and f.get("acodec") != "none"]
            if audio_formats:
                best_audio = max(audio_formats, key=lambda f: f.get("abr") or f.get("filesize") or 0)
                best_audio_size = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0

            for fmt in info.get("formats", []):
                if fmt.get("vcodec") == "none": 
                    continue

                height = fmt.get("height")
                if not height:
                    continue

                ext = fmt.get("ext", "").upper()
                fps = fmt.get("fps")
                video_size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
                
                if fmt.get("acodec") != "none":
                    combined_size = video_size
                else:
                    combined_size = video_size + best_audio_size if video_size > 0 else 0

                label = f"{height}p"
                if fps:
                    label += f" • {ext} • {int(fps)} FPS"
                else:
                    label += f" • {ext}"

                if combined_size > 0:
                    label += f" • {combined_size/(1024*1024):.1f} MB"

                format_id = fmt.get("format_id")
                if label not in app_instance.quality_map and format_id:
                    app_instance.quality_map[label] = {
                        "format_id": format_id,
                        "filesize": video_size,
                        "combined_size": combined_size,
                        "audio_size": best_audio_size,
                        "ext": fmt.get("ext"),
                        "height": height
                    }
                    qualities.append(label)

            if best_audio_size > 0:
                audio_label = f"Audio Only (MP3) • {best_audio_size / (1024 * 1024):.1f} MB"
                if audio_label not in app_instance.quality_map:
                    app_instance.quality_map[audio_label] = {
                        "format_id": "bestaudio[ext=mp3]/bestaudio",
                        "filesize": best_audio_size,
                        "combined_size": best_audio_size,
                        "audio_size": best_audio_size,
                        "ext": "MP3",
                        "height": 0,
                        "is_audio_only": True,
                    }
                    qualities.append(audio_label)

            qualities = sorted(
                qualities,
                key=lambda q: int(re.findall(r'\d+', q)[0]) if re.findall(r'\d+', q) else 0,
                reverse=True
            )
            if "Best Quality" not in qualities:
                qualities.insert(0, "Best Quality")
            app_instance.root.after(0, lambda: app_instance.cmb_quality.configure(values=qualities))
            
            user_quality = app_instance.user_settings.get("default_quality", "Best Quality")
            app_instance.root.after(0, lambda: app_instance.cmb_quality.set(user_quality))

            app_instance.title = info.get("title", "--")
            duration = info.get("duration")
            if duration:
                minutes = duration // 60
                seconds = duration % 60
                app_instance._safe_ui_update(app_instance.lbl_ETA, {"text": f"Duration: {minutes}:{seconds:02d}", "text_color": "#94a3b8"})

            max_display_length = 35
            if len(app_instance.title) > max_display_length:
                name_part, ext_part = os.path.splitext(app_instance.title)
                allowed_name_len = max_display_length - len(ext_part) - 3
                display_filename = name_part[:allowed_name_len] + "..."
            else:
                display_filename = app_instance.title

            app_instance._safe_ui_update(app_instance.lbl_file_name, {"text": f"File Name: {display_filename}", "text_color": "#cbd5e1"})
            app_instance.root.after(0, lambda: app_instance.quality_frame.grid(row=6, column=1, padx=20, pady=2, sticky="w"))
            app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Link analyzed successfully", "text_color": "#10b981"})
            app_instance._safe_ui_update(app_instance.btn_download, {"state": "normal"})

    else:
        app_instance.video_info = None
        app_instance.is_playlist = False
        app_instance.root.after(0, app_instance.quality_frame.grid_remove)
        _fetch_file_size(app_instance, url)

def _deep_playlist_analyze(app_instance, flat_entries):
    qualities = ["Best Quality", "1080p", "720p", "480p", "360p", "Audio Only (MP3)"]
    total_entries = len(flat_entries)
    processed_entries = 0
    counter_lock = threading.Lock()

    app_instance._safe_ui_update(
        app_instance.lbl_status,
        {"text": f"Scanning playlist videos: 0/{total_entries}", "text_color": "#38bdf8"}
    )

    def _build_playlist_format_selector(target_quality):
        general_quality_map = {
            "Best Quality": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "Audio Only (MP3)": "bestaudio[ext=mp3]/bestaudio",
            "Audio Only (m4a)": "bestaudio[ext=m4a]/bestaudio",
        }
        if target_quality in general_quality_map:
            return general_quality_map[target_quality]

        height_match = re.findall(r'\d+p', target_quality)
        if height_match:
            h = height_match[0].replace('p', '')
            return f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    def _estimate_size_from_info(info_dict):
        if not info_dict:
            return 0.0

        requested_formats = info_dict.get("requested_formats") or []
        if requested_formats:
            total_size = 0
            for fmt in requested_formats:
                size_value = fmt.get("filesize") or fmt.get("filesize_approx") or 0
                if size_value:
                    total_size += size_value
            if total_size > 0:
                return total_size / (1024 * 1024)

        formats_list = info_dict.get("formats", [])
        if not formats_list:
            return 0.0

        audio_formats = [f for f in formats_list if f.get("vcodec") == "none" and f.get("acodec") != "none"]
        best_audio_size_mb = 0.0
        if audio_formats:
            max_audio_size = max([(f.get("filesize") or f.get("filesize_approx") or 0) for f in audio_formats])
            best_audio_size_mb = max_audio_size / (1024 * 1024)

        video_formats = [f for f in formats_list if f.get("vcodec") != "none"]
        if not video_formats:
            return best_audio_size_mb

        best_stream_size = 0.0
        for fmt in video_formats:
            f_size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
            if f_size <= 0:
                continue

            size_mb = f_size / (1024 * 1024)
            if fmt.get("acodec") == "none":
                size_mb += best_audio_size_mb

            if size_mb > best_stream_size:
                best_stream_size = size_mb

        return best_stream_size

    for q in qualities:
        if q not in app_instance.quality_map:
            app_instance.quality_map[q] = {
                "format_id": "bestaudio[ext=mp3]/bestaudio" if q == "Audio Only (MP3)" else "bestvideo+bestaudio/best",
                "is_playlist_preset": True,
                "estimated_size_mb": 0.0,
                "is_audio_only": (q == "Audio Only (MP3)")
            }

    def update_playlist_quality_labels():
        labels = []
        for q in qualities:
            size_mb = app_instance.quality_map[q].get("estimated_size_mb", 0.0)
            if size_mb > 0:
                if size_mb > 1024:
                    labels.append(f"{q} ({(size_mb / 1024):.2f} GB)")
                else:
                    labels.append(f"{q} ({size_mb:.1f} MB)")
            else:
                labels.append(q)
        app_instance.root.after(0, lambda: app_instance.cmb_quality.configure(values=labels))

    def fetch_single_entry_size(entry):
        nonlocal processed_entries
        try:
            video_url = entry.get("url") or entry.get("id")
            if not video_url:
                return
            if not video_url.startswith("http"):
                video_url = f"https://www.youtube.com/watch?v={video_url}"

            for quality in qualities:
                format_selector = _build_playlist_format_selector(quality)
                ydl_opts_sub = {
                    "quiet": True,
                    "skip_download": True,
                    "nocheckcertificate": True,
                    "no_warnings": False,
                    "format": format_selector,
                }
                with yt_dlp.YoutubeDL(ydl_opts_sub) as ydl_sub:
                    sub_info = ydl_sub.extract_info(video_url, download=False)

                estimated_mb = _estimate_size_from_info(sub_info)
                if estimated_mb > 0:
                    app_instance.quality_map[quality]["estimated_size_mb"] += estimated_mb

            with counter_lock:
                processed_entries += 1
                done_count = processed_entries

            app_instance.root.after(0, lambda: app_instance._safe_ui_update(
                app_instance.lbl_status,
                {"text": f"Scanning playlist videos: {done_count}/{total_entries}", "text_color": "#38bdf8"}
            ))
            update_playlist_quality_labels()
        except Exception:
            with counter_lock:
                processed_entries += 1
                done_count = processed_entries
            app_instance.root.after(0, lambda: app_instance._safe_ui_update(
                app_instance.lbl_status,
                {"text": f"Scanning playlist videos: {done_count}/{total_entries}", "text_color": "#38bdf8"}
            ))
            pass

    def calculate_total_size_async():
        with ThreadPoolExecutor(max_workers=min(15, max(1, len(flat_entries)))) as executor:
            executor.map(fetch_single_entry_size, flat_entries)

        for q in qualities:
            app_instance.quality_map[q]["estimated_size_mb"] = round(app_instance.quality_map[q].get("estimated_size_mb", 0.0), 1)

        update_playlist_quality_labels()

        total_mb = app_instance.quality_map["Best Quality"]["estimated_size_mb"]
        if total_mb > 1024:
            size_text = f"Total Size (Best): {(total_mb / 1024):.2f} GB"
            update_download_data(app_instance.download_id, size=f"{(total_mb / 1024):.2f} GB")
        else:
            size_text = f"Total Size (Best): {total_mb:.2f} MB"
            update_download_data(app_instance.download_id, size=f"{total_mb:.2f} MB")

        if total_mb > 0:
            app_instance._safe_ui_update(app_instance.lbl_size, {"text": size_text, "text_color": "#10b981"})
        else:
            app_instance._safe_ui_update(app_instance.lbl_size, {"text": "Size: Unknown", "text_color": "#f59e0b"})

        app_instance._safe_ui_update(app_instance.lbl_status, {"text": "Link analyzed successfully", "text_color": "#10b981"})
        app_instance._safe_ui_update(app_instance.btn_analyze_playlist, {"state": "disabled", "text": "Complete!"})
        app_instance._safe_ui_update(app_instance.btn_download, {"state": "normal"})

    app_instance.user_quality = app_instance.user_settings.get("default_quality", "Best Quality")
    app_instance.root.after(0, lambda: app_instance.cmb_quality.set(app_instance.user_quality))

    app_instance.root.after(0, lambda: app_instance.quality_frame.grid(row=6, column=1, padx=20, pady=2, sticky="w"))
    app_instance._safe_ui_update(app_instance.lbl_file_name, {"text": f"File Name: {app_instance.title}", "text_color": "#cbd5e1"})

    threading.Thread(target=calculate_total_size_async, daemon=True).start()