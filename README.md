# YTB Downloader

基于 PySide6 + QML (Material) 的下载器图形界面。一般网站用 yt-dlp，B 站链接用 [BBDownT](https://github.com/LOVAHE/BBDownT)；
yt-dlp / BBDownT / ffmpeg 都是外部可执行文件，可单独更新。

## 运行

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe run.pyw
```

首次运行若没有 `bin/yt-dlp.exe` / `bin/BBDownT.exe`，在 **设置** 里点对应的“下载”按钮获取；ffmpeg 放进 `bin/` 或系统 PATH。
B 站会员清晰度需要在 **设置 → B 站 → 扫码登录**。

## 结构

```
bin/                    外部工具（yt-dlp.exe、BBDownT.exe、ffmpeg.exe），替换无需重新打包
app/
  main.py               入口：高 DPI、Material 风格、加载 QML
  core/                 与界面无关的逻辑（不 import QML）
    config.py           路径、用户设置（config.json）
    presets.py          下载预设 → yt-dlp 参数 / BBDownT 选项（加预设改这里）
    command.py          拼 yt-dlp 命令行（纯函数）
    progress.py         解析进度 JSON / 视频信息（纯函数）
    process.py          QProcess 封装：按行读取、结束整个进程树
    manager.py          下载队列：按链接选择 yt-dlp / BBDownT，顺序分析、下载、取消、重试
    bili.py             BBDownT 后端：serve 模式 HTTP API、-info 分析、扫码登录
    updater.py          外部工具版本检查、自更新（-U / --update）、首次下载
  models/task_model.py  队列的 QAbstractListModel
  bridge/backend.py     暴露给 QML 的 `backend` 对象
  ui/                   纯 QML，改界面不用动 Python
    Main.qml
    components/         UrlCard、QueueRow、StatusChip、SettingsDialog、BiliLoginDialog、Toast
    icons/              SVG 图标（高 DPI 下清晰）
```

## 与 yt-dlp 的通信

- 进度：`--progress-template "download:[progress]%(progress)j"`，每行一个 JSON。
- 当前条目 / 最终文件：`--print before_dl:[item]...`、`--print after_move:[done]%(filepath)s`。
- 解析：`yt-dlp -J --flat-playlist`。
- 取消：`taskkill /T /F` 结束 yt-dlp 及其 ffmpeg 子进程。

## 与 BBDownT 的通信

BBDownT 在输出被重定向时不打印进度，所以下载走它的服务器模式：

- 按需启动 `BBDownT serve -l http://127.0.0.1:<随机端口> --server-allow-custom-output`。
- `POST /add-task` 提交（`WorkDir` = 保存目录，清晰度用 `DfnPriority`），`GET /get-tasks/{TaskId}` 轮询进度。
- 分析：`BBDownT <url> -info`，读取 `视频标题: ...`。
- 取消：服务器不支持取消单个任务，取消时结束服务进程，下一个任务自动重启服务。
- “仅音频 MP3”：BBDownT 下载 m4a 后用 ffmpeg 转成 mp3。

## 打包（之后）

```bash
pyinstaller --noconsole --onedir --name YTBDownloader --add-data "app/ui;app/ui" run.pyw
```

打包后把 `bin/` 放在 exe 同级目录。
