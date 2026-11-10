import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

ApplicationWindow {
    id: win
    width: 980
    height: 720
    minimumWidth: 640
    minimumHeight: 520
    visible: true
    title: "YTB Downloader"

    Material.theme: backend.darkTheme ? Material.Dark : Material.Light
    Material.accent: Material.Teal
    Material.primary: Material.Teal

    readonly property color subtleText: Material.theme === Material.Dark ? "#9aa5b1" : "#5f6b77"

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
            Label {
                text: "下载队列"
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
            Label {
                text: backend.tasks.count
                color: win.subtleText
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "清除已完成"
                flat: true
                enabled: backend.tasks.count > 0
                onClicked: backend.clearFinished()
            }
        }

        ListView {
            id: taskList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: backend.tasks
            delegate: TaskCard {}
            ScrollBar.vertical: ScrollBar {}

            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 200 }
                NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 200; easing.type: Easing.OutCubic }
            }
            remove: Transition {
                NumberAnimation { property: "opacity"; to: 0; duration: 150 }
            }
            displaced: Transition {
                NumberAnimation { properties: "y"; duration: 200; easing.type: Easing.OutCubic }
            }

            Label {
                anchors.centerIn: parent
                visible: taskList.count === 0
                text: "粘贴或拖入视频链接开始下载"
                color: win.subtleText
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

    // 把链接直接拖进窗口
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
