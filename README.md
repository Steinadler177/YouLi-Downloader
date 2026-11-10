# YTB Downloader

基于 PySide6 + QML (Material) 的 yt-dlp 图形界面。yt-dlp / ffmpeg 作为外部可执行文件，可单独更新。

## 运行

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe run.pyw
```

首次运行若没有 `bin/yt-dlp.exe`，在 **设置 → 下载 yt-dlp** 获取；ffmpeg 放进 `bin/` 或系统 PATH。

## 结构

```
bin/                    外部工具（yt-dlp.exe、ffmpeg.exe），替换无需重新打包
app/
  main.py               入口：高 DPI、Material 风格、加载 QML
  core/                 与界面无关的逻辑（不 import QML）
    config.py           路径、用户设置（config.json）
    presets.py          下载预设 → yt-dlp 参数（加预设改这里）
    command.py          拼 yt-dlp 命令行（纯函数）
    progress.py         解析进度 JSON / 视频信息（纯函数）
    process.py          QProcess 封装：按行读取、结束整个进程树
    manager.py          下载队列：并发、取消、重试
    updater.py          yt-dlp 版本检查、-U 自更新、首次下载
  models/task_model.py  队列的 QAbstractListModel
  bridge/backend.py     暴露给 QML 的 `backend` 对象
  ui/                   纯 QML，改界面不用动 Python
    Main.qml
    components/         UrlCard、TaskCard、StatusChip、SettingsDialog、Toast
    icons/              SVG 图标（高 DPI 下清晰）
```

## 与 yt-dlp 的通信

- 进度：`--progress-template "download:[progress]%(progress)j"`，每行一个 JSON。
- 当前条目 / 最终文件：`--print before_dl:[item]...`、`--print after_move:[done]%(filepath)s`。
- 解析：`yt-dlp -J --flat-playlist`。
- 取消：`taskkill /T /F` 结束 yt-dlp 及其 ffmpeg 子进程。

## 打包（之后）

```bash
pyinstaller --noconsole --onedir --name YTBDownloader --add-data "app/ui;app/ui" run.pyw
```

打包后把 `bin/` 放在 exe 同级目录。
