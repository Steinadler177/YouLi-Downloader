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
    width: Math.min(620, parent.width - 48)
    height: Math.min(480, parent.height - 48)
    standardButtons: Dialog.Close
    Material.roundedScale: Material.LargeScale

    readonly property var browsers: ["", "firefox", "chrome", "edge", "brave", "opera", "vivaldi"]
    readonly property var biliApis: ["", "tv", "app"]

    BiliLoginDialog { id: loginDialog }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        TabBar {
            id: tabs
            Layout.fillWidth: true
            TabButton { text: "常规" }
            TabButton { text: "外部工具" }
            TabButton { text: "B 站" }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            // ---- 常规 ----
            ScrollView {
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent ? parent.width - 16 : 400
                    spacing: 12

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 8

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

                        Label { text: "添加后自动开始队列" }
                        Switch {
                            checked: backend.autoStartQueue
                            onToggled: backend.autoStartQueue = checked
                            ToolTip.visible: hovered
                            ToolTip.text: "入队后立刻按顺序分析并下载"
                        }
                    }
                }
            }

            // ---- 外部工具 ----
            ScrollView {
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent ? parent.width - 16 : 400
                    spacing: 12

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 8

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

            // ---- B 站 ----
            ScrollView {
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent ? parent.width - 16 : 400
                    spacing: 12

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 8

                        Label { text: "B 站链接用 BBDownT" }
                        Switch {
                            checked: backend.useBbdownt
                            onToggled: backend.useBbdownt = checked
                            ToolTip.visible: hovered
                            ToolTip.text: "关闭或找不到 BBDownT.exe 时，B 站链接改用 yt-dlp"
                        }

                        Label { text: "解析接口" }
                        ComboBox {
                            Layout.fillWidth: true
                            model: ["WEB（默认）", "TV 端", "APP 端"]
                            currentIndex: Math.max(0, dlg.biliApis.indexOf(backend.biliApi))
                            onActivated: (i) => backend.biliApi = dlg.biliApis[i]
                        }

                        Label { text: "BBDownT" }
                        Label {
                            Layout.fillWidth: true
                            text: backend.bbdowntPath ? backend.bbdowntVersion + "  —  " + backend.bbdowntPath
                                                      : "未找到（放到 bin/BBDownT.exe，或点下方按钮下载）"
                            color: backend.bbdowntPath ? win.subtleText : Material.color(Material.Orange)
                            elide: Text.ElideMiddle
                            wrapMode: backend.bbdowntPath ? Text.NoWrap : Text.Wrap
                        }

                        Label { text: "账号" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Label {
                                text: backend.biliLoggedIn ? "已登录" : "未登录（只能下载公开的非会员清晰度）"
                                color: backend.biliLoggedIn ? Material.color(Material.Teal) : win.subtleText
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Button {
                                flat: true
                                text: backend.biliLoggedIn ? "退出登录" : "扫码登录"
                                enabled: backend.bbdowntPath !== "" && !backend.loginRunning
                                onClicked: {
                                    if (backend.biliLoggedIn) {
                                        backend.biliLogout()
                                    } else {
                                        backend.biliLogin()
                                        loginDialog.open()
                                    }
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Button {
                            text: backend.bbdowntPath ? "更新 BBDownT" : "下载 BBDownT"
                            icon.source: "../icons/refresh.svg"
                            enabled: !backend.bbdowntUpdating
                            onClicked: backend.updateBbdownt()
                        }
                        BusyIndicator {
                            visible: backend.bbdowntUpdating
                            running: visible
                            Layout.preferredWidth: 32
                            Layout.preferredHeight: 32
                        }
                        Label {
                            Layout.fillWidth: true
                            text: backend.bbdowntStatus
                            color: win.subtleText
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }
}
