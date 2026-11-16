import QtQuick

// 队列表头与行共享列宽；表头拖拽分隔条可调节（非 readonly）
QtObject {
    property int margin: 10
    property int spacing: 0   // 分隔条自带间距，行/表头 spacing 用 0
    property int seq: 40
    property int title: 260
    property int preset: 100
    property int status: 240
    property int actions: 120

    readonly property int seqMin: 28
    readonly property int titleMin: 120
    readonly property int presetMin: 72
    readonly property int statusMin: 140
    readonly property int actionsMin: 96

    function resize(name, delta) {
        const mins = {
            seq: seqMin, title: titleMin, preset: presetMin,
            status: statusMin, actions: actionsMin
        }
        const min = mins[name] || 40
        const cur = this[name]
        if (typeof cur !== "number")
            return
        this[name] = Math.max(min, Math.round(cur + delta))
    }
}
