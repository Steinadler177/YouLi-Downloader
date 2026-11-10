import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// 队列表格中的一行
Item {
    id: row
    required property int index
    required property int seq
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
    required property string params
    required property string item

    readonly property bool busy: status === "analyzing" || status === "downloading" || status === "processing"
    readonly property bool failed: status === "error" || status === "cancelled"

    width: ListView.view ? ListView.view.width : 800
    height: 52

    function statusHint() {
        if (status === "downloading" || status === "processing") {
            if (progress < 0) return message || "准备中…"
            const pct = Math.round(progress * 100) + "%"
            return [pct, size, speed, eta ? "剩余 " + eta : ""].filter(s => s).join("  ")
        }
        if (status === "analyzing") return "正在分析…"
        if (status === "error") return message
        return message
    }

    Rectangle {
        anchors.fill: parent
        color: index % 2 === 0
            ? (Material.theme === Material.Dark ? "#1e2329" : "#f7f9fb")
            : "transparent"
        radius: 6
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 6
        spacing: 8

        Label {
            Layout.preferredWidth: 40
            text: String(row.seq)
            horizontalAlignment: Text.AlignHCenter
            color: win.subtleText
        }
        Label {
            Layout.preferredWidth: 180
            Layout.fillWidth: true
            text: row.title || "（待分析）"
            elide: Text.ElideRight
            font.weight: Font.Medium
        }
        Label {
            Layout.preferredWidth: 160
            Layout.fillWidth: true
            text: row.url
            elide: Text.ElideMiddle
            color: win.subtleText
            font.pixelSize: 12
        }
        Label {
            Layout.preferredWidth: 90
            text: row.preset
            elide: Text.ElideRight
            font.pixelSize: 12
        }
        Label {
            Layout.preferredWidth: 140
            Layout.fillWidth: true
            text: row.params
            elide: Text.ElideRight
            color: win.subtleText
            font.pixelSize: 11
        }
        ColumnLayout {
            Layout.preferredWidth: 130
            spacing: 2
            StatusChip { status: row.status }
            Label {
                visible: row.statusHint().length > 0
                Layout.fillWidth: true
                text: row.statusHint()
                color: row.failed ? Material.color(Material.Red) : win.subtleText
                font.pixelSize: 10
                elide: Text.ElideRight
            }
        }
        RowLayout {
            Layout.preferredWidth: 96
            spacing: 0
            ToolButton {
                visible: row.busy
                icon.source: "../icons/stop.svg"
                onClicked: backend.cancel(row.taskId)
                ToolTip.visible: hovered; ToolTip.text: "取消"
            }
            ToolButton {
                visible: row.failed
                icon.source: "../icons/refresh.svg"
                onClicked: backend.retry(row.taskId)
                ToolTip.visible: hovered; ToolTip.text: "重试"
            }
            ToolButton {
                visible: row.status === "done"
                icon.source: "../icons/folder.svg"
                onClicked: backend.showInFolder(row.taskId)
                ToolTip.visible: hovered; ToolTip.text: "打开目录"
            }
            ToolButton {
                visible: !row.busy
                icon.source: "../icons/close.svg"
                onClicked: backend.remove(row.taskId)
                ToolTip.visible: hovered; ToolTip.text: "移除"
            }
        }
    }

    ProgressBar {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 2
        from: 0; to: 1
        value: Math.max(0, row.progress)
        visible: row.busy && (row.status === "downloading" || row.status === "processing")
        indeterminate: row.status === "processing" || (row.status === "downloading" && row.progress < 0)
    }
}
