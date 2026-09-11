import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import winreg

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from PyQt6.QtCore import QPoint, Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)
import requests


class PropertiesDialog(QDialog):
  """Dialog window to display file details (Double-click item)."""

  def __init__(self, info, parent=None):
    super().__init__(parent)
    self.info = info
    self.setWindowTitle("File Properties")
    self.setFixedSize(560, 500)
    self.setModal(True)
    self.init_ui()

  def init_ui(self):
    layout = QVBoxLayout(self)
    layout.setSpacing(12)

    top_layout = QHBoxLayout()
    icon_label = QLabel("📄")
    icon_label.setFont(QFont("Segoe UI", 32))
    top_layout.addWidget(icon_label)

    name_label = QLabel(self.info.get("name", "Unknown File"))
    name_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    name_label.setWordWrap(True)
    top_layout.addWidget(name_label, 1)
    layout.addLayout(top_layout)

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    layout.addWidget(line)

    ext = (
        os.path.splitext(self.info.get("name", ""))[1].upper().replace(".", "")
    )
    file_type = f"{ext} File" if ext else "Unknown File Type"

    self.add_row(layout, "Type:", file_type)
    self.add_row(
        layout,
        "Status:",
        f"{self.info.get('progress', '0%')} ({self.info.get('status', 'unknown')})",
    )
    self.add_row(layout, "Size:", self.info.get("size", "Unknown Size"))

    default_path = os.path.join(
        os.path.expanduser("~"), "Downloads", self.info.get("name", "")
    )
    self.add_row(layout, "Save To:", default_path, is_entry=True)
    self.add_row(
        layout,
        "Address:",
        self.info.get("url", "Unknown URL"),
        is_entry=True,
    )
    self.add_row(
        layout, "Description:", "No description available.", is_entry=True
    )

    lbl_web = QLabel("Source Web Page:")
    lbl_web.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    layout.addWidget(lbl_web)

    self.add_row(
        layout,
        "Referer:",
        self.info.get("url", "Unknown"),
        is_entry=True,
    )

    speed_details = f"Transfer Speed: {self.info.get('speed', '0 KB/s')} - Time Left: {self.info.get('time_left', 'Unknown')}"
    lbl_speed = QLabel(speed_details)
    lbl_speed.setStyleSheet("color: #888888;")
    layout.addWidget(lbl_speed)

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    open_btn = QPushButton("Open File")
    open_btn.setFixedSize(90, 32)
    open_btn.clicked.connect(self.open_file_action)
    btn_layout.addWidget(open_btn)

    ok_btn = QPushButton("OK")
    ok_btn.setFixedSize(90, 32)
    ok_btn.clicked.connect(self.accept)
    btn_layout.addWidget(ok_btn)

    layout.addLayout(btn_layout)

  def add_row(self, parent_layout, label_text, val_text, is_entry=False):
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(100)
    lbl.setStyleSheet("color: #a0a0a0;")
    row.addWidget(lbl)

    if is_entry:
      entry = QLineEdit(val_text)
      entry.setReadOnly(True)
      row.addWidget(entry)
    else:
      val = QLabel(val_text)
      row.addWidget(val)

    parent_layout.addLayout(row)

  def open_file_action(self):
    if self.info.get("status", "").lower() == "✅ complete":
      QMessageBox.information(
          self, "Open File", "Opening selected file..."
      )
    else:
      QMessageBox.warning(
          self,
          "Warning",
          "Cannot open file until the download is complete.",
      )


class SettingsDialog(QDialog):
  """Dialog window for download settings."""

  def __init__(self, parent=None):
    super().__init__(parent)
    self.main_app = parent
    self.setWindowTitle("Preferences & Settings")
    self.setFixedSize(520, 380)
    self.setModal(True)
    self.init_ui()

  def init_ui(self):
    layout = QVBoxLayout(self)
    layout.setSpacing(15)

    lbl_title = QLabel("⚙️ Preferences")
    lbl_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    lbl_title.setStyleSheet("color: #1f538d;")
    layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

    # 1. Save Folder
    row1 = QHBoxLayout()
    row1.addWidget(QLabel("Download Directory:"))
    self.entry_dir = QLineEdit(
        self.main_app.settings.get("download_dir", "")
    )
    row1.addWidget(self.entry_dir)
    browse_btn = QPushButton("Browse")
    browse_btn.clicked.connect(self.browse_folder)
    row1.addWidget(browse_btn)
    layout.addLayout(row1)

    # 2. Connections
    row2 = QHBoxLayout()
    row2.addWidget(QLabel("Max Connections:"))
    self.cmb_threads = QComboBox()
    self.cmb_threads.addItems(["1", "4", "8", "16", "32"])
    self.cmb_threads.setCurrentText(
        str(self.main_app.settings.get("num_threads", "8"))
    )
    row2.addWidget(self.cmb_threads)
    row2.addStretch()
    layout.addLayout(row2)

    # 3. Quality
    row3 = QHBoxLayout()
    row3.addWidget(QLabel("Preferred Quality:"))
    self.cmb_quality = QComboBox()
    self.cmb_quality.addItems([
        "Best Quality",
        "1080p",
        "720p",
        "480p",
        "Audio Only (MP3)",
    ])
    self.cmb_quality.setCurrentText(
        self.main_app.settings.get("default_quality", "Best Quality")
    )
    row3.addWidget(self.cmb_quality)
    row3.addStretch()
    layout.addLayout(row3)

    # 4. Startup
    self.chk_startup = QCheckBox("Launch Download Manager on Windows startup")
    self.chk_startup.setChecked(
        self.main_app.settings.get("start_with_windows", False)
    )
    layout.addWidget(self.chk_startup)

    layout.addStretch()

    # Buttons
    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(self.reject)
    btn_layout.addWidget(cancel_btn)

    save_btn = QPushButton("Save Changes")
    save_btn.setStyleSheet(
        "background-color: #27ae60; color: white; font-weight: bold;"
    )
    save_btn.clicked.connect(self.save_action)
    btn_layout.addWidget(save_btn)

    layout.addLayout(btn_layout)

  def browse_folder(self):
    chosen_dir = QFileDialog.getExistingDirectory(
        self, "Select Directory", self.entry_dir.text()
    )
    if chosen_dir:
      self.entry_dir.setText(chosen_dir)

  def save_action(self):
    self.main_app.settings["download_dir"] = self.entry_dir.text()
    self.main_app.settings["num_threads"] = self.cmb_threads.currentText()
    self.main_app.settings["default_quality"] = (
        self.cmb_quality.currentText()
    )
    self.main_app.settings["start_with_windows"] = (
        self.chk_startup.isChecked()
    )

    self.main_app.save_settings()
    self.main_app.handle_windows_startup(self.chk_startup.isChecked())

    QMessageBox.information(self, "Saved", "Settings saved successfully.")
    self.accept()


class AddUrlDialog(QDialog):
  """Dialog window for pasting and submitting a new download URL."""

  def __init__(self, parent=None):
    super().__init__(parent)
    self.main_app = parent
    self.setWindowTitle("Add New Download")
    self.setFixedSize(500, 160)
    self.setModal(True)

    self.last_clipboard = ""
    self.init_ui()

  def init_ui(self):
    layout = QVBoxLayout(self)

    layout.addWidget(QLabel("Enter File URL / Address:"))

    self.url_entry = QLineEdit()
    self.url_entry.setFixedHeight(34)
    layout.addWidget(self.url_entry)

    # Auto paste clipboard content if it is a valid URL
    clipboard_text = QApplication.clipboard().text().strip()
    if clipboard_text.startswith(("http://", "https://")):
      self.url_entry.setText(clipboard_text)
      self.last_clipboard = clipboard_text

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    cancel_btn = QPushButton("Cancel")
    cancel_btn.setFixedSize(80, 32)
    cancel_btn.clicked.connect(self.reject)
    btn_layout.addWidget(cancel_btn)

    start_btn = QPushButton("Start Download")
    start_btn.setFixedSize(120, 32)
    start_btn.setStyleSheet(
        "background-color: #27ae60; color: white; font-weight: bold;"
    )
    start_btn.clicked.connect(self.confirm)
    btn_layout.addWidget(start_btn)

    layout.addLayout(btn_layout)

    self.timer = QTimer(self)
    self.timer.timeout.connect(self.auto_capture_url)
    self.timer.start(500)

  def auto_capture_url(self):
    text = QApplication.clipboard().text().strip()
    current = self.url_entry.text().strip()

    if (
        text
        and text != self.last_clipboard
        and text.startswith(("http://", "https://"))
        and not current.startswith(("http://", "https://"))
    ):
      self.last_clipboard = text
      self.url_entry.setText(text)

  def confirm(self):
    full_url = self.url_entry.text().strip()
    if not full_url:
      QMessageBox.warning(self, "Warning", "URL field cannot be empty.")
      return

    main_exe_path = os.path.join(self.main_app.current_dir, "main.exe")
    main_py = os.path.join(self.main_app.current_dir, "main.py")

    try:
      if os.path.exists(main_exe_path):
        subprocess.Popen(
            [main_exe_path, full_url],
            creationflags=(
                subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
            ),
        )
      else:
        subprocess.Popen([sys.executable, main_py, full_url])
    except Exception as e:
      QMessageBox.critical(
          self, "Error", f"Failed to start download process: {e}"
      )

    self.accept()


class UpdateCheckerThread(QThread):
    # إشارة نمرر من خلالها (الإصدار الجديد، رابط التحميل، مميزات التحديث)
    update_available = pyqtSignal(str, str, str)

    def __init__(self, current_version, version_url, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.version_url = version_url

    def run(self):
        time.sleep(1) # انتظر ثانية واحدة للتأكد من اكتمال رسم الواجهة
        try:
            response = requests.get(self.version_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = str(data.get("version", "")).strip()
                download_url = data.get("url", "")
                release_notes = data.get("description", "No release notes provided.")

                # طباعة للـ Debugging في الترمينال للتأكد من القراءة
                print(f"[UpdateCheck] Current: '{self.current_version}' | Latest on Server: '{latest_version}'")

                # التحقق من وجود إصدار جديد
                if latest_version and latest_version != self.current_version:
                    self.update_available.emit(latest_version, download_url, release_notes)
        except Exception as e:
            print(f"[UpdateCheck] Error: {e}")


class IDMRealTimeViewer(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowTitle("Modern Download Manager")
    self.resize(1100, 620)
    self.setMinimumSize(950, 500)

    if getattr(sys, "frozen", False):
      self.current_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
      self.current_dir = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(self.current_dir, "icon", "icon.ico")
    if os.path.exists(icon_path):
      self.setWindowIcon(QIcon(icon_path))

    appdata_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "DM_Temp"
    )
    if not os.path.exists(appdata_dir):
      os.makedirs(appdata_dir)

    self.json_file = os.path.join(appdata_dir, "downloads_history.json")
    if not os.path.exists(self.json_file):
      with open(self.json_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    self.settings_file = os.path.join(appdata_dir, "settings.json")
    self.load_settings()

    self.CURRENT_VERSION = "1.0.4"
    self.VERSION_URL = "https://raw.githubusercontent.com/Sudo-3D/download-manager/main/version.json"
    self.current_category = "All Downloads"

    self.setup_stylesheet()
    self.init_ui()
    self.create_tray_icon()

    self.load_data_from_json()

    # Real-time monitoring timer
    self.monitor_timer = QTimer(self)
    self.monitor_timer.timeout.connect(self.load_data_from_json)
    self.monitor_timer.start(500)

    self.start_update_thread()

  def closeEvent(self, event):
    """Minimize to system tray on exit button instead of killing app."""
    event.ignore()
    self.hide()

  def setup_stylesheet(self):
    """Sleek Dark Theme stylesheet."""
    self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121212;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QFrame#Toolbar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2d2d2d;
            }
            QPushButton {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3d3d3d;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QListWidget {
                background-color: #181818;
                border: 1px solid #2d2d2d;
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                height: 36px;
                padding-left: 10px;
                color: #c0c0c0;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QListWidget::item:selected {
                background-color: #1f538d;
                color: #ffffff;
            }
            QTableWidget {
                background-color: #181818;
                border: 1px solid #2d2d2d;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #1f538d;
                color: white;
            }
            QHeaderView::section {
                background-color: #242424;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-right: 1px solid #2d2d2d;
                border-bottom: 1px solid #2d2d2d;
            }
            QLineEdit, QComboBox {
                background-color: #242424;
                border: 1px solid #3d3d3d;
                color: white;
                border-radius: 4px;
                padding: 4px;
            }
            QScrollBar:vertical {
                background: #181818;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #3d3d3d;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #1f538d;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

  def init_ui(self):
    central_widget = QWidget()
    self.setCentralWidget(central_widget)
    main_layout = QVBoxLayout(central_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # 1. Top Toolbar
    toolbar = QFrame()
    toolbar.setObjectName("Toolbar")
    toolbar_layout = QHBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(10, 8, 10, 8)

    buttons = [
        ("➕ Add URL", self.add_download_url, "#27ae60", "#218c53"),
        ("▶️ Resume", self.resume_download, None, None),
        ("⏸️ Pause", self.pause_download, None, None),
        ("❌ Delete", self.delete_download, "#c0392b", "#962d22"),
        ("🛑 Stop All", self.stop_all_downloads, "#d35400", "#a04000"),
        ("⚙️ Settings", self.open_settings_window, None, None),
    ]

    for text, command, bg_color, _ in buttons:
      btn = QPushButton(text)
      if bg_color:
        btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg_color};
                        border: none;
                    }}
                """)
      btn.clicked.connect(command)
      toolbar_layout.addWidget(btn)

    toolbar_layout.addStretch()

    version_lbl = QLabel(f"v{self.CURRENT_VERSION}")
    version_lbl.setStyleSheet("color: #3b8ed0; font-weight: bold; background-color: #1e1e1e;")
    toolbar_layout.addWidget(version_lbl)

    main_layout.addWidget(toolbar)

    # 2. Main Body Content
    content_layout = QHBoxLayout()
    content_layout.setContentsMargins(10, 10, 10, 10)
    content_layout.setSpacing(10)

    # Sidebar Navigation
    self.sidebar = QListWidget()
    self.sidebar.setFixedWidth(200)

    categories = [
        "All Downloads",
        "Not Completed",
        "Completed",
        "📋 Documents",
        "🎬 Video",
        "🎵 Audio",
        "📦 Compressed",
        "🎮 Programs",
    ]
    for cat in categories:
      item_widget = QListWidgetItem(cat)
      self.sidebar.addItem(item_widget)

    self.sidebar.setCurrentRow(0)
    self.sidebar.itemClicked.connect(self.on_category_clicked)
    content_layout.addWidget(self.sidebar)

    # Main Table
    self.table = QTableWidget()
    # 1. تفعيل التمرير الناعم بالبيكسل بدلاً من التمرير بالصفوف
    self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    # 2. تسريع وتنعيم استجابة عجلة الماوس (Mouse Wheel Scroll Speed)
    self.table.verticalScrollBar().setSingleStep(15) # يمكنك زيادة أو تقليل الرقم للتحكم بالسرعة
    self.table.setColumnCount(7)
    self.table.setHorizontalHeaderLabels([
        "ID",
        "File Name",
        "Status",
        "Size",
        "Progress",
        "Speed",
        "Time Left",
    ])

    self.table.setColumnHidden(0, True)  # Hide ID Column
    self.table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
    )
    self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    self.table.verticalHeader().setVisible(False)

    header = self.table.horizontalHeader()
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    for i in [2, 3, 4, 5, 6]:
      header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
      self.table.setColumnWidth(i, 110)

    self.table.cellDoubleClicked.connect(self.on_row_double_click)
    self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.table.customContextMenuRequested.connect(self.show_context_menu)

    content_layout.addWidget(self.table)
    main_layout.addLayout(content_layout)

  def create_tray_icon(self):
    icon_path = os.path.join(self.current_dir, "icon", "icon.ico")
    if os.path.exists(icon_path):
      image = Image.open(icon_path)
    else:
      image = Image.new("RGB", (64, 64), color=(30, 144, 255))
      d = ImageDraw.Draw(image)
      d.rectangle([(16, 16), (48, 48)], fill=(255, 255, 255))

    menu = (
        item("Open Manager", lambda: self.show_window(), default=True),
        item("Exit", lambda: self.quit_program()),
    )

    self.tray_icon = pystray.Icon(
        "DownloadManager", image, "Download Manager", menu
    )
    threading.Thread(target=self.tray_icon.run, daemon=True).start()

  def show_window(self):
    QTimer.singleShot(0, self.showNormal)
    QTimer.singleShot(0, self.activateWindow)

  def quit_program(self):
    """Clean shutdown routed safely through the main GUI thread."""
    # إيقاف أيقونة الـ Tray
    if hasattr(self, "tray_icon") and self.tray_icon:
        try:
            self.tray_icon.stop()
        except Exception:
            pass
    
    # تمرير أمر الإغلاق الفعلي ليتنفذ داخل الخيط الرئيسي لـ PyQt
    QTimer.singleShot(0, self._safe_close)

  def _safe_close(self):
    # إيقاف الـ Timer بأمان من الخيط الرئيسي
    if hasattr(self, "monitor_timer") and self.monitor_timer.isActive():
        self.monitor_timer.stop()
    
    # خروج كلي وفوري من التطبيق
    QApplication.quit()

  def on_category_clicked(self, item_widget):
    self.current_category = item_widget.text()
    self.load_data_from_json()

  def show_context_menu(self, pos: QPoint):
    row = self.table.rowAt(pos.y())
    if row >= 0:
      self.table.selectRow(row)
      menu = QMenu(self)

      resume_act = QAction("▶️ Resume Download", self)
      resume_act.triggered.connect(self.resume_download)
      menu.addAction(resume_act)

      pause_act = QAction("⏸️ Pause Download", self)
      pause_act.triggered.connect(self.pause_download)
      menu.addAction(pause_act)

      menu.addSeparator()

      delete_act = QAction("❌ Remove from List", self)
      delete_act.triggered.connect(self.delete_download)
      menu.addAction(delete_act)

      menu.exec(self.table.viewport().mapToGlobal(pos))

  def read_json_file(self):
    if not os.path.exists(self.json_file):
      return []
    try:
      with open(self.json_file, "r", encoding="utf-8") as f:
        return json.load(f)
    except (json.JSONDecodeError, PermissionError):
      return None

  def write_json_file(self, data):
    try:
      with open(self.json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    except PermissionError:
      pass

  def load_data_from_json(self):
    downloads = self.read_json_file()
    if downloads is None:
      return

    selected_id = self.get_selected_file_id()

    # Apply category filtering
    filtered = []
    for item_data in downloads:
      file_name = item_data.get("name", "").lower()
      status = item_data.get("status", "").lower()
      ext = os.path.splitext(file_name)[1]

      if (
          self.current_category == "Not Completed"
          and status == "✅ complete"
      ):
        continue
      if (
          self.current_category == "Completed"
          and status != "✅ complete"
      ):
        continue

      if self.current_category == "📋 Documents" and ext not in [
          ".pdf",
          ".docx",
          ".doc",
          ".txt",
          ".xlsx",
          ".pptx",
      ]:
        continue
      if self.current_category == "🎬 Video" and ext not in [
          ".mp4",
          ".mkv",
          ".avi",
          ".mov",
          ".flv",
          ".wmv",
      ]:
        continue
      if self.current_category == "🎵 Audio" and ext not in [
          ".mp3",
          ".wav",
          ".m4a",
          ".flac",
          ".ogg",
      ]:
        continue
      if self.current_category == "📦 Compressed" and ext not in [
          ".zip",
          ".rar",
          ".7z",
          ".tar",
          ".gz",
      ]:
        continue
      if self.current_category == "🎮 Programs" and ext not in [
          ".exe",
          ".msi",
          ".apk",
          ".bat",
          ".sh",
      ]:
        continue

      filtered.append(item_data)

    self.table.setRowCount(len(filtered))

    for row_idx, item_data in enumerate(filtered):
      file_id = str(item_data.get("id", ""))
      cols = [
          file_id,
          item_data.get("name", ""),
          item_data.get("status", ""),
          str(item_data.get("size", "")),
          str(item_data.get("progress", "")),
          str(item_data.get("speed", "")),
          str(item_data.get("time_left", "")),
      ]

      for col_idx, text in enumerate(cols):
        cell_item = QTableWidgetItem(text)
        if col_idx in [2, 3, 4, 5, 6]:
          cell_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row_idx, col_idx, cell_item)

      if selected_id and file_id == str(selected_id):
        self.table.selectRow(row_idx)

  def get_selected_file_id(self):
    selected_rows = self.table.selectedItems()
    if selected_rows:
      row = selected_rows[0].row()
      id_item = self.table.item(row, 0)
      if id_item:
        return id_item.text()
    return None

  def on_row_double_click(self, row, col):
    id_item = self.table.item(row, 0)
    if not id_item:
      return

    file_id = int(id_item.text())
    download_info = self.get_download_by_id(file_id)
    if download_info:
      dialog = PropertiesDialog(download_info, self)
      dialog.exec()

  def get_download_by_id(self, download_id):
    current_data = self.read_json_file() or []
    for item_data in current_data:
      if item_data.get("id") == int(download_id):
        return item_data
    return None

  def update_item_status(self, file_id, status_text):
    current_data = self.read_json_file() or []
    for item_data in current_data:
      if item_data["id"] == int(file_id):
        item_data["status"] = status_text
        if status_text == "Paused":
          item_data["speed"] = "0 KB/s"
        break
    self.write_json_file(current_data)

  def resume_download(self):
    file_id = self.get_selected_file_id()
    if not file_id:
      QMessageBox.warning(self, "Warning", "Please select an item from the list.")
      return

    download = self.get_download_by_id(file_id)
    if not download:
      QMessageBox.critical(self, "Error", "Download data not found.")
      return

    unique_port = 65432 + int(file_id)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      s.bind(("127.0.0.1", unique_port))
      s.close()

      main_exe_path = os.path.join(self.current_dir, "main.exe")
      main_py_path = os.path.join(self.current_dir, "main.py")

      try:
          # تحديد flags الإخفاء التام المناسبة لنظام ويندوز
          if sys.platform == "win32":
            # دمج CREATE_NO_WINDOW مع DETACHED_PROCESS لمنع ظهور الكونسول إطلاقاً
            flags = (
                subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
          else:
            flags = 0

          if os.path.exists(main_exe_path):
            subprocess.Popen(
                [main_exe_path, download["url"], str(file_id)],
                creationflags=flags,
            )
          else:
            # استخدام pythonw.exe تلقائياً بدلاً من python.exe أثناء التطوير لتفادي فتح كونسول البايثون
            executable = sys.executable
            if executable.endswith("python.exe"):
              executable = executable.replace("python.exe", "pythonw.exe")

            subprocess.Popen(
                [executable, main_py_path, download["url"], str(file_id)],
                creationflags=flags,
            )

          self.update_item_status(file_id, "Downloading")
      except Exception as e:
        QMessageBox.critical(
            self, "Error", f"Failed to execute background process:\n{str(e)}"
        )

    except socket.error:
      pass

  def pause_download(self):
    file_id = self.get_selected_file_id()
    if file_id:
      self.update_item_status(file_id, "paused")

  def stop_all_downloads(self):
    downloads = self.read_json_file()
    if not downloads:
      return

    updated = False
    for item_data in downloads:
      status = item_data.get("status", "")
      if "downloading" in status.lower() or "⏳" in status:
        item_data["status"] = "Paused"
        updated = True

    if updated:
      self.write_json_file(downloads)
      self.load_data_from_json()

  def delete_download(self):
    file_id = self.get_selected_file_id()
    if file_id:
      row = self.table.currentRow()
      name = self.table.item(row, 1).text() if row >= 0 else "selected item"

      ans = QMessageBox.question(
          self,
          "Confirm Removal",
          f"Are you sure you want to remove '{name}'?",
          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
      )

      if ans == QMessageBox.StandardButton.Yes:
        self.delete_temp_download(file_id)
        current_data = self.read_json_file() or []
        current_data = [
            item_data
            for item_data in current_data
            if item_data["id"] != int(file_id)
        ]
        self.write_json_file(current_data)
        self.load_data_from_json()

  def delete_temp_download(self, download_id):
    try:
      if not download_id:
        return False
      folder_name = os.path.splitext(download_id)[0]
      appdata_local = os.path.join(
          os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "DM_Temp"
      )
      temp_dir = os.path.join(appdata_local, "DwnlData", folder_name)

      if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        return True
      return False
    except Exception as e:
      print(f"Delete Temp Error: {e}")
      return False

  def add_download_url(self):
    dialog = AddUrlDialog(self)
    dialog.exec()

  def open_settings_window(self):
    dialog = SettingsDialog(self)
    dialog.exec()

  def load_settings(self):
    default_settings = {
        "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "num_threads": "8",
        "default_quality": "Best Quality",
        "start_with_windows": False,
    }
    if not os.path.exists(self.settings_file):
      self.settings = default_settings
      self.save_settings()
    else:
      try:
        with open(self.settings_file, "r", encoding="utf-8") as f:
          self.settings = json.load(f)
      except Exception:
        self.settings = default_settings

  def save_settings(self):
    with open(self.settings_file, "w", encoding="utf-8") as f:
      json.dump(self.settings, f, ensure_ascii=False, indent=4)

  def handle_windows_startup(self, enable: bool):
    key_name = "DownloadManagerTray"
    registry_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
      key = winreg.OpenKey(
          winreg.HKEY_CURRENT_USER, registry_path, 0, winreg.KEY_SET_VALUE
      )
      if enable:
        if getattr(sys, "frozen", False):
          executable_path = os.path.abspath(sys.executable)
          command = f'"{executable_path}" --tray'
        else:
          python_exe = os.path.abspath(sys.executable)
          script_path = os.path.abspath(__file__)
          command = f'"{python_exe}" "{script_path}" --tray'

        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, command)
      else:
        try:
          winreg.DeleteValue(key, key_name)
        except FileNotFoundError:
          pass
      winreg.CloseKey(key)
    except Exception as e:
      print(f"Startup Config Error: {e}")

  def start_update_thread(self):
        # حفظ المرجع في self.update_thread يمنع الـ Garbage Collector من حذفه تلقائياً
        self.update_thread = UpdateCheckerThread(self.CURRENT_VERSION, self.VERSION_URL, self)
        self.update_thread.update_available.connect(self.show_update_dialog)
        self.update_thread.start()

  def show_update_dialog(self, latest_version, download_url, release_notes):
    import webbrowser

    msg_box = QMessageBox(self)
    msg_box.setWindowTitle("Update Available!")
    msg_box.setText(f"🎉 <b>A new version (v{latest_version}) is available!</b>")
    
    # تنسيق مميزات التحديث المكتوبة في الديسكربشن لتظهر بشكل منظم
    formatted_notes = release_notes.replace('\n', '<br>')
    msg_box.setInformativeText(f"<b>What's New:</b><br><br>{formatted_notes}")
    
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
    
    # تغيير نصوص الأزرار
    yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)
    yes_btn.setText("Download Update")
    
    no_btn = msg_box.button(QMessageBox.StandardButton.No)
    no_btn.setText("Later")

    reply = msg_box.exec()
    if reply == QMessageBox.StandardButton.Yes:
        webbrowser.open(download_url)


if __name__ == "__main__":
  # Single Instance Lock Mechanism
  try:
    single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    single_instance_socket.bind(("127.0.0.1", 65432))
  except socket.error:
    print("Application is already running in the background.")
    sys.exit(0)

  app = QApplication(sys.argv)
  viewer = IDMRealTimeViewer()

  if len(sys.argv) > 1 and sys.argv[1] == "--tray":
    viewer.hide()
  else:
    viewer.show()

  exit_code = app.exec()
  os._exit(exit_code)