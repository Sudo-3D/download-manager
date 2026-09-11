# 📥 Modern Download Manager (MDM)

A free, open-source download manager featuring a smart file organizer and seamless browser integration.

**Download Manager** is a complete, free utility designed to help you download software, games, videos, and audio from virtually any website or platform at high speeds. It features an intuitive graphical interface for file organization, runs silently in the background via the system tray for fast instant access, and integrates directly with your web browser via a native extension.

---

## 🚀 Quick Download for End Users (Just want to use the app?)

If you just want to use MDM on your PC without setting up code or Python environments:

1. Go to the **[Releases](../../releases)** section on the right side of this GitHub repository.
2. Download the latest version of the pre-compiled executable (`.exe`).
3. Run the application directly on your Windows PC!

---

## ✨ Key Features

- 🎥 **Universal Video Downloads:** Download videos and full playlists from almost any platform.
- 🎵 **Audio Extraction:** Extract and download audio-only streams at maximum quality with a single click.
- 🎮 **Software & Games:** Fast multi-threaded downloading for large files and direct links.
- ⚡ **Background System Tray Icon:** Runs efficiently in the background with a system tray (Taskbar) icon for instant launching and minimized resource usage.
- 📁 **Smart File Organizer:** Automatically categorizes your downloads by type, size, and date for effortless file management.
- 🧩 **Smart Browser Integration:** Automatically captures download links as you browse, and adds a handy download button directly on YouTube videos for quick one-click downloads.
- 🔓 **100% Free & Open Source:** Free for personal use, modification, and community contribution.

---

## 🛠️ Browser Extension Installation Guide (Developer Mode)

> **Note:** The extension is currently undergoing review for the **Chrome Web Store** and **Microsoft Edge Add-ons**. In the meantime, you can easily install it manually using Developer Mode:

1. **Run the Installer as Administrator:**
   - Go to the project root directory.
   - Right-click on the `install` file (or `install.bat`) and select **Run as Administrator**.
   - *This step registers the extension path in the Windows Registry for all Chromium-based browsers.*

2. **Enable Developer Mode in Your Browser:**
   - Open your browser (Chrome, Edge, Brave, etc.).
   - Navigate to the Extensions page (`chrome://extensions` or `edge://extensions`).
   - Toggle **Developer Mode** on in the top-right corner.

3. **Load the Unpacked Extension:**
   - Click the **Load unpacked** button.
   - Navigate to the installation path on your system drive (typically `C:\`).
   - Select the **`extension`** folder and click **Select Folder**.
   - *The extension is now activated!* 🎉

---

### ⚠️ Important Note (If Installed on a Non-C Drive)

If you install or move the application to a partition other than `C:\` (such as `D:\` or `E:\`):

1. After adding the extension to your browser, copy its **Extension ID** (the long string of random letters, e.g., `ehlmakpkikgbekcdaoonkflbidmfeaag`).
2. Open the **`com.python.download.manager.json`** file located inside the program folder.
3. Locate the `allowed_origins` field:
   ```json
   "allowed_origins": [
     "chrome-extension://YOUR_COPIED_EXTENSION_ID/"
   ]