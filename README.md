# ScreenSnapper

A sci-fi themed, multi-monitor screenshot tool for Windows, built with PyQt5.

---

## Features
- **Global Hotkey**: Set a custom global hotkey to trigger screenshots (e.g., Ctrl+Shift+S).
- **Multi-Monitor Support**: Select and capture any area across all connected monitors.
- **Overlay Selection**: Dimmed overlay with drag-to-select, Save, Copy, and Cancel buttons.
- **Save**: Cropped screenshots are saved in `Pictures/<date>/` as high-quality PNGs.
- **Copy to Clipboard**: Instantly copy the selected screenshot to the clipboard.
- **Auto-Start**: Option to start with Windows logon (via registry).
- **System Tray**: Runs in the tray with minimize/restore and exit options.
- **Custom Sci-Fi Theme**: Black and neon green UI, custom title bars, and tray icon.
- **Developer Credit**: Developed by R ! Y 4 Z.

---

## Installation

1. **Clone the repository**
   ```sh
   git clone https://github.com/yourusername/screensnapper.git
   cd screensnapper
   ```
2. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```
3. **(Optional) Place your icon**
   - Place your `s.png` icon in the project directory for a custom tray/app icon.

---

## Usage

- Run the app:
  ```sh
  python sstaker.py
  ```
- Set your hotkey and preferences in the main window.
- Use the hotkey to select and save/copy screenshots.
- Minimize to tray and restore by double-clicking the tray icon.

---

## Build Windows Executable

1. **Install PyInstaller**
   ```sh
   pip install pyinstaller
   ```
2. **Build the .exe**
   ```sh
   pyinstaller --noconfirm --onefile --windowed --icon=s.png sstaker.py
   ```
3. **Find your .exe in the `dist/` folder.**

---

## Developer

**Developed by R ! Y 4 Z**

---

## License

MIT License (or specify your own) 