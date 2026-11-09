import ctypes
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterHotKey.argtypes = (
    wintypes.HWND,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.UINT,
)
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
_user32.GetAsyncKeyState.restype = ctypes.c_short

_NAVIGATION_KEYS = {
    Qt.Key.Key_Space: 0x20,
    Qt.Key.Key_Tab: 0x09,
    Qt.Key.Key_Backspace: 0x08,
    Qt.Key.Key_Return: 0x0D,
    Qt.Key.Key_Enter: 0x0D,
    Qt.Key.Key_Escape: 0x1B,
    Qt.Key.Key_Insert: 0x2D,
    Qt.Key.Key_Delete: 0x2E,
    Qt.Key.Key_Home: 0x24,
    Qt.Key.Key_End: 0x23,
    Qt.Key.Key_Left: 0x25,
    Qt.Key.Key_Up: 0x26,
    Qt.Key.Key_Right: 0x27,
    Qt.Key.Key_Down: 0x28,
    Qt.Key.Key_PageUp: 0x21,
    Qt.Key.Key_PageDown: 0x22,
}


class WindowsHotkey(QAbstractNativeEventFilter):
    HOTKEY_ID = 0x4E46
    WM_HOTKEY = 0x0312

    def __init__(self, app: QApplication, callback: Callable[[], None], sequence="Ctrl+Alt+N"):
        super().__init__()
        self._app = app
        self._callback = callback
        self._registered = False
        self._hotkey_id = self.HOTKEY_ID
        self._sequence = ""
        self.set_sequence(sequence)
        app.aboutToQuit.connect(self.unregister)

    @property
    def sequence(self) -> str:
        return self._sequence

    @property
    def registered(self) -> bool:
        return self._registered

    @staticmethod
    def _register_key(hotkey_id, modifiers, key, sequence):
        if not _user32.RegisterHotKey(None, hotkey_id, modifiers, key):
            error = ctypes.get_last_error()
            raise OSError(
                error,
                f"无法注册 {sequence}，快捷键可能被其他程序占用或被系统保留。"
                f"Windows 错误：{ctypes.FormatError(error).strip()}",
            )

    def set_sequence(self, sequence: str) -> None:
        if not isinstance(sequence, str) or not sequence.strip():
            raise ValueError("快捷键不能为空。")
        text = "+".join("Meta" if part.strip().lower() == "win" else part.strip() for part in sequence.split("+"))
        parsed = QKeySequence.fromString(text, QKeySequence.SequenceFormat.PortableText)
        if parsed.count() != 1:
            raise ValueError("请设置一个组合键，不支持连续多段快捷键。")
        combination = parsed[0]
        key = combination.key()
        qt_modifiers = combination.keyboardModifiers()
        allowed_modifiers = (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.MetaModifier
        )
        if qt_modifiers.value & ~allowed_modifiers.value:
            raise ValueError("修饰键只支持 Ctrl、Alt、Shift 和 Win。")
        is_function_key = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            virtual_key = key.value
        elif is_function_key:
            virtual_key = 0x70 + key.value - Qt.Key.Key_F1.value
        elif key in _NAVIGATION_KEYS:
            virtual_key = _NAVIGATION_KEYS[key]
        else:
            raise ValueError("快捷键须包含字母、数字、F1–F24、空格或导航键，不能只有修饰键。")
        if not qt_modifiers and not is_function_key:
            raise ValueError("字母、数字、空格和导航键须搭配 Ctrl、Alt、Shift 或 Win。")
        modifiers = 0x4000  # MOD_NOREPEAT，长按只触发一次。
        key_groups = [(virtual_key,)]
        for qt_modifier, native_modifier, keys in (
            (Qt.KeyboardModifier.ControlModifier, 0x0002, (0x11,)),
            (Qt.KeyboardModifier.AltModifier, 0x0001, (0x12,)),
            (Qt.KeyboardModifier.ShiftModifier, 0x0004, (0x10,)),
            (Qt.KeyboardModifier.MetaModifier, 0x0008, (0x5B, 0x5C)),
        ):
            if qt_modifiers & qt_modifier:
                modifiers |= native_modifier
                key_groups.append(keys)
        canonical = parsed.toString(QKeySequence.SequenceFormat.PortableText)
        if self._registered and (modifiers, virtual_key) != (self._modifiers, self._virtual_key):
            candidate_id = self.HOTKEY_ID + (self._hotkey_id == self.HOTKEY_ID)
            self._register_key(candidate_id, modifiers, virtual_key, canonical)
            if not _user32.UnregisterHotKey(None, self._hotkey_id):
                error = ctypes.get_last_error()
                if not _user32.UnregisterHotKey(None, candidate_id):
                    raise OSError(error, "原快捷键仍保留，临时快捷键注销失败，请重启程序后重试。")
                raise OSError(error, "无法注销原快捷键，已撤销修改，请重试。")
            self._hotkey_id = candidate_id
        self._sequence = canonical
        self._modifiers = modifiers
        self._virtual_key = virtual_key
        self._key_groups = tuple(key_groups)

    def register(self) -> None:
        if self._registered:
            return
        self._register_key(self._hotkey_id, self._modifiers, self._virtual_key, self.sequence)
        self._registered = True
        self._app.installNativeEventFilter(self)

    def unregister(self) -> None:
        if not self._registered:
            return
        if not _user32.UnregisterHotKey(None, self._hotkey_id):
            raise ctypes.WinError(ctypes.get_last_error())
        self._app.removeNativeEventFilter(self)
        self._registered = False

    def is_held(self) -> bool:
        return all(any(_user32.GetAsyncKeyState(key) & 0x8000 for key in group) for group in self._key_groups)

    def is_released(self) -> bool:
        return not any(_user32.GetAsyncKeyState(key) & 0x8000 for group in self._key_groups for key in group)

    def nativeEventFilter(self, event_type, message):
        if self._registered and event_type in (
            b"windows_generic_MSG",
            b"windows_dispatcher_MSG",
        ):
            native_message = wintypes.MSG.from_address(int(message))
            if native_message.message == self.WM_HOTKEY and native_message.wParam == self._hotkey_id:
                self._callback()
                return True, 0
        return False, 0
