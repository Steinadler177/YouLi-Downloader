import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

Rectangle {
    id: chip
    property string status: ""

    readonly property var spec: ({
        added:       { text: "已添加",   color: Material.color(Material.Grey) },
        analyzing:   { text: "分析中",   color: Material.color(Material.Indigo) },
        analyzed:    { text: "已分析",   color: Material.color(Material.Cyan) },
        downloading: { text: "正在下载", color: Material.color(Material.Blue) },
        processing:  { text: "正在下载", color: Material.color(Material.Blue) },
        done:        { text: "下载完成", color: Material.color(Material.Teal) },
        error:       { text: "下载失败", color: Material.color(Material.Red) },
        cancelled:   { text: "已取消",   color: Material.color(Material.BlueGrey) },
        // 兼容旧状态
        queued:      { text: "已添加",   color: Material.color(Material.Grey) }
    })[status] || { text: status, color: Material.color(Material.Grey) }

    implicitWidth: label.implicitWidth + 20
    implicitHeight: 24
    radius: height / 2
    color: Qt.alpha(spec.color, 0.18)
    Behavior on color { ColorAnimation { duration: 200 } }

    Label {
        id: label
        anchors.centerIn: parent
        text: chip.spec.text
        color: chip.spec.color
        font.pixelSize: 12
        font.weight: Font.Medium
    }
}
