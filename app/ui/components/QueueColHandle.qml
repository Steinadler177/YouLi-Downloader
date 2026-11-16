import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// 表头列宽拖拽条：拖动时调节左侧列（target）宽度
Item {
    id: handle
    property var columns
    property string target: ""

    Layout.preferredWidth: 8
    Layout.fillHeight: true
    Layout.minimumWidth: 8
    z: 2

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        width: 2
        height: parent.height - 10
        radius: 1
        color: area.containsMouse || area.pressed
               ? Material.accent
               : (Material.theme === Material.Dark ? "#3a424c" : "#c5ced6")
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        anchors.leftMargin: -4
        anchors.rightMargin: -4
        hoverEnabled: true
        cursorShape: Qt.SizeHorCursor
        preventStealing: true

        property real lastX: 0

        onPressed: (mouse) => {
            lastX = mapToItem(null, mouse.x, 0).x
        }
        onPositionChanged: (mouse) => {
            if (!pressed || !handle.columns || !handle.target)
                return
            const x = mapToItem(null, mouse.x, 0).x
            const dx = x - lastX
            if (dx !== 0) {
                handle.columns.resize(handle.target, dx)
                lastX = x
            }
        }
    }
}
