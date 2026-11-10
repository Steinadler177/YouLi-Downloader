import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

Rectangle {
    id: chip
    property string status: ""

    readonly property var spec: ({
        queued:      { text: "排队",   color: Material.color(Material.Grey) },
        downloading: { text: "下载中", color: Material.color(Material.Blue) },
        processing:  { text: "处理中", color: Material.color(Material.Purple) },
        done:        { text: "完成",   color: Material.color(Material.Teal) },
        error:       { text: "失败",   color: Material.color(Material.Red) },
        cancelled:   { text: "已取消", color: Material.color(Material.BlueGrey) }
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
