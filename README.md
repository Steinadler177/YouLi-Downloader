# YTB Downloader

基于 PySide6 + QML (Material) 的下载器图形界面。一般网站用 yt-dlp，B 站链接用 [BBDownT](https://github.com/LOVAHE/BBDownT)；
yt-dlp / BBDownT / ffmpeg 都是外部可执行文件，可单独更新。

## 运行

**双击 `start.bat`**。首次运行会自动创建 `.venv` 并安装依赖（有 uv 用 uv，否则用 py/pip），之后直接启动，不弹控制台。

手动方式：

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe run.pyw
```

首次运行若没有 `bin/yt-dlp.exe` / `bin/BBDownT.exe`，在 **设置 → 外部工具 / B 站** 里点对应的“下载”按钮获取；ffmpeg 放进 `bin/` 或系统 PATH。
B 站会员清晰度可在顶栏点「B站 未登录」，或在 **设置 → B 站 → 扫码登录**。

队列支持多行粘贴 / 拖入批量添加、添加后自动开始（设置开关）、关闭后恢复未完成任务（`queue.json`）。
播放列表（YouTube 列表页 / B 站多 P 等）入队分析后会**展开成多条任务**，并保存到下载目录下以列表名命名的子文件夹。

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
    components/         UrlCard、QueueRow、QueueColumns、StatusChip、SettingsDialog、BiliLoginDialog、Toast
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

## 打包成 exe

**双击 `build.bat`**，输出 `dist\YTBDownloader\YTBDownloader.exe`：

```
dist\YTBDownloader\
  YTBDownloader.exe
  _internal\            Python + Qt 运行库（约 112 MB）
  bin\                  从项目 bin\ 复制的 yt-dlp / BBDownT / ffmpeg（只复制 exe，不复制登录信息）
```

- 整个 `dist\YTBDownloader` 文件夹可以直接拷到别的电脑，不需要装 Python。
- 打包版的设置（`config.json`）和 B 站登录（`bin\BBDownT.data`）都在它自己的文件夹里，
  和源码版互不影响，第一次使用需要重新扫码登录。
- `build.bat` 会创建单独的 `.venv-build`，里面只装 `PySide6-Essentials` + PyInstaller。
  不要用开发用的 `.venv` 打包：它是完整 PySide6，会多带约 200 MB 的 QtWebEngine。
- 打包逻辑在 `tools/build.py`：生成图标、PyInstaller 单文件夹打包、删掉没用到的 Qt 文件、复制 `bin\` 工具。
