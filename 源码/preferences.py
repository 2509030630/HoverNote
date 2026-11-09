from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QKeySequenceEdit, QLabel,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, sequence, autostart, apply_settings, error="", parent=None):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("设置")
        self.setMinimumWidth(440)
        self.apply_settings = apply_settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        form = QFormLayout()
        self.shortcut = QKeySequenceEdit(QKeySequence(sequence), self)
        self.shortcut.setMaximumSequenceLength(1)
        self.shortcut.setClearButtonEnabled(True)
        self.shortcut.setAccessibleName("框选快捷键")
        form.addRow("框选快捷键", self.shortcut)
        layout.addLayout(form)
        hint = QLabel("点击输入框后按下组合键，例如 Ctrl+Shift+N。\nCtrl+S 用于保存；F1–F24 可单独使用。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.autostart = QCheckBox("登录 Windows 后自动启动")
        self.autostart.setChecked(autostart)
        layout.addWidget(self.autostart)
        if error:
            message = QLabel(error)
            message.setWordWrap(True)
            message.setStyleSheet("color: #B42318;")
            layout.addWidget(message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        sequence = self.shortcut.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if self.apply_settings(sequence, self.autostart.isChecked()):
            self.accept()
