import sys
import os
import datetime
import traceback
import threading
import pyautogui
import keyboard
from PIL import Image
from PyQt5 import QtWidgets, QtCore, QtGui
import winreg

APP_NAME = "ScreenSnapper"
REG_PATH = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
ICON_PATH = os.path.join(os.path.dirname(__file__), 's.png')

class Overlay(QtWidgets.QWidget):
    selection_made = QtCore.pyqtSignal(QtCore.QRect, QtGui.QPixmap)

    def __init__(self, screenshot, min_x=0, min_y=0, parent=None):
        super().__init__(parent)
        # Set overlay to cover the entire virtual desktop (all monitors)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.start = None
        self.end = None
        self.rubber_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)
        self.screenshot = screenshot
        self.save_btn = None
        self.cancel_btn = None
        self.selection_rect = None
        self.min_x = min_x  # Virtual desktop top-left X
        self.min_y = min_y  # Virtual desktop top-left Y
        # Set geometry to match virtual desktop
        self.setGeometry(self.min_x, self.min_y, self.screenshot.width(), self.screenshot.height())
        self.show()  # Show at the correct position and size

    @staticmethod
    def grab_fullscreen():
        # Capture the entire virtual desktop (all monitors)
        screens = QtWidgets.QApplication.screens()
        if len(screens) > 1:
            min_x = min([s.geometry().x() for s in screens])
            min_y = min([s.geometry().y() for s in screens])
            max_x = max([s.geometry().x() + s.geometry().width() for s in screens])
            max_y = max([s.geometry().y() + s.geometry().height() for s in screens])
            full_rect = QtCore.QRect(min_x, min_y, max_x - min_x, max_y - min_y)
            img = QtGui.QPixmap(full_rect.size())
            painter = QtGui.QPainter(img)
            for s in screens:
                s_img = s.grabWindow(0)
                # Draw each screen at the correct offset in the virtual desktop
                painter.drawPixmap(s.geometry().topLeft() - full_rect.topLeft(), s_img)
            painter.end()
            return img, min_x, min_y
        else:
            geo = screens[0].geometry()
            return screens[0].grabWindow(0), geo.x(), geo.y()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setOpacity(1.0)
        painter.drawPixmap(0, 0, self.screenshot)
        if self.start and self.end:
            rect = QtCore.QRect(self.start, self.end).normalized()
            region = QtGui.QRegion(self.rect())
            region = region.subtracted(QtGui.QRegion(rect))
            painter.setOpacity(0.4)
            painter.setClipRegion(region)
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 200))
            painter.setClipping(False)
            painter.setOpacity(1.0)
            painter.setPen(QtGui.QPen(QtCore.Qt.red, 2))
            painter.drawRect(rect)
        else:
            painter.setOpacity(0.4)
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 200))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            self.start = pos
            self.end = self.start
            self.rubber_band.setGeometry(QtCore.QRect(self.start, QtCore.QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if self.start:
            self.end = event.pos()
            self.rubber_band.setGeometry(QtCore.QRect(self.start, self.end).normalized())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.start:
            self.end = event.pos()
            self.rubber_band.hide()
            rect = QtCore.QRect(self.start, self.end).normalized()
            self.selection_rect = rect
            self.show_buttons(rect)
            self.update()

    def show_buttons(self, rect):
        btn_w, btn_h = 80, 30
        margin = 10
        # Ensure buttons are always visible within the overlay
        x = min(rect.right() - btn_w, self.width() - btn_w - margin)
        y = min(rect.bottom() + margin, self.height() - btn_h - margin)
        x = max(x, margin)
        y = max(y, margin)
        self.save_btn = QtWidgets.QPushButton("Save", self)
        self.save_btn.setGeometry(x, y, btn_w, btn_h)
        self.save_btn.clicked.connect(self.save_selection)
        self.save_btn.show()
        self.copy_btn = QtWidgets.QPushButton("Copy", self)
        self.copy_btn.setGeometry(x - btn_w - margin, y, btn_w, btn_h)
        self.copy_btn.clicked.connect(self.copy_selection)
        self.copy_btn.show()
        self.cancel_btn = QtWidgets.QPushButton("Cancel", self)
        self.cancel_btn.setGeometry(x - 2*btn_w - 2*margin, y, btn_w, btn_h)
        self.cancel_btn.clicked.connect(self.cancel_selection)
        self.cancel_btn.show()

    def save_selection(self):
        if self.selection_rect:
            # Crop the screenshot using the selection rect (relative to virtual desktop)
            cropped = self.screenshot.copy(self.selection_rect)
            self.selection_made.emit(self.selection_rect, cropped)
        QtCore.QTimer.singleShot(0, self.close)

    def copy_selection(self):
        if self.selection_rect:
            cropped = self.screenshot.copy(self.selection_rect)
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setPixmap(cropped)
        self.close()

    def cancel_selection(self):
        self.close()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        menu = QtWidgets.QMenu(parent)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(QtWidgets.qApp.quit)
        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)
        self.parent_window = parent

    def on_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            if self.parent_window:
                self.parent_window.showNormal()
                self.parent_window.activateWindow()
                self.parent_window.raise_()

class SciFiTitleBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(36)
        self.setMinimumWidth(350)
        self.setMaximumHeight(36)
        self.setStyleSheet('''
            background-color: #101820;
            border-bottom: 2px solid #39FF14;
        ''')
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        self.title = QtWidgets.QLabel(APP_NAME)
        self.title.setStyleSheet('color: #39FF14; font-size: 16px; font-weight: bold;')
        self.title.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(self.title)
        layout.addStretch(1)
        self.min_btn = QtWidgets.QPushButton()
        self.min_btn.setFixedSize(28, 28)
        # Use a QLabel with a green '-' as the icon for the minimize button
        min_label = QtWidgets.QLabel("-")
        min_label.setAlignment(QtCore.Qt.AlignCenter)
        min_label.setStyleSheet('color: #39FF14; font-size: 18px; font-weight: bold;')
        min_pixmap = QtGui.QPixmap(18, 18)
        min_pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(min_pixmap)
        painter.setPen(QtGui.QPen(QtGui.QColor("#39FF14"), 3))
        painter.drawLine(3, 9, 15, 9)
        painter.end()
        min_icon = QtGui.QIcon(min_pixmap)
        self.min_btn.setIcon(min_icon)
        self.min_btn.setIconSize(QtCore.QSize(18, 18))
        self.min_btn.setStyleSheet('''
            QPushButton {
                background: #101820;
                color: #39FF14;
                border: 2px solid #39FF14;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #39FF14;
                color: #101820;
                border: 2px solid #39FF14;
            }
        ''')
        self.min_btn.clicked.connect(self.on_minimize)
        layout.addWidget(self.min_btn, 0, QtCore.Qt.AlignRight)
        # Use a Qt standard close icon for the close button
        self.close_btn = QtWidgets.QPushButton()
        self.close_btn.setFixedSize(28, 28)
        close_icon = self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton)
        self.close_btn.setIcon(close_icon)
        self.close_btn.setIconSize(QtCore.QSize(18, 18))
        self.close_btn.setStyleSheet('''
            QPushButton {
                background: #101820;
                color: #39FF14;
                border: 2px solid #39FF14;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #FF003C;
                color: #FFFFFF;
                border: 2px solid #FF003C;
            }
        ''')
        self.close_btn.clicked.connect(self.on_close)
        layout.addWidget(self.close_btn, 0, QtCore.Qt.AlignRight)
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.parent.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def on_close(self):
        self.parent.close()

    def on_minimize(self):
        self.parent.showMinimized()

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setFixedSize(420, 220)
        # Frameless window for custom title bar
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        # Use s.png as the icon if it exists, else fallback
        if os.path.exists(ICON_PATH):
            icon = QtGui.QIcon(ICON_PATH)
        else:
            style = QtWidgets.QApplication.style()
            icon = style.standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.setWindowIcon(icon)
        # Apply sci-fi black and green theme
        self.setStyleSheet('''
            QWidget {
                background-color: #101820;
                color: #39FF14;
                font-family: "Consolas", "Fira Mono", "Courier New", monospace;
                font-size: 14px;
            }
            QPushButton {
                background-color: #101820;
                color: #39FF14;
                border: 2px solid #39FF14;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                transition: background 0.2s;
            }
            QPushButton:hover {
                background-color: #39FF14;
                color: #101820;
            }
            QLabel {
                color: #39FF14;
                font-size: 15px;
                font-weight: bold;
            }
            QCheckBox {
                color: #39FF14;
                font-size: 14px;
            }
            QCheckBox::indicator {
                border: 2px solid #39FF14;
                background: #101820;
            }
            QCheckBox::indicator:checked {
                background: #39FF14;
            }
            QLineEdit {
                background: #101820;
                color: #39FF14;
                border: 2px solid #39FF14;
                border-radius: 4px;
                padding: 4px 8px;
            }
        ''')
        # Layout with custom title bar
        vlayout = QtWidgets.QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(0)
        self.title_bar = SciFiTitleBar(self)
        vlayout.addWidget(self.title_bar)
        content = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        self.hotkey_btn = QtWidgets.QPushButton("Set Hotkey")
        self.hotkey_btn.setMinimumHeight(36)
        self.hotkey_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        font = self.hotkey_btn.font()
        font.setBold(True)
        self.hotkey_btn.setFont(font)
        self.hotkey_label = QtWidgets.QLabel("Current Hotkey: None")
        self.autostart_chk = QtWidgets.QCheckBox("Auto start with Windows logon")
        layout.addWidget(self.hotkey_btn)
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.autostart_chk)
        layout.addStretch()
        # Add developer credit
        self.credit_label = QtWidgets.QLabel('Developed by R ! Y 4 Z')
        self.credit_label.setAlignment(QtCore.Qt.AlignCenter)
        self.credit_label.setStyleSheet('color: #39FF14; font-size: 12px; font-weight: normal; margin-top: 8px;')
        layout.addWidget(self.credit_label)
        vlayout.addWidget(content)
        self.hotkey_btn.clicked.connect(self.set_hotkey)
        self.autostart_chk.stateChanged.connect(self.toggle_autostart)
        self.hotkey = None
        self.hotkey_str = None
        self.tray_icon = SystemTrayIcon(icon, self)
        self.tray_icon.setToolTip(APP_NAME)
        self.tray_icon.show()
        self.registered_hotkey = None
        self.load_hotkey()  # Load hotkey before autostart to ensure label is set
        self.load_autostart()
        self.tray_msg_shown = False  # To show notification only once
        self.hotkey_dialog_open = False

    def set_hotkey(self):
        self.hotkey_dialog_open = True
        dlg = HotkeyDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.hotkey_str = dlg.hotkey_str
            self.hotkey = dlg.hotkey
            self.hotkey_label.setText(f"Current Hotkey: {self.hotkey_str}")
            self.save_hotkey()
            self.register_hotkey()
        self.hotkey_dialog_open = False

    def register_hotkey(self):
        if self.registered_hotkey:
            keyboard.remove_hotkey(self.registered_hotkey)
        if self.hotkey_str:
            try:
                self.registered_hotkey = keyboard.add_hotkey(self.hotkey_str, self.trigger_overlay)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Hotkey Error", str(e))

    def trigger_overlay(self):
        if getattr(self, 'hotkey_dialog_open', False):
            return  # Don't take screenshot if hotkey dialog is open
        QtCore.QMetaObject.invokeMethod(self, "show_overlay", QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def show_overlay(self):
        # Take screenshot before showing overlay, covering all monitors
        screenshot, min_x, min_y = Overlay.grab_fullscreen()
        self.overlay = Overlay(screenshot, min_x, min_y)
        self.overlay.selection_made.connect(self.save_cropped_image)
        # self.overlay.showFullScreen()  # Not needed, overlay.show() is called in constructor

    def save_cropped_image(self, rect, pixmap):
        try:
            now = datetime.datetime.now()
            date_folder = now.strftime("%d-%b-%Y")
            time_str = now.strftime("%I_%M_%S %p")
            pictures = os.path.join(os.path.expanduser("~"), "Pictures", date_folder)
            os.makedirs(pictures, exist_ok=True)
            file_path = os.path.join(pictures, f"{time_str}.png")  # Use PNG for lossless quality
            img = pixmap.toImage()
            buffer = img.bits().asstring(img.byteCount())
            pil_img = Image.frombytes("RGBA", (img.width(), img.height()), buffer, "raw", "BGRA")
            # Save as PNG with alpha channel, no compression for max quality
            pil_img.save(file_path, "PNG", optimize=True, compress_level=0)
            def show_success():
                QtWidgets.QMessageBox.information(self, "Screenshot Saved", f"Screenshot saved successfully!\n{file_path}")
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("Shell.Application")
                    folder = os.path.abspath(pictures)
                    shell.Namespace(folder)
                except ImportError:
                    pass
            QtCore.QTimer.singleShot(0, show_success)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Failed to save screenshot:\n{e}\n{traceback.format_exc()}")

    def toggle_autostart(self, state):
        try:
            if state == QtCore.Qt.Checked:
                self.set_autostart()
            else:
                self.remove_autostart()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Autostart Error", str(e))

    def set_autostart(self):
        exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)

    def remove_autostart(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass

    def load_autostart(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                self.autostart_chk.setChecked(True)
        except FileNotFoundError:
            self.autostart_chk.setChecked(False)

    def save_hotkey(self):
        try:
            with open("hotkey.txt", "w") as f:
                f.write(self.hotkey_str or "")
        except Exception:
            pass

    def load_hotkey(self):
        try:
            with open("hotkey.txt", "r") as f:
                self.hotkey_str = f.read().strip()
                if self.hotkey_str:
                    self.hotkey_label.setText(f"Current Hotkey: {self.hotkey_str}")
                    self.register_hotkey()
                else:
                    self.hotkey_label.setText("Current Hotkey: None")
        except Exception:
            self.hotkey_label.setText("Current Hotkey: None")

    def on_hide(self, event):
        self.hide()
        self.tray_icon.show()
        event.ignore()

    def closeEvent(self, event):
        # Minimize to tray instead of exiting
        event.ignore()
        self.hide()
        self.tray_icon.show()
        if not self.tray_msg_shown:
            self.tray_icon.showMessage(
                APP_NAME,
                "Application minimized to tray. Double-click the tray icon to restore.",
                QtWidgets.QSystemTrayIcon.Information,
                3000
            )
            self.tray_msg_shown = True

class HotkeyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Frameless window for custom title bar
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setModal(True)
        self.setFixedSize(400, 180)
        # Sci-fi themed custom title bar
        vlayout = QtWidgets.QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(0)
        self.title_bar = SciFiTitleBar(self)
        self.title_bar.title.setText("Set Hotkey")
        vlayout.addWidget(self.title_bar)
        content = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self.label = QtWidgets.QLabel("Enter the hotkey combination (e.g., ctrl+shift+s):")
        layout.addWidget(self.label)
        self.input = QtWidgets.QLineEdit(self)
        self.input.setPlaceholderText("ctrl+shift+s")
        self.input.setMinimumHeight(36)
        input_font = self.input.font()
        input_font.setPointSize(16)
        self.input.setFont(input_font)
        layout.addWidget(self.input)
        # Add spacing above the Set button
        layout.addSpacing(12)
        # Add a Set button, make it more visible
        self.set_btn = QtWidgets.QPushButton("Set")
        self.set_btn.setMinimumHeight(36)
        self.set_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.set_btn.clicked.connect(self.accept)
        layout.addWidget(self.set_btn, alignment=QtCore.Qt.AlignHCenter)
        vlayout.addWidget(content)
        self.hotkey = None
        self.hotkey_str = None
        self.input.setFocus()
        self.input.returnPressed.connect(self.accept)
        # Apply the same sci-fi stylesheet as MainWindow
        self.setStyleSheet('''
            QWidget {
                background-color: #101820;
                color: #39FF14;
                font-family: "Consolas", "Fira Mono", "Courier New", monospace;
                font-size: 14px;
            }
            QPushButton {
                background-color: #101820;
                color: #39FF14;
                border: 2px solid #39FF14;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                transition: background 0.2s;
            }
            QPushButton:hover {
                background-color: #39FF14;
                color: #101820;
            }
            QLabel {
                color: #39FF14;
                font-size: 15px;
                font-weight: bold;
            }
            QCheckBox {
                color: #39FF14;
                font-size: 14px;
            }
            QCheckBox::indicator {
                border: 2px solid #39FF14;
                background: #101820;
            }
            QCheckBox::indicator:checked {
                background: #39FF14;
            }
            QLineEdit {
                background: #101820;
                color: #39FF14;
                border: 2px solid #39FF14;
                border-radius: 4px;
                padding: 4px 8px;
            }
        ''')

    def accept(self):
        text = self.input.text().strip().lower()
        if text:
            self.hotkey_str = text
            super().accept()
        else:
            QtWidgets.QMessageBox.warning(self, "Invalid Hotkey", "Please enter a valid hotkey combination.")

    def keyPressEvent(self, event):
        # Allow normal QLineEdit editing
        super().keyPressEvent(event)

    def closeEvent(self, event):
        super().closeEvent(event)

def main():
    app = QtWidgets.QApplication(sys.argv)
    QtWidgets.QApplication.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
