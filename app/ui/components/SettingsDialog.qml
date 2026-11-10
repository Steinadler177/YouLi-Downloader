import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Dialog {
    id: dlg
    title: "设置"
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(560, parent.width - 48)
    standardButtons: Dialog.Close
    Material.roundedScale: Material.LargeScale

    readonly property var browsers: ["", "firefox", "chrome", "edge", "brave", "opera", "vivaldi"]

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 16
            rowSpacing: 4

            Label { text: "文件名模板" }
            TextField {
                Layout.fillWidth: true
                text: backend.filenameTemplate
                selectByMouse: true
                onEditingFinished: if (text.trim()) backend.filenameTemplate = text.trim()
            }

            Label { text: "浏览器 Cookies" }
            ComboBox {
                Layout.fillWidth: true
                model: dlg.browsers.map(b => b || "不使用")
                currentIndex: Math.max(0, dlg.browsers.indexOf(backend.cookiesBrowser))
                onActivated: (i) => backend.cookiesBrowser = dlg.browsers[i]
            }

            Label { text: "同时下载数" }
            SpinBox {
                from: 1; to: 6
                value: backend.maxConcurrent
                onValueModified: backend.maxConcurrent = value
            }

            Label { text: "下载整个播放列表" }
            Switch {
                checked: backend.downloadPlaylist
                onToggled: backend.downloadPlaylist = checked
            }

            Label { text: "深色主题" }
            Switch {
                checked: backend.darkTheme
                onToggled: backend.darkTheme = checked
            }
        }

        MenuSeparator { Layout.fillWidth: true }

        Label { text: "外部工具"; font.weight: Font.DemiBold }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 16
            rowSpacing: 6

            Label { text: "yt-dlp" }
            Label {
                Layout.fillWidth: true
                text: backend.ytdlpPath ? backend.ytdlpVersion + "  —  " + backend.ytdlpPath : "未找到"
                color: backend.ytdlpPath ? win.subtleText : Material.color(Material.Red)
                elide: Text.ElideMiddle
            }
            Label { text: "ffmpeg" }
            Label {
                Layout.fillWidth: true
                text: backend.ffmpegPath || "未找到（合并音视频、转 MP3 需要它，放到 bin/ 下即可）"
                color: backend.ffmpegPath ? win.subtleText : Material.color(Material.Orange)
                elide: Text.ElideMiddle
                wrapMode: backend.ffmpegPath ? Text.NoWrap : Text.Wrap
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Button {
                text: backend.ytdlpPath ? "更新 yt-dlp" : "下载 yt-dlp"
                icon.source: "../icons/refresh.svg"
                enabled: !backend.updating
                onClicked: backend.updateYtdlp()
            }
            BusyIndicator {
                visible: backend.updating
                running: visible
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
            }
            Label {
                Layout.fillWidth: true
                text: backend.updateStatus
                color: win.subtleText
                font.pixelSize: 12
                elide: Text.ElideRight
            }
        }
    }
}
