import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import json
import struct
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.core.analyze_engine import _update_url_information
from src.core.download_engine import _core_download_engine
from src.managers.history_manager import update_download_data
from src.managers.settings_manager import load_settings, save_settings
from src.managers.shortcuts import handle_global_shortcuts

# Set modern appearance mode and default color palette
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

NO_CONSOLE_FLAG = (
    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
)

def handle_browser_launch():
  """قراءة الرابط من المتصفح مباشرة عند تشغيل main.exe كـ Native Messaging Host."""
  if len(sys.argv) > 1 and sys.argv[1].startswith(("chrome-extension://", "moz-extension://")):
    try:
      raw_length = sys.stdin.buffer.read(4)
      if not raw_length or len(raw_length) < 4:
        sys.exit(0)

      msg_len = struct.unpack("I", raw_length)[0]
      msg = json.loads(sys.stdin.buffer.read(msg_len).decode("utf-8"))

      url = str(msg.get("url", "")).strip()
      if url.startswith("{") and "url" in url:
        url = json.loads(url).get("url", url).strip()
      if url.startswith("mydl://"):
        url = url.replace("mydl://", "https://")

      # إرسال رد فوري للمتصفح وإغلاق قناة stdin/stdout حتى لا ينتظر المتصفح إغلاق النافذة
      reply = json.dumps({"status": "success", "message": "Launched main"}).encode("utf-8")
      sys.stdout.buffer.write(struct.pack("I", len(reply)))
      sys.stdout.buffer.write(reply)
      sys.stdout.buffer.flush()
      sys.stdout.close()
      sys.stdin.close()

      if not url:
        sys.exit(0)

      # توليد ID جديد بناءً على سجل التحميلات
      appdata_dir = os.path.join(
          os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "DM_Temp"
      )
      json_file = os.path.join(appdata_dir, "downloads_history.json")
      max_id = 0
      if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
          max_id = max((int(item.get("id", 0)) for item in (json.load(f) or [])), default=0)

      return url, max_id + 1
    except Exception:
      sys.exit(0)

  # التشغيل العادي من الواجهة الرئيسية (Download Manager.exe)
  passed_url = sys.argv[1] if len(sys.argv) > 1 else ""
  try:
    passed_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
  except ValueError:
    passed_id = None
  return passed_url, passed_id

class PythonAutoDownloadManagerGUI:

  def __init__(self, root, initial_url="", initial_id=None):
    self.root = root
    self.root.title("Download")
    self.root.geometry("860x365")
    self.root.resizable(False, False)
    self.root.configure(fg_color="#121212")

    self.final_save_path = None
    self.is_downloading = False
    self.is_paused = False
    self.is_cancelled = False
    self.btn_paused = None
    self.is_video_url = False
    self.video_info = None
    self.current_url = ""
    self.last_clipboard = ""
    self.video_formats = []
    self.quality_map = {}
    self.download_id = None
    self.remaining_videos = 0

    self.user_settings = load_settings()
    self.DEFAULT_THREADS = int(self.user_settings.get("num_threads", 8))
    self.default_downloads_dir = self.user_settings.get(
        "download_dir", os.path.expanduser("~")
    )

    self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    if getattr(sys, "frozen", False):
      self.current_dir = os.path.dirname(os.path.abspath(sys.executable))
      bundle_dir = getattr(sys, "_MEIPASS", self.current_dir)
    else:
      self.current_dir = os.path.dirname(os.path.abspath(__file__))
      bundle_dir = self.current_dir

    self.icon_path = os.path.join(bundle_dir, "assets", "icon", "icon.ico")
    if os.path.exists(self.icon_path):
      self.root.iconbitmap(self.icon_path)

    self.lock = threading.Lock()

    self._create_widgets()
    try:
      self.last_clipboard = self.root.clipboard_get().strip()
    except tk.TclError:
      self.last_clipboard = ""

    self.launch_main_manager_in_background()
    self.check_and_update_ytdlp()
    self.url_var.trace_add("write", self._on_url_change)

    if initial_url:
      self.url_var.set(initial_url)
      self.last_clipboard = initial_url

    self.download_id = initial_id
    self.root.after(500, self._auto_capture_url)

  def check_and_update_ytdlp(self):
    def _update():
      try:
        subprocess.run(
            ["uv", "pip", "install", "--upgrade", "yt-dlp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            creationflags=NO_CONSOLE_FLAG,
        )
      except Exception:
        pass

    update_thread = threading.Thread(target=_update, daemon=True)
    update_thread.start()

  def launch_main_manager_in_background(self):
    def worker():
      try:
        main_manager_exe = os.path.join(
            self.current_dir, "Download Manager.exe"
        )
        main_manager_py = os.path.join(self.current_dir, "Download Manager.py")

        if sys.platform == "win32":
          ps_cmd = (
              'powershell -NoProfile -Command "Get-Process | Where-Object'
              " {$_.Name -eq 'Download Manager' -or $_.CommandLine -like"
              " '*Download Manager.py*'} | Select-Object -ExpandProperty Name\""
          )
          try:
            output = subprocess.check_output(
                ps_cmd, stderr=subprocess.DEVNULL, creationflags=NO_CONSOLE_FLAG
            ).decode("utf-8", errors="ignore")
            if "Download Manager" in output:
              return
          except Exception:
            pass

        if os.path.exists(main_manager_exe):
          subprocess.Popen(
              [main_manager_exe, "--background"],
              creationflags=(
                  subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                  if sys.platform == "win32"
                  else 0
              ),
          )
        elif os.path.exists(main_manager_py):
          executable = sys.executable
          if executable.endswith("python.exe"):
            executable = executable.replace("python.exe", "pythonw.exe")

          subprocess.Popen(
              [executable, main_manager_py, "--background"],
              creationflags=(
                  subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                  if sys.platform == "win32"
                  else 0
              ),
          )
      except Exception:
        pass

    threading.Thread(target=worker, daemon=True).start()

  def _create_widgets(self):
    # Unified typography system
    font_bold = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
    font_regular = ctk.CTkFont(family="Segoe UI", size=12)
    font_small = ctk.CTkFont(family="Segoe UI", size=11)

    # --- URL Input Section ---
    lbl_url = ctk.CTkLabel(
        self.root,
        text="URL Address:",
        font=font_bold,
        text_color="#f1f5f9",
    )
    lbl_url.grid(row=0, column=0, padx=(20, 10), pady=(18, 8), sticky="w")

    self.url_var = tk.StringVar()
    self.ent_url = ctk.CTkEntry(
        self.root,
        textvariable=self.url_var,
        width=630,
        height=36,
        font=font_regular,
        fg_color="#1e1e2e",
        text_color="#ffffff",
        border_color="#313244",
        border_width=1,
        corner_radius=8,
        placeholder_text="Paste your download URL here...",
    )
    self.ent_url.grid(
        row=0, column=0, padx=(120, 20), pady=(18, 8), columnspan=2, sticky="ew"
    )

    self.ent_url.bind(
        "<Key>", lambda event: handle_global_shortcuts(event, self)
    )

    def _change_default_path():
      chosen_dir = filedialog.askdirectory(
          initialdir=self.default_downloads_dir,
          title="Select Default Save Folder",
      )
      if chosen_dir:
        self.default_downloads_dir = chosen_dir
        self.lbl_path.configure(
            text=f"Save Path: {chosen_dir}", text_color="#94a3b8"
        )
        save_settings(download_dir=chosen_dir)

    path_frame = ctk.CTkFrame(self.root, fg_color="transparent")
    path_frame.grid(
        row=1, column=0, padx=20, pady=(0, 6), sticky="w", columnspan=2
    )

    self.lbl_path = ctk.CTkLabel(
        path_frame,
        text=f"Save Path: {self.default_downloads_dir}",
        font=font_regular,
        text_color="#94a3b8",
    )
    self.lbl_path.pack(side="left", padx=(0, 10))

    self.btn_browse = ctk.CTkButton(
        path_frame,
        text="📂 Browse",
        fg_color="#2b2d42",
        hover_color="#3d405b",
        text_color="#f1f5f9",
        font=font_regular,
        width=80,
        height=26,
        corner_radius=6,
        command=_change_default_path,
    )
    self.btn_browse.pack(side="left")

    self.lbl_mode_title = ctk.CTkLabel(
        self.root,
        text="Download Mode: Unknown",
        font=font_regular,
        text_color="#64748b",
    )
    self.lbl_mode_title.grid(row=1, column=1, padx=20, pady=0, sticky="w")

    self.lbl_num_video = ctk.CTkLabel(
        self.root,
        text="",
        font=font_regular,
        text_color="#64748b",
    )
    self.lbl_num_video.grid(row=2, column=1, padx=20, pady=0, sticky="w")

    self.lbl_file_name = ctk.CTkLabel(
        self.root,
        text="File Name: --",
        font=font_regular,
        text_color="#cbd5e1",
    )
    self.lbl_file_name.grid(
        row=2, column=0, padx=20, pady=2, sticky="w", columnspan=2
    )

    self.lbl_ETA = ctk.CTkLabel(
        self.root, text="ETA: --", font=font_regular, text_color="#94a3b8"
    )
    self.lbl_ETA.grid(
        row=3, column=0, padx=20, pady=2, sticky="w", columnspan=2
    )

    self.lbl_size = ctk.CTkLabel(
        self.root,
        text="Size: --",
        font=font_regular,
        text_color="#94a3b8",
    )
    self.lbl_size.grid(
        row=4, column=0, padx=20, pady=2, sticky="w", columnspan=2
    )

    self.lbl_status = ctk.CTkLabel(
        self.root,
        text="Status: Ready",
        font=font_bold,
        text_color="#38bdf8",
    )
    self.lbl_status.grid(
        row=5, column=0, columnspan=2, padx=20, pady=(6, 2), sticky="w"
    )

    self.lbl_threads = ctk.CTkLabel(
        self.root,
        text="Connections allocated: --",
        font=font_bold,
        text_color="#94a3b8",
    )
    self.lbl_threads.grid(
        row=6, column=0, columnspan=2, padx=20, pady=2, sticky="w"
    )

    self.quality_frame = ctk.CTkFrame(self.root, fg_color="transparent")
    self.quality_frame.grid(
        row=6, column=1, padx=20, pady=2, sticky="w", columnspan=2
    )

    self.lbl_quality = ctk.CTkLabel(
        self.quality_frame,
        text="Video Quality:",
        font=font_bold,
        text_color="#f1f5f9",
    )
    self.lbl_quality.pack(side="left", padx=(0, 10))

    self.quality_var = tk.StringVar(value="Best Quality")
    self.cmb_quality = ctk.CTkOptionMenu(
        self.quality_frame,
        variable=self.quality_var,
        values=["Best Quality", "1080p", "720p", "480p"],
        width=150,
        height=30,
        fg_color="#1e1e2e",
        button_color="#3b82f6",
        button_hover_color="#2563eb",
        dropdown_fg_color="#181825",
        dropdown_hover_color="#313244",
        font=font_regular,
        command=self._quality_changed,
    )
    self.cmb_quality.pack(side="left")
    self.quality_frame.grid_remove()

    # --- Progress Section ---
    self.progress = ctk.CTkProgressBar(
        self.root,
        orientation="horizontal",
        width=820,
        height=14,
        progress_color="#3b82f6",
        fg_color="#1e1e2e",
        corner_radius=7,
        border_width=0,
    )
    self.progress.grid(
        row=7, column=0, columnspan=2, padx=20, pady=(16, 4), sticky="we"
    )
    self.progress.set(0.0)

    self.lbl_percentage = ctk.CTkLabel(
        self.root, text="0%", font=font_bold, text_color="#38bdf8"
    )
    self.lbl_percentage.grid(
        row=6, column=1, padx=20, pady=(6, 0), sticky="e"
    )

    # --- Action Control Bar ---
    self.button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
    self.button_frame.grid(
        row=9, column=0, columnspan=2, padx=20, pady=(12, 16), sticky="ew"
    )
    self.button_frame.grid_columnconfigure(0, weight=1)

    self.btn_open_folder = ctk.CTkButton(
        self.button_frame,
        text="Open Folder",
        fg_color="#10b981",
        hover_color="#059669",
        text_color="#ffffff",
        font=font_bold,
        height=36,
        corner_radius=8,
        state="disabled",
        command=self._open_download_folder,
    )
    self.btn_open_folder.pack(side="left", padx=(0, 8))

    self.btn_analyze_playlist = ctk.CTkButton(
        self.button_frame,
        text="Analyze",
        fg_color="#2b2d42",
        hover_color="#3d405b",
        text_color="#ffffff",
        font=font_bold,
        height=36,
        corner_radius=8,
        state="disabled",
    )
    self.btn_analyze_playlist.pack(side="left", padx=4)

    self.btn_cancel = ctk.CTkButton(
        self.button_frame,
        text="Cancel",
        fg_color="#ef4444",
        hover_color="#dc2626",
        text_color="#ffffff",
        font=font_bold,
        height=36,
        corner_radius=8,
        command=self._cancel_download,
    )
    self.btn_cancel.pack(side="right", padx=(8, 0))

    self.btn_pause = ctk.CTkButton(
        self.button_frame,
        text="Pause",
        fg_color="#f59e0b",
        hover_color="#d97706",
        text_color="#ffffff",
        font=font_bold,
        height=36,
        corner_radius=8,
        state="disabled",
        command=self._toggle_pause,
    )
    self.btn_pause.pack(side="right", padx=4)

    self.btn_download = ctk.CTkButton(
        self.button_frame,
        text="Start Download",
        fg_color="#3b82f6",
        hover_color="#2563eb",
        text_color="#ffffff",
        font=font_bold,
        height=36,
        corner_radius=8,
        command=self._start_download_thread,
    )
    self.btn_download.pack(side="right", padx=4)

    self.root.grid_columnconfigure(1, weight=1)
    self.root.grid_columnconfigure(0, weight=1)

  def _on_url_change(self, *args):
    if hasattr(self, "_url_job"):
      self.root.after_cancel(self._url_job)
    self._url_job = self.root.after(700, self._analyze_current_url)

  def _analyze_current_url(self):
    url = self.url_var.get().strip()
    if not url.startswith(("http://", "https://")):
      return

    threading.Thread(
        target=_update_url_information, args=(url, self), daemon=True
    ).start()

  def _quality_changed(self, selected):
    if selected in ["Best Quality"]:
      return

    fmt = self.quality_map.get(selected)
    if fmt and isinstance(fmt, dict):
      size = (
          fmt.get("combined_size")
          or fmt.get("filesize")
          or fmt.get("filesize_approx")
          or 0
      )
      if size:
        self._safe_ui_update(
            self.lbl_size, {"text": f"Size: {size/(1024*1024):.2f} MB"}
        )

  def _auto_capture_url(self):
    try:
      current_entry_text = self.url_var.get().strip()
      text = self.root.clipboard_get().strip()

      if (
          text != self.last_clipboard
          and text.startswith(("http://", "https://"))
          and not current_entry_text.startswith(("http://", "https://"))
      ):
        self.last_clipboard = text
        self.url_var.set(text)
    except tk.TclError:
      pass

    self.root.after(500, self._auto_capture_url)

  def _start_download_thread(self):
    if self.is_downloading:
      messagebox.showwarning("In Progress", "A download is already running!")
      return

    self.ent_url.configure(state="disabled")
    url = self.ent_url.get().strip()
    if not url:
      messagebox.showerror("Error", "Please enter a valid URL.")
      return

    self.is_downloading = True
    selected_quality = self.cmb_quality.get()
    quality_info = self.quality_map.get(selected_quality, {})
    self.total_combined_size = quality_info.get("combined_size", 0)
    self.video_only_size = quality_info.get("filesize", 0)

    self.is_paused = False
    self.is_cancelled = False
    self.btn_download.configure(state="disabled")
    self.root.after(
        0,
        lambda: self.btn_pause.configure(
            state="normal", text="Pause", fg_color="#f59e0b"
        ),
    )
    self.progress.set(0.0)
    self._safe_ui_update(self.lbl_percentage, {"text": "0%"})

    downloader_thread = threading.Thread(
        target=_core_download_engine,
        args=(self, url, selected_quality),
        daemon=True,
    )
    downloader_thread.start()

  def _toggle_pause(self):
    if not self.is_downloading:
      return

    self.is_paused = not self.is_paused
    if self.is_paused:
      self.root.after(
          0,
          lambda: self.btn_pause.configure(text="Resume", fg_color="#3b82f6"),
      )
      self._safe_ui_update(
          self.lbl_status, {"text": "Status: Paused", "text_color": "#f59e0b"}
      )
      update_download_data(self.download_id, status="Paused")
      update_download_data(self.download_id, speed="0 KB/s")
    else:
      update_download_data(self.download_id, status="Downloading")
      self.root.after(
          0, lambda: self.btn_pause.configure(text="Pause", fg_color="#f59e0b")
      )
      self._safe_ui_update(
          self.lbl_status, {"text": "Downloading...", "text_color": "#10b981"}
      )

  def _cancel_download(self):
    if not self.is_downloading:
      return

    self._toggle_pause()
    self._safe_ui_update(
        self.lbl_status,
        {"text": "Status: Confirming Cancel...", "text_color": "#ef4444"},
    )

    if messagebox.askokcancel(
        "Cancel Download",
        "There is an active download. Do you want to terminate it?",
    ):
      self.is_cancelled = True
      self.is_downloading = False
      self.is_paused = False
      self._reset_ui()
      self._on_closing()
    else:
      self.is_cancelled = False
      self.is_paused = True
      self._safe_ui_update(
          self.lbl_status,
          {
              "text": "⏸️ Download Paused - Click Resume to continue",
              "text_color": "#f59e0b",
          },
      )
      self.root.after(
          0,
          lambda: self.btn_pause.configure(
              state="normal", text="Resume", fg_color="#3b82f6"
          ),
      )
      update_download_data(self.download_id, status="Paused")

  def _open_download_folder(self):
    target_dir = self.default_downloads_dir
    if self.final_save_path:
        if os.path.isdir(self.final_save_path):
            target_dir = self.final_save_path
        elif os.path.exists(self.final_save_path):
            target_dir = os.path.dirname(self.final_save_path)

    if os.path.exists(target_dir):
        if sys.platform == "win32":
            os.startfile(target_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target_dir])
        else:
            subprocess.Popen(["xdg-open", target_dir])

  def _safe_ui_update(self, widget, property_dict):
    self.root.after(0, lambda: widget.configure(**property_dict))

  def _safe_progress_update(self, value):
    self.root.after(0, lambda: self.progress.set(value / 100.0))
    self.root.after(
        0, lambda: self.lbl_percentage.configure(text=f"{int(value)}%")
    )
    update_download_data(self.download_id, progress=f"{int(value)}%")

  def _on_closing(self):
    if self.is_downloading:
      if messagebox.askokcancel(
          "Quit",
          "There is an active download. Quitting will cancel the download. Do"
          " you want to quit?",
      ):
        self._reset_ui()
        self._safe_ui_update(
            self.lbl_status,
            {"text": "⏳ Cleaning up and closing...", "text_color": "#ef4444"},
        )
        update_download_data(self.download_id, status="Paused", speed="0 KB/s")

        def wait_and_destroy():
          time.sleep(0.5)
          self.root.after(0, self.root.destroy)

        threading.Thread(target=wait_and_destroy, daemon=True).start()
    else:
      update_download_data(self.download_id, status="Paused", speed="0 KB/s")
      self.root.destroy()

  def _reset_ui(self):
    self.is_downloading = False
    self.is_paused = False

    self.root.after(
        0,
        lambda: self.btn_download.configure(
            state="normal", fg_color="#3b82f6"
        ),
    )
    self.root.after(
        0,
        lambda: self.btn_pause.configure(
            state="disabled",
            text="Pause",
            fg_color="#f59e0b",
            hover_color="#d97706",
        ),
    )
    self.root.after(
        0, lambda: self.btn_open_folder.configure(state="disabled")
    )
    self.root.after(0, lambda: self.ent_url.configure(state="normal"))

    self._safe_ui_update(
        self.lbl_threads, {"text": "Connections allocated: --"}
    )
    self._safe_ui_update(self.lbl_status, {"text": "Status: Ready"})
    self._safe_ui_update(self.lbl_size, {"text": "Size: --"})
    self._safe_ui_update(self.lbl_file_name, {"text": "File Name: --"})
    self._safe_ui_update(self.lbl_mode_title, {"text": "Download Mode: --"})

    self._safe_ui_update(self.lbl_ETA, {"text": "ETA: --"})
    self._safe_ui_update(self.lbl_percentage, {"text": "0%"})
    update_download_data(self.download_id, time_left="--")

    if self.final_save_path or os.path.exists(self.default_downloads_dir):
        self.root.after(0, lambda: self.btn_open_folder.configure(state="normal"))
    else:
        self.root.after(0, lambda: self.btn_open_folder.configure(state="disabled"))

    self.root.after(0, lambda: self.ent_url.configure(state="normal"))


if __name__ == "__main__":
  target_url, download_id = handle_browser_launch()

  try:
    single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    unique_port = 49152 + (int(download_id or 1) % 16383)
    single_instance_socket.bind(("127.0.0.1", unique_port))
  except (socket.error, ValueError):
    sys.exit(0)

  window = ctk.CTk()
  app = PythonAutoDownloadManagerGUI(
      window, initial_url=target_url, initial_id=download_id
  )
  window.mainloop()