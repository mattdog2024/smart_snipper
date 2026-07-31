# SmartSnipper 智能截图工具

一款轻量级 Windows 截图工具，支持截图后直接标注、画笔、文字，并一键复制或保存。

## 功能特性

- **系统级热键**：组合键使用 Windows `RegisterHotKey` API
- **默认快捷键**：`F2`（低级键盘钩子独占，触发截图时不会再传给当前软件）
- **快速启动截图**：优先使用 `mss` 抓屏，失败时自动回退到 Pillow
- **快捷键持久保存**：设置保存在 `%APPDATA%\SmartSnipper\config.json`，重启后不丢失
- **护眼模式兼容**：自动提亮截图，避免护眼软件导致截图全黑
- **截图标注**：支持画笔涂鸦和文字标注
- **一键复制**：截图直接复制到剪贴板
- **保存到桌面**：截图保存为 PNG 文件到桌面
- **开机自启**：自动添加到 Windows 启动项

## 使用方法

1. 运行 `SmartSnipper.exe`，程序会在系统托盘显示图标
2. 按 `F2`（默认）触发截图
3. 拖动鼠标框选截图区域
4. 松开鼠标后出现工具栏，可进行标注、复制或保存
5. 按 `ESC` 或右键取消截图

## 修改快捷键

右键点击托盘图标 → **设置快捷键** → 输入新快捷键（如 `f2` 或 `ctrl+shift+a`）→ 保存

## 构建

每次推送代码到 `main` 分支，GitHub Actions 会自动构建 `SmartSnipper.exe`，
可在 Actions 页面的 **Artifacts** 中下载。

## 依赖

- Python 3.11+
- pillow
- pystray
- mss
- pyinstaller（仅打包时需要）
