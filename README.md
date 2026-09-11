# 📥 Modern Download Manager (MDM)

> **A free, open-source download manager featuring a smart file organizer and seamless browser integration.**

**Download Manager** is a complete, free utility designed to help you download software, games, videos, and audio from virtually any website or platform at high speeds. It features an intuitive graphical interface for file organization and integrates directly with your web browser via a native extension.

---

## ✨ Key Features

- 🎥 **Universal Video Downloads:** Download videos and full playlists from almost any platform.
- 🎵 **Audio Extraction:** Extract and download audio-only streams at maximum quality with a single click.
- 🎮 **Software & Games:** Fast multi-threaded downloading for large files and direct links.
- 📁 **Smart File Organizer:** Automatically categorizes your downloads by type, size, and date for effortless file management.
- 🧩 **Browser Extension:** Captures download links automatically as soon as you click them in your browser.
- 🔓 **100% Free & Open Source:** Free for personal use, modification, and community contribution.

---

## 🛠️ Browser Extension Installation Guide (Developer Mode)

> **Note:** The extension is currently undergoing review for the **Chrome Web Store and Edge Web Store**. In the meantime, you can easily install it manually using Developer Mode:

1. **Run the Installer as Administrator:**
   - Go to the project root directory.
   - Right-click on the `install` file (or `install.bat`) and select **Run as Administrator**.
   - *This step registers the extension path in the Windows Registry for all Chromium-based browsers.*

2. **Enable Developer Mode in Your Browser:**
   - Open your browser (Chrome, Edge, Brave, etc.).
   - Navigate to the Extensions page (`chrome://extensions`).
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


This project is completely Open Source, and contributions are welcome! If you would like to add features or fix issues.

<ElicitationsGroup message="Would you like to add badges or extra sections to your README?">
  <Elicitation label="Add technical shields/badges (Python, PyQt, License)" query="How do I add SVG shields/badges for Python, License, and GitHub release at the top of the English README?"/>
  <Elicitation label="Add a Quick Start guide for building from source using uv" query="How do I add a developer setup section in English explaining how to clone, set up uv, and build with PyInstaller?"/>
</ElicitationsGroup>