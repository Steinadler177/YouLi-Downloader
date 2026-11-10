import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// 下载队列中的一项。属性由 TaskModel 的角色注入。
Pane {
    id: card
    required property int index
    required property int taskId
    required property string url
    required property string title
    required property string status
    required property real progress
    required property string speed
    required property string eta
    required property string size
    required property string message
    required property string filepath
    required property string preset
    required property string item

    readonly property bool active: status === "queued" || status === "downloading" || status === "processing"

    width: ListView.view ? ListView.view.width : 400
    padding: 14
    Material.elevation: 1
    Material.roundedScale: Material.SmallScale

    function detailText() {
        switch (status) {
        case "queued": return "等待中 · " + preset
        case "downloading":
            if (progress < 0) return "准备中…" + (message ? "  " + message : "")
            return [Math.round(progress * 100) + "%", size, speed, eta ? "剩余 " + eta : "",
                    item ? message : ""].filter(s => s).join("  ·  ")
        case "processing": return "正在合并 / 转码…" + (item ? "  " + message : "")
        case "done": return filepath || "完成"
        case "cancelled": return "已取消"
        case "error": return message
        }
        return ""
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Label {
                Layout.fillWidth: true
                text: card.title || card.url
                font.weight: Font.Medium
                elide: Text.ElideRight
            }
            StatusChip { status: card.status }

            ToolButton {
                visible: card.active
                icon.source: "../icons/stop.svg"
                onClicked: backend.cancel(card.taskId)
                ToolTip.visible: hovered; ToolTip.text: "取消"
            }
            ToolButton {
                visible: card.status === "error" || card.status === "cancelled"
                icon.source: "../icons/refresh.svg"
                onClicked: backend.retry(card.taskId)
                ToolTip.visible: hovered; ToolTip.text: "重试"
            }
            ToolButton {
                visible: card.status === "done"
                icon.source: "../icons/play.svg"
                onClicked: backend.openFile(card.taskId)
                ToolTip.visible: hovered; ToolTip.text: "打开文件"
            }
            ToolButton {
                visible: card.status === "done"
                icon.source: "../icons/folder.svg"
                onClicked: backend.showInFolder(card.taskId)
                ToolTip.visible: hovered; ToolTip.text: "在文件夹中显示"
            }
            ToolButton {
                visible: !card.active
                icon.source: "../icons/close.svg"
                onClicked: backend.remove(card.taskId)
                ToolTip.visible: hovered; ToolTip.text: "移除"
            }
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: card.active
            from: 0; to: 1
            value: Math.max(0, card.progress)
            indeterminate: card.status === "processing" || (card.status === "downloading" && card.progress < 0)
            Behavior on value { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
        }

        Label {
            Layout.fillWidth: true
            text: card.detailText()
            color: card.status === "error" ? Material.color(Material.Red) : win.subtleText
            font.pixelSize: 12
            elide: Text.ElideMiddle
            wrapMode: card.status === "error" ? Text.Wrap : Text.NoWrap
            maximumLineCount: 3
        }
    }
}
