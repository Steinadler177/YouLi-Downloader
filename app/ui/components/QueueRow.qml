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
    required property string source

    readonly property bool busy: status === "analyzing" || status === "downloading" || status === "processing"
    readonly property bool failed: status === "error" || status === "cancelled"
    readonly property bool downloading: status === "downloading" || status === "processing"

    width: ListView.view ? ListView.view.width : 800
    height: 58

    function progressText() {
        if (status === "analyzing")
            return "正在分析…"
        if (status === "processing")
            return "合并/转码…"
        if (status === "downloading") {
            if (progress < 0)
                return message || "准备中…"
            const parts = [Math.round(progress * 100) + "%"]
            if (size) parts.push(size)
            if (speed) parts.push(speed)
            if (eta) parts.push("剩余 " + eta)
            return parts.join("  ·  ")
        }
        if (failed)
            return message
        return message
    }

    Rectangle {
        anchors.fill: parent
        color: index % 2 === 0
            ? (Material.theme === Material.Dark ? "#1e2329" : "#f7f9fb")
            : "transparent"
        radius: 6
    }

    // 与表头一致：固定列 + 标题列可拉伸；列间 8px 对应 QueueColHandle 宽度
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: win.queueColumns.margin
        anchors.rightMargin: 6
        anchors.topMargin: 6
        anchors.bottomMargin: 6
        spacing: 0

        Label {
            Layout.preferredWidth: win.queueColumns.seq
            Layout.maximumWidth: win.queueColumns.seq
            text: String(row.seq)
            horizontalAlignment: Text.AlignHCenter
            color: win.subtleText
        }
        Item { Layout.preferredWidth: 8; Layout.maximumWidth: 8 }

        RowLayout {
            Layout.preferredWidth: win.queueColumns.title
            Layout.maximumWidth: win.queueColumns.title
            Layout.fillWidth: false
            spacing: 8

            Rectangle {
                visible: row.source.length > 0
                Layout.preferredWidth: sourceLabel.implicitWidth + 12
                Layout.preferredHeight: 22
                radius: 4
                color: {
                    if (row.source === "B站")
                        return Qt.alpha(Material.color(Material.Pink), 0.18)
                    if (row.source === "YouTube")
                        return Qt.alpha(Material.color(Material.Red), 0.16)
                    return Qt.alpha(Material.color(Material.BlueGrey), 0.18)
                }
                Label {
                    id: sourceLabel
                    anchors.centerIn: parent
                    text: row.source
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: {
                        if (row.source === "B站")
                            return Material.color(Material.Pink)
                        if (row.source === "YouTube")
                            return Material.color(Material.Red)
                        return Material.color(Material.BlueGrey)
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                text: row.title || "（待分析）"
                elide: Text.ElideRight
                font.weight: Font.Medium
                ToolTip.visible: titleHover.hovered
                ToolTip.delay: 400
                ToolTip.text: "地址：" + row.url + (row.params ? "\n参数：" + row.params : "")
                HoverHandler { id: titleHover }
            }
        }
        Item { Layout.preferredWidth: 8; Layout.maximumWidth: 8 }

        Label {
            Layout.preferredWidth: win.queueColumns.preset
            Layout.maximumWidth: win.queueColumns.preset
            text: row.preset
            elide: Text.ElideRight
            font.pixelSize: 12
        }
        Item { Layout.preferredWidth: 8; Layout.maximumWidth: 8 }

        ColumnLayout {
            Layout.preferredWidth: win.queueColumns.status
            Layout.maximumWidth: win.queueColumns.status
            Layout.fillWidth: false
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatusChip { status: row.status }
                Label {
                    Layout.fillWidth: true
                    visible: row.progressText().length > 0
                    text: row.progressText()
                    color: row.failed ? Material.color(Material.Red) : win.subtleText
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    ToolTip.visible: row.failed && errHover.hovered && row.message.length > 0
                    ToolTip.delay: 300
                    ToolTip.text: row.message
                    HoverHandler { id: errHover }
                }
            }
            ProgressBar {
                Layout.fillWidth: true
                Layout.preferredHeight: 5
                from: 0; to: 1
                value: Math.max(0, row.progress)
                visible: row.downloading || row.status === "analyzing"
                indeterminate: row.status === "analyzing" || row.status === "processing"
                               || (row.status === "downloading" && row.progress < 0)
            }
        }
        Item { Layout.preferredWidth: 8; Layout.maximumWidth: 8 }

        RowLayout {
            Layout.preferredWidth: win.queueColumns.actions
            Layout.maximumWidth: win.queueColumns.actions
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
                visible: row.failed && row.message.length > 0
                text: "复制"
                font.pixelSize: 11
                onClicked: backend.copyTaskError(row.taskId)
                ToolTip.visible: hovered; ToolTip.text: "复制错误信息"
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
        Item { Layout.preferredWidth: 8; Layout.maximumWidth: 8 }
        Item { Layout.fillWidth: true }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: (mouse) => {
            if (row.failed && row.message)
                errMenu.popup()
        }
    }
    Menu {
        id: errMenu
        MenuItem {
            text: "复制错误信息"
            onTriggered: backend.copyTaskError(row.taskId)
        }
    }
}
