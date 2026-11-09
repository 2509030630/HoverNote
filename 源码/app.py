import sys
from pathlib import Path

from PySide6.QtCore import (
    QIODevice, QRect, QRectF, QSaveFile, QSettings, QStandardPaths, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QCursor, QFont, QIcon, QKeySequence, QPainter, QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMenu, QMenuBar, QMessageBox,
    QPlainTextEdit, QPushButton, QSizeGrip, QSizePolicy, QSystemTrayIcon,
    QToolButton, QVBoxLayout, QWidget,
)

from windows_hotkey import WindowsHotkey
from preferences import SettingsDialog
import startup


STYLE = """
QWidget#note { background: #FFFFFF; border: 1px solid #CDD3DC; border-radius: 8px; }
QWidget#titlebar { background: #F5F6F8; border-bottom: 1px solid #E5E7EB; }
QLabel#title { color: #202630; font-weight: 600; }
QLabel#state { color: #707783; font-size: 12px; }
QPlainTextEdit { background: #FFFFFF; color: #202630; border: 0; padding: 12px; }
QToolButton, QPushButton { color: #202630; border: 1px solid transparent; border-radius: 4px;
              padding: 5px 10px; background: transparent; }
QToolButton:hover, QPushButton:hover { background: #E7ECF3; }
QPushButton#save { border-color: #B6CAEE; background: #F2F7FF; text-align: center; }
QPushButton#save:hover { background: #E2EEFF; }
QPushButton#save:pressed { background: #D4E5FF; }
QPushButton#save:focus { border-color: #2675EF; }
QToolButton#close:hover { background: #C42B1C; color: white; }
QWidget#statusbar { background: #F5F6F8; }
QLabel#status { color: #707783; font-size: 12px; }
QMenuBar { background: #F5F6F8; color: #202630; border-bottom: 1px solid #E5E7EB; }
QMenuBar::item { padding: 5px 10px; background: transparent; }
QMenuBar::item:selected { background: #E2EEFF; }
QMenu { background: #FFFFFF; color: #202630; border: 1px solid #CDD3DC;
        padding: 5px; }
QMenu::item { padding: 8px 18px; border-radius: 4px; }
QMenu::item:selected { background: #E2EEFF; }
"""


class TitleBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
            event.accept()
        else:
            super().mousePressEvent(event)


class NoteWindow(QWidget):
    closed = Signal(object)
    settings_requested = Signal()

    def __init__(self, rect: QRect):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.file_path = None
        self.setObjectName("note")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setWindowTitle("未命名 - 悬浮文本框")
        self.setMinimumSize(300, 180)
        self.setGeometry(rect)
        self.setStyleSheet(STYLE)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)
        titlebar = TitleBar(self)
        titlebar.setObjectName("titlebar")
        titlebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        titlebar.setCursor(Qt.CursorShape.SizeAllCursor)
        row = QHBoxLayout(titlebar)
        row.setContentsMargins(12, 6, 6, 6)
        row.setSpacing(8)
        self.title = QLabel("未命名")
        self.title.setObjectName("title")
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.state = QLabel("未保存")
        self.state.setObjectName("state")
        self.state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self.title, 1)
        row.addWidget(self.state)

        self.save_action = QAction("保存", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(lambda: self.save())
        self.addAction(self.save_action)
        self.save_button = QPushButton("保存")
        self.save_button.setObjectName("save")
        self.save_button.setToolTip("保存（Ctrl+S）")
        self.save_button.clicked.connect(self.save_action.trigger)
        row.addWidget(self.save_button)
        close_button = QToolButton()
        close_button.setObjectName("close")
        close_button.setText("×")
        close_button.setToolTip("关闭")
        close_button.setAccessibleName("关闭文本框")
        close_button.clicked.connect(self.close)
        row.addWidget(close_button)
        layout.addWidget(titlebar)

        self.menu_bar = QMenuBar(self)
        self.menu_bar.setNativeMenuBar(False)
        self.menu_bar.setCursor(Qt.CursorShape.ArrowCursor)
        self.file_menu = self.menu_bar.addMenu("文件")
        self.file_menu.addAction(self.save_action)
        self.file_menu.addAction("保存为 TXT", lambda: self.save("txt"))
        self.file_menu.addAction("保存为 Markdown", lambda: self.save("md"))
        self.settings_menu = self.menu_bar.addMenu("设置")
        self.settings_menu.addAction("设置…", self.settings_requested.emit)
        layout.addWidget(self.menu_bar)

        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Microsoft YaHei UI", 11))
        self.editor.setAccessibleName("文本内容")
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)
        self.editor.document().modificationChanged.connect(self.update_title)
        layout.addWidget(self.editor, 1)
        statusbar = QWidget(self)
        statusbar.setObjectName("statusbar")
        statusbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        statusbar.setCursor(Qt.CursorShape.ArrowCursor)
        status_row = QHBoxLayout(statusbar)
        status_row.setContentsMargins(12, 4, 2, 2)
        status_row.setSpacing(4)
        self.status = QLabel("UTF-8    |    Ctrl+S 保存")
        self.status.setObjectName("status")
        status_row.addWidget(self.status, 1)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setToolTip("拖动边缘或右下角调整大小")
        self.size_grip.setAccessibleName("调整文本框大小")
        status_row.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(statusbar)

    def resize_edges(self, point):
        edges = Qt.Edge(0)
        if point.x() < 6:
            edges |= Qt.Edge.LeftEdge
        elif point.x() >= self.width() - 6:
            edges |= Qt.Edge.RightEdge
        if point.y() < 6:
            edges |= Qt.Edge.TopEdge
        elif point.y() >= self.height() - 6:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mousePressEvent(self, event):
        edges = self.resize_edges(event.position())
        if event.button() == Qt.MouseButton.LeftButton and edges:
            self.windowHandle().startSystemResize(edges)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        edges = self.resize_edges(event.position())
        if edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_title()

    def update_title(self, modified=False):
        name = self.file_path.name if self.file_path else "未命名"
        metrics = self.title.fontMetrics()
        self.title.setText(metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, self.title.width()))
        self.title.setAccessibleName(name)
        self.title.setToolTip(str(self.file_path) if self.file_path else name)
        self.setWindowTitle(f"{name} - 悬浮文本框")
        self.state.setText("未保存" if not self.file_path or self.editor.document().isModified()
                           else "已保存")

    def show_context_menu(self, point):
        menu = self.editor.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(self.save_action)
        menu.addAction("保存为 TXT", lambda: self.save("txt"))
        menu.addAction("保存为 Markdown", lambda: self.save("md"))
        menu.exec(self.editor.mapToGlobal(point))
        menu.deleteLater()

    def save(self, suffix=None):
        if self.file_path and suffix is None:
            return self.save_to(self.file_path)
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        suggested = self.file_path or Path(documents) / "未命名.txt"
        if suffix:
            suggested = suggested.with_suffix("." + suffix)
        filters = "文本文档 (*.txt);;Markdown 文档 (*.md)"
        selected = "Markdown 文档 (*.md)" if suggested.suffix.lower() == ".md" else "文本文档 (*.txt)"
        filename, selected = QFileDialog.getSaveFileName(self, "保存文本", str(suggested), filters, selected)
        if not filename:
            return False
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".md" if "*.md" in selected else ".txt")
            if path.exists():
                answer = QMessageBox.question(
                    self, "覆盖文件", f"{path.name} 已存在，是否覆盖？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return False
        return self.save_to(path)

    def save_to(self, path):
        path = Path(path)
        target = QSaveFile(str(path))
        if not target.open(QIODevice.OpenModeFlag.WriteOnly):
            QMessageBox.critical(self, "保存失败", target.errorString())
            return False
        data = self.editor.toPlainText().encode("utf-8")
        if target.write(data) != len(data):
            error = target.errorString()
            target.cancelWriting()
            QMessageBox.critical(self, "保存失败", error)
            return False
        if not target.commit():
            QMessageBox.critical(self, "保存失败", target.errorString())
            return False
        self.file_path = path
        self.editor.document().setModified(False)
        self.update_title()
        return True

    def closeEvent(self, event):
        if self.editor.document().isModified():
            answer = QMessageBox.question(
                self, "保存更改", "内容尚未保存，是否保存后关闭？",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save and not self.save():
                event.ignore()
                return
        self.closed.emit(self)
        event.accept()


class SelectionOverlay(QWidget):
    selected = Signal(QRect)
    canceled = Signal()

    def __init__(self, screen, shortcut="Ctrl+Alt+N"):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(screen.geometry())
        self.start = None
        self.selection = QRect()
        self.shortcut = shortcut

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = event.position()
            self.selection = QRect()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.canceled.emit()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            # shortcut: 一次框选限于起始屏幕，需跨屏选区时再统一物理坐标。
            self.selection = QRectF(self.start, event.position()).normalized().toRect().intersected(self.rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start is not None:
            self.selection = QRectF(self.start, event.position()).normalized().toRect().intersected(self.rect())
            if self.selection.width() >= 8 and self.selection.height() >= 8:
                self.selected.emit(QRect(self.mapToGlobal(self.selection.topLeft()), self.selection.size()))
            else:
                self.canceled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canceled.emit()
        else:
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRect(QRectF(self.rect()))
        if not self.selection.isNull():
            path.addRect(QRectF(self.selection))
        painter.fillPath(path, QColor(16, 30, 50, 100))
        if not self.selection.isNull():
            painter.setPen(QPen(QColor("#2675EF"), 2))
            painter.drawRect(self.selection.adjusted(1, 1, -1, -1))
        screen = self.screen()
        available = screen.availableGeometry().translated(-self.geometry().topLeft())
        hint = QRect(available.left() + 16, available.bottom() - 66, available.width() - 32, 44)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(25, 38, 57, 225))
        painter.drawRoundedRect(hint, 8, 8)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Microsoft YaHei UI", 11))
        painter.drawText(hint, Qt.AlignmentFlag.AlignCenter,
                         f"按住 {self.shortcut}，左键拖动框选 · Esc 取消")


def note_icon():
    return QIcon(str(Path(__file__).with_name("HoverNote.ico")))


class Controller:
    def __init__(self, app):
        self.app = app
        self.notes = []
        self.overlays = []
        self.pending_rect = None
        self.settings_dialog = None
        self.settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                                  "FloatingNotes", "FloatingNotes")
        self.hotkey = WindowsHotkey(app, self.begin_selection,
                                   self.settings.value("shortcut", "Ctrl+Alt+N", type=str))
        self.hotkey_error = ""
        self.timer = QTimer(app)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.check_keys)
        self.tray = QSystemTrayIcon(app.windowIcon(), app)
        menu = QMenu()
        self.tray_hint = menu.addAction("")
        self.tray_hint.setEnabled(False)
        menu.addAction("设置…", self.show_settings)
        menu.addSeparator()
        menu.addAction("退出", self.quit)
        self.tray.setContextMenu(menu)
        self.tray_menu = menu
        self.tray.activated.connect(self.tray_clicked)
        try:
            self.hotkey.register()
        except OSError as error:
            self.hotkey_error = str(error)
        self.update_shortcut_hint()
        self.tray.show()
        if self.hotkey_error:
            QTimer.singleShot(0, self.show_settings)
        else:
            self.show_hint()

    def update_shortcut_hint(self):
        self.shortcut_text = self.hotkey.sequence.replace("Meta+", "Win+")
        hint = f"按住 {self.shortcut_text} 框选" if self.hotkey.registered else "快捷键未注册，请打开设置"
        self.tray_hint.setText(hint)
        self.tray.setToolTip(f"悬浮文本框 · {hint}")

    def show_settings(self):
        if self.settings_dialog is not None:
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        self.cancel_selection()
        try:
            autostart = startup.enabled()
        except OSError as error:
            QMessageBox.critical(None, "无法读取自启动设置", str(error))
            return
        active = self.app.activeWindow()
        parent = active if isinstance(active, NoteWindow) else None
        dialog = SettingsDialog(self.hotkey.sequence, autostart, self.apply_settings,
                                self.hotkey_error, parent)
        self.settings_dialog = dialog
        try:
            dialog.exec()
        finally:
            self.settings_dialog = None
            dialog.deleteLater()

    def apply_settings(self, sequence, autostart):
        old_sequence, was_registered = self.hotkey.sequence, self.hotkey.registered
        try:
            if QKeySequence(sequence) == QKeySequence(QKeySequence.StandardKey.Save):
                raise ValueError("Ctrl+S 已用于保存，请选择其他框选快捷键。")
            self.hotkey.set_sequence(sequence)
            self.hotkey.register()
            startup.set_enabled(autostart)
        except (ValueError, OSError) as error:
            try:
                if not was_registered:
                    self.hotkey.unregister()
                self.hotkey.set_sequence(old_sequence)
            except OSError as rollback_error:
                error = OSError(f"{error}\n恢复原快捷键失败：{rollback_error}")
            self.update_shortcut_hint()
            QMessageBox.critical(self.settings_dialog, "设置未保存", str(error))
            return False
        self.settings.setValue("shortcut", self.hotkey.sequence)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            QMessageBox.warning(self.settings_dialog, "配置写入失败",
                                "设置已在本次运行生效，但无法写入配置文件；重启后可能恢复原快捷键。")
        self.hotkey_error = ""
        self.update_shortcut_hint()
        return True

    def show_hint(self):
        self.tray.showMessage("悬浮文本框已就绪", f"按住 {self.shortcut_text}，左键拖出文本框；Esc 取消。",
                              QSystemTrayIcon.MessageIcon.Information, 6000)

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_hint()

    def begin_selection(self):
        if self.settings_dialog is not None or self.overlays or self.pending_rect is not None:
            return
        for screen in self.app.screens():
            overlay = SelectionOverlay(screen, self.shortcut_text)
            overlay.selected.connect(self.finish_selection)
            overlay.canceled.connect(self.cancel_selection)
            self.overlays.append(overlay)
            overlay.show()
        active = next((overlay for overlay in self.overlays
                       if overlay.geometry().contains(QCursor.pos())), self.overlays[0])
        active.raise_()
        active.activateWindow()
        active.setFocus()
        self.timer.start()

    def clear_overlays(self):
        for overlay in self.overlays:
            overlay.close()
        self.overlays.clear()

    def cancel_selection(self):
        self.timer.stop()
        self.clear_overlays()
        self.pending_rect = None

    def finish_selection(self, rect):
        self.pending_rect = rect
        self.clear_overlays()

    def check_keys(self):
        if self.pending_rect is not None:
            if self.hotkey.is_released():
                rect = self.pending_rect
                self.pending_rect = None
                self.timer.stop()
                self.create_note(rect)
        elif not self.hotkey.is_held():
            self.cancel_selection()

    def create_note(self, rect):
        rect = QRect(rect)
        screen = self.app.screenAt(rect.center()) or self.app.primaryScreen()
        bounds = screen.availableGeometry()
        rect.setSize(rect.size().expandedTo(QRect(0, 0, 300, 180).size()).boundedTo(bounds.size()))
        rect.moveLeft(max(bounds.left(), min(rect.left(), bounds.right() - rect.width() + 1)))
        rect.moveTop(max(bounds.top(), min(rect.top(), bounds.bottom() - rect.height() + 1)))
        note = NoteWindow(rect)
        self.notes.append(note)
        note.closed.connect(self.notes.remove)
        note.settings_requested.connect(self.show_settings)
        note.show()
        note.raise_()
        note.activateWindow()
        note.editor.setFocus()

    def quit(self):
        self.cancel_selection()
        for note in self.notes[:]:
            if not note.close():
                return
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("悬浮文本框")
    app.setOrganizationName("FloatingNotes")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setWindowIcon(note_icon())
    app.setQuitOnLastWindowClosed(False)
    try:
        controller = Controller(app)
    except (OSError, ValueError) as error:
        QMessageBox.critical(None, "启动失败", str(error))
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
