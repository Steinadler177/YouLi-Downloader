import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// 链接输入 + 解析结果 + 预设选择
Pane {
    id: root
    padding: 16
    Material.elevation: 2
    Material.roundedScale: Material.MediumScale

    readonly property var info: backend.probeInfo
    readonly property bool hasInfo: info && info.title !== undefined && info.url === urlField.text.trim()

    function setUrl(text) {
        urlField.text = text
        backend.probe(text)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
                id: urlField
                Layout.fillWidth: true
                placeholderText: "粘贴视频或播放列表链接，回车解析"
                selectByMouse: true
                onAccepted: backend.probe(text)
            }
            ToolButton {
                icon.source: "../icons/paste.svg"
                onClicked: root.setUrl(backend.clipboardText())
                ToolTip.visible: hovered
                ToolTip.text: "从剪贴板粘贴并解析"
            }
            Button {
                text: "解析"
                icon.source: "../icons/search.svg"
                enabled: urlField.text.trim().length > 0 && !backend.probing
                onClicked: backend.probe(urlField.text)
            }
        }

        // 解析中
        ProgressBar {
            Layout.fillWidth: true
            indeterminate: true
            visible: backend.probing
        }

        // 解析结果
        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            visible: root.hasInfo

            Rectangle {
                Layout.preferredWidth: 192
                Layout.preferredHeight: 108
                radius: 8
                clip: true
                color: Material.theme === Material.Dark ? "#2b3138" : "#e6eaee"
                Image {
                    anchors.fill: parent
                    source: root.hasInfo ? root.info.thumbnail : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 250 } }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Label {
                    Layout.fillWidth: true
                    text: root.hasInfo ? root.info.title : ""
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    color: win.subtleText
                    text: !root.hasInfo ? ""
                        : [root.info.uploader,
                           root.info.isPlaylist ? root.info.count + " 个视频" : root.info.duration]
                          .filter(s => s).join("  ·  ")
                }
                Label {
                    Layout.fillWidth: true
                    visible: root.hasInfo && root.info.heights !== ""
                    color: win.subtleText
                    font.pixelSize: 12
                    text: root.hasInfo ? "可用分辨率：" + root.info.heights : ""
                    elide: Text.ElideRight
                }
                Item { Layout.fillHeight: true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ComboBox {
                id: presetBox
                Layout.preferredWidth: 200
                model: backend.presetNames
                currentIndex: backend.lastPreset
            }
            Label {
                visible: root.hasInfo && root.info.isPlaylist && !backend.downloadPlaylist
                text: "提示：设置中未开启“下载整个播放列表”"
                color: Material.color(Material.Orange)
                font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "下载"
                icon.source: "../icons/download.svg"
                highlighted: true
                enabled: urlField.text.trim().length > 0
                onClicked: {
                    backend.download(urlField.text, presetBox.currentIndex)
                    urlField.clear()
                }
            }
        }
    }
}
