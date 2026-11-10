import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// B 站扫码登录：显示 BBDownT 生成的二维码，用哔哩哔哩 App 扫描
Dialog {
    id: dlg
    title: "B 站扫码登录"
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(380, parent.width - 48)
    closePolicy: Popup.NoAutoClose
    Material.roundedScale: Material.LargeScale

    // 登录结束（成功/失败/取消）后自动关闭
    Connections {
        target: backend
        function onLoginChanged() {
            if (dlg.opened && !backend.loginRunning)
                closeTimer.restart()
        }
    }
    Timer { id: closeTimer; interval: 1200; onTriggered: dlg.close() }

    footer: DialogButtonBox {
        Button {
            text: backend.loginRunning ? "取消" : "关闭"
            flat: true
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }
        onRejected: {
            if (backend.loginRunning) backend.cancelBiliLogin()
            dlg.close()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 240
            Layout.preferredHeight: 240
            radius: 12
            color: "white"

            Image {
                anchors.fill: parent
                anchors.margins: 8
                source: backend.loginQr
                fillMode: Image.PreserveAspectFit
                smooth: false          // 二维码保持锐利
                cache: false
                visible: backend.loginQr !== ""
            }
            BusyIndicator {
                anchors.centerIn: parent
                running: backend.loginRunning && backend.loginQr === ""
                visible: running
            }
        }

        Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: "打开哔哩哔哩 App → 我的 → 右上角扫一扫"
            color: win.subtleText
            font.pixelSize: 12
        }
        Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: backend.loginStatus
            wrapMode: Text.Wrap
        }
    }
}
