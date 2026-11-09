# HoverNote

HoverNote 是一款 Windows 桌面悬浮笔记工具。按住快捷键拖选屏幕区域，即可创建置顶文本框，随手记录想法、待办和临时内容，并以 TXT 或 Markdown 格式保存到本地。

[下载 Windows x64 版 v0.1.0](https://github.com/2509030630/HoverNote/releases/download/v0.1.0/HoverNote-0.1.0-windows-x64.exe)

## 功能

- 快捷键框选区域，原位创建悬浮文本框。
- 文本框保持置顶，可拖动标题栏移动位置，拖动四边、四角或右下角调整大小。
- 支持中文输入、复制粘贴和撤销。
- 支持保存为 `.txt` 和 `.md`，统一使用 UTF-8 编码。
- 提供顶部「文件」「设置」菜单，支持自定义框选快捷键和开机自启动。
- 关闭有未保存内容的窗口或从托盘退出时，会提示保存。

## 快速使用

1. 从 [Releases](https://github.com/2509030630/HoverNote/releases/tag/v0.1.0) 下载 Windows 可执行程序，双击启动；程序驻留系统托盘，无需安装 Python。本地已有的 `悬浮文本框.exe` 也可直接运行。
2. 按住默认快捷键 `Ctrl+Alt+N`，同时按住鼠标左键拖出矩形区域。
3. **先松开鼠标左键，再松开快捷键**，随后在生成的文本框中输入内容。
4. 文本框处于活动状态时，按 `Ctrl+S` 保存；也可通过「文件」菜单或编辑区右键菜单保存为 TXT、Markdown。
5. 退出程序时，右键点击系统托盘图标，选择「退出」。

框选尚未完成时，按 `Esc`、点击鼠标右键或松开框选快捷键，可取消框选。

## 设置

通过窗口顶部的「设置」菜单，或托盘右键菜单中的「设置…」打开设置窗口。

- **框选快捷键**：点击快捷键输入框，按下新的组合键，再点击「保存」。普通按键须搭配 Ctrl、Alt、Shift 或 Win；F1–F24 支持单键设置，实际能否使用取决于系统及其他程序是否占用。`Ctrl+S` 保留用于保存。
- **登录 Windows 后自动启动**：勾选后保存设置，程序将在当前用户登录 Windows 时启动。默认关闭。
- **快捷键冲突**：更改失败时保留原快捷键；启动时若快捷键被占用，可在设置窗口中选择其他组合键。

自启动记录程序的绝对路径。移动程序后，应先退出原实例，从新位置启动，再重新保存自启动设置。

## 仓库结构

EXE 程序通过上方的 Release 下载。

```text
HoverNote/
├─ README.md          使用说明
└─ 源码/
   ├─ app.py          悬浮窗口、框选、菜单及保存逻辑
   ├─ HoverNote.png   图标原图
   ├─ HoverNote.ico   程序图标
   ├─ windows_hotkey.py  Windows 全局快捷键
   ├─ preferences.py  设置窗口
   ├─ startup.py      当前用户自启动配置
   └─ requirements.txt  Python 依赖
```

## 从源码运行

使用 Windows x64 和 Python 3.10 或更新版本，在项目根目录的 PowerShell 中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\源码\requirements.txt
.\.venv\Scripts\python.exe .\源码\app.py
```

运行源码前，请先退出已启动的 EXE，避免占用同一个全局快捷键。

## 当前范围

- 当前提供 Windows x64 版，macOS 尚未适配。
- 一次框选限于起始屏幕，不支持跨屏框选。
- Markdown 按源码编辑和保存，暂不提供实时预览。
- 置顶面向普通桌面窗口，不保证覆盖系统安全界面或其他置顶窗口。
- 内容需要主动保存，暂不提供异常退出后的自动恢复。
