import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window
import "components"

ApplicationWindow {
    id: win
    width: backend.windowW > 0 ? backend.windowW : 1100
    height: backend.windowH > 0 ? backend.windowH : 740
    minimumWidth: 720
    minimumHeight: 520
    visible: true
    title: "YTB Downloader"

    Material.theme: backend.darkTheme ? Material.Dark : Material.Light
    Material.accent: Material.Teal
    Material.primary: Material.Teal

    readonly property color subtleText: Material.theme === Material.Dark ? "#9aa5b1" : "#5f6b77"
    readonly property color headerBg: Material.theme === Material.Dark ? "#252a31" : "#eef2f5"

    // 表头与 QueueRow 共用（必须是 property，子组件 id 在 QueueRow 里访问不到）
    readonly property QtObject queueColumns: QueueColumns {}

    Component.onCompleted: {
        if (backend.windowX >= 0 && backend.windowY >= 0) {
            x = backend.windowX
            y = backend.windowY
        }
        if (backend.windowMaximized)
            showMaximized()
    }

    onClosing: {
        const maximized = visibility === Window.Maximized
        // 最大化时保存恢复前的普通几何更稳妥；这里保存当前（系统会在还原后给出正常值）
        backend.saveWindowGeometry(x, y, width, height, maximized)
    }

    BiliLoginDialog { id: headerLoginDialog }

    // ---------- 顶栏 ----------
    header: Pane {
        padding: 12
        leftPadding: 20
        rightPadding: 12
        Material.elevation: 0
        RowLayout {
            anchors.fill: parent
            spacing: 10
            Image {
                source: "icons/app.svg"
                sourceSize: Qt.size(28, 28)
            }
            Label {
                text: "YTB Downloader"
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true }
            Label {
                text: backend.ytdlpVersion ? "yt-dlp " + backend.ytdlpVersion : "未找到 yt-dlp"
                color: backend.ytdlpVersion ? win.subtleText : Material.color(Material.Red)
                font.pixelSize: 12
            }
            Label {
                text: backend.bbdowntVersion ? "BBDownT " + backend.bbdowntVersion : "未找到 BBDownT"
                color: backend.bbdowntPath ? win.subtleText : Material.color(Material.Orange)
                font.pixelSize: 12
            }
            Label {
                text: backend.biliLoggedIn ? "B站 已登录" : "B站 未登录"
                color: backend.biliLoggedIn ? Material.color(Material.Teal) : win.subtleText
                font.pixelSize: 12
                font.underline: !backend.biliLoggedIn && backend.bbdowntPath !== ""
                MouseArea {
                    anchors.fill: parent
                    cursorShape: (!backend.biliLoggedIn && backend.bbdowntPath !== "")
                                 ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: !backend.biliLoggedIn && backend.bbdowntPath !== ""
                    hoverEnabled: true
                    onClicked: {
                        backend.biliLogin()
                        headerLoginDialog.open()
                    }
                    ToolTip.visible: containsMouse && !backend.biliLoggedIn
                    ToolTip.text: "点击扫码登录"
                }
            }
            ToolButton {
                icon.source: "icons/theme.svg"
                onClicked: backend.darkTheme = !backend.darkTheme
                ToolTip.visible: hovered
                ToolTip.text: "切换深色/浅色"
            }
            ToolButton {
                icon.source: "icons/tune.svg"
                onClicked: settingsDialog.open()
                ToolTip.visible: hovered
                ToolTip.text: "设置"
            }
        }
    }

    // ---------- 主体 ----------
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        anchors.topMargin: 4
        spacing: 16

        UrlCard {
            id: urlCard
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Label {
                text: "下载队列"
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Label {
                text: backend.tasks.count
                color: win.subtleText
            }
            Label {
                visible: backend.queueRunning
                text: "运行中"
                color: Material.color(Material.Teal)
                font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "开始队列"
                highlighted: true
                icon.source: "icons/play.svg"
                enabled: backend.hasPending && !backend.queueRunning
                onClicked: backend.startQueue()
            }
            Button {
                text: "停止队列"
                flat: true
                icon.source: "icons/stop.svg"
                enabled: backend.canStopQueue
                onClicked: backend.stopQueue()
            }
            Button {
                text: "重试失败"
                flat: true
                icon.source: "icons/refresh.svg"
                enabled: backend.failedCount > 0
                onClicked: backend.retryFailed()
            }
            Button {
                text: "清除已完成"
                flat: true
                enabled: backend.tasks.count > 0
                onClicked: backend.clearFinished()
            }
            Button {
                text: "清除队列"
                flat: true
                enabled: backend.tasks.count > 0
                onClicked: backend.clearQueue()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 36
            radius: 6
            color: win.headerBg
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: queueColumns.margin
                anchors.rightMargin: 6
                spacing: 0
                Label {
                    Layout.preferredWidth: queueColumns.seq
                    Layout.maximumWidth: queueColumns.seq
                    text: "#"
                    color: win.subtleText
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                }
                QueueColHandle { columns: queueColumns; target: "seq" }
                Label {
                    Layout.preferredWidth: queueColumns.title
                    Layout.maximumWidth: queueColumns.title
                    text: "视频标题"
                    color: win.subtleText
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
                QueueColHandle { columns: queueColumns; target: "title" }
                Label {
                    Layout.preferredWidth: queueColumns.preset
                    Layout.maximumWidth: queueColumns.preset
                    text: "下载画质"
                    color: win.subtleText
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
                QueueColHandle { columns: queueColumns; target: "preset" }
                Label {
                    Layout.preferredWidth: queueColumns.status
                    Layout.maximumWidth: queueColumns.status
                    text: "状态"
                    color: win.subtleText
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
                QueueColHandle { columns: queueColumns; target: "status" }
                Label {
                    Layout.preferredWidth: queueColumns.actions
                    Layout.maximumWidth: queueColumns.actions
                    text: "操作"
                    color: win.subtleText
                    font.pixelSize: 12
                }
                QueueColHandle { columns: queueColumns; target: "actions" }
                Item { Layout.fillWidth: true }  // 剩余空间，避免列被强行拉伸
            }
        }

        ListView {
            id: taskList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: backend.tasks
            delegate: QueueRow {}
            ScrollBar.vertical: ScrollBar {}

            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 180 }
            }
            remove: Transition {
                NumberAnimation { property: "opacity"; to: 0; duration: 120 }
            }

            Label {
                anchors.centerIn: parent
                visible: taskList.count === 0
                text: "粘贴链接后点「添加」或回车加入队列，再点「开始队列」"
                color: win.subtleText
            }
        }
    }

    // ---------- 合并底栏：工作状态 + 保存目录 ----------
    footer: Pane {
        padding: 8
        leftPadding: 20
        rightPadding: 12
        Material.elevation: 2
        RowLayout {
            anchors.fill: parent
            spacing: 12
            Label {
                text: "工作状态"
                color: win.subtleText
                font.pixelSize: 12
            }
            Label {
                Layout.preferredWidth: 280
                Layout.fillWidth: true
                Layout.maximumWidth: parent.width * 0.45
                text: backend.workStatus
                elide: Text.ElideMiddle
                font.pixelSize: 13
                color: backend.queueRunning
                       ? Material.color(Material.Teal)
                       : (Material.theme === Material.Dark ? "#e8eef4" : "#1f2933")
            }
            ToolSeparator {}
            Label { text: "保存到"; color: win.subtleText; font.pixelSize: 12 }
            Label {
                Layout.fillWidth: true
                text: backend.outputDir
                elide: Text.ElideMiddle
                font.pixelSize: 12
            }
            Button {
                text: "打开"
                flat: true
                icon.source: "icons/folder.svg"
                onClicked: backend.openOutputDir()
            }
            Button {
                text: "更改…"
                flat: true
                onClicked: {
                    folderDialog.currentFolder = backend.outputDirUrl()
                    folderDialog.open()
                }
            }
        }
    }

    FolderDialog {
        id: folderDialog
        title: "选择保存目录"
        onAccepted: backend.setOutputDirUrl(selectedFolder)
    }

    SettingsDialog {
        id: settingsDialog
    }

    Toast {
        id: toast
    }

    Connections {
        target: backend
        function onToast(msg) { toast.show(msg) }
    }

    // 焦点不在输入框时，Ctrl+V 批量入队
    Shortcut {
        sequences: [StandardKey.Paste]
        enabled: !urlCard.inputFocused
        onActivated: urlCard.addFromClipboard()
    }

    DropArea {
        anchors.fill: parent
        onDropped: (drop) => {
            let chunks = []
            if (drop.hasUrls) {
                for (let i = 0; i < drop.urls.length; i++)
                    chunks.push(drop.urls[i].toString())
            }
            if (drop.text)
                chunks.push(drop.text)
            const text = chunks.join("\n").trim()
            if (text) {
                urlCard.addText(text)
                drop.accept()
            }
        }
    }
}
