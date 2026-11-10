import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

ApplicationWindow {
    id: win
    width: 1100
    height: 740
    minimumWidth: 720
    minimumHeight: 520
    visible: true
    title: "YTB Downloader"

    Material.theme: backend.darkTheme ? Material.Dark : Material.Light
    Material.accent: Material.Teal
    Material.primary: Material.Teal

    readonly property color subtleText: Material.theme === Material.Dark ? "#9aa5b1" : "#5f6b77"
    readonly property color headerBg: Material.theme === Material.Dark ? "#252a31" : "#eef2f5"

    // ---------- 顶栏 ----------
    header: Pane {
        padding: 12
        leftPadding: 20
        rightPadding: 12
        Material.elevation: 0
        RowLayout {
            anchors.fill: parent
            spacing: 8
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
                text: "停止"
                flat: true
                icon.source: "icons/stop.svg"
                visible: backend.queueRunning
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
        }

        // 表头
        Rectangle {
            Layout.fillWidth: true
            height: 36
            radius: 6
            color: win.headerBg
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 6
                spacing: 8
                Label { Layout.preferredWidth: 40; text: "#"; color: win.subtleText; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter }
                Label { Layout.preferredWidth: 180; Layout.fillWidth: true; text: "视频标题"; color: win.subtleText; font.pixelSize: 12 }
                Label { Layout.preferredWidth: 160; Layout.fillWidth: true; text: "视频地址"; color: win.subtleText; font.pixelSize: 12 }
                Label { Layout.preferredWidth: 90; text: "下载画质"; color: win.subtleText; font.pixelSize: 12 }
                Label { Layout.preferredWidth: 140; Layout.fillWidth: true; text: "参数"; color: win.subtleText; font.pixelSize: 12 }
                Label { Layout.preferredWidth: 130; text: "状态"; color: win.subtleText; font.pixelSize: 12 }
                Label { Layout.preferredWidth: 96; text: "操作"; color: win.subtleText; font.pixelSize: 12 }
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

        // 当前工作状态（队列表下方）
        Pane {
            Layout.fillWidth: true
            padding: 10
            leftPadding: 14
            rightPadding: 14
            Material.elevation: 1
            Material.roundedScale: Material.SmallScale
            RowLayout {
                anchors.fill: parent
                spacing: 10
                Label {
                    text: "工作状态"
                    color: win.subtleText
                    font.pixelSize: 12
                }
                Label {
                    Layout.fillWidth: true
                    text: backend.workStatus
                    elide: Text.ElideMiddle
                    font.pixelSize: 13
                    color: backend.queueRunning
                           ? Material.color(Material.Teal)
                           : (Material.theme === Material.Dark ? "#e8eef4" : "#1f2933")
                }
            }
        }
    }

    // ---------- 底栏：保存目录 ----------
    footer: Pane {
        padding: 8
        leftPadding: 20
        rightPadding: 12
        Material.elevation: 2
        RowLayout {
            anchors.fill: parent
            spacing: 8
            Label { text: "保存到"; color: win.subtleText }
            Label {
                Layout.fillWidth: true
                text: backend.outputDir
                elide: Text.ElideMiddle
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

    DropArea {
        anchors.fill: parent
        onDropped: (drop) => {
            const text = drop.hasUrls ? drop.urls[0].toString() : drop.text
            if (text) {
                urlCard.setUrl(text.trim())
                drop.accept()
            }
        }
    }
}
