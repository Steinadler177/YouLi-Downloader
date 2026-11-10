import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material

// 底部轻提示（类似 Flutter 的 SnackBar）
Popup {
    id: toast
    property alias text: label.text

    function show(msg) {
        text = msg
        open()
        timer.restart()
    }

    parent: Overlay.overlay
    x: (parent.width - width) / 2
    y: parent.height - height - 72
    width: Math.min(label.implicitWidth + leftPadding + rightPadding, parent.width - 48)
    padding: 12
    leftPadding: 20
    rightPadding: 20
    closePolicy: Popup.NoAutoClose
    modal: false
    focus: false

    Material.theme: Material.Dark
    Material.roundedScale: Material.SmallScale
    background: Rectangle { radius: 8; color: "#323232" }

    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 150 } }

    Label {
        id: label
        width: Math.min(implicitWidth, toast.parent.width - 48 - toast.leftPadding - toast.rightPadding)
        color: "white"
        elide: Text.ElideRight
    }

    Timer {
        id: timer
        interval: 3000
        onTriggered: toast.close()
    }
}
