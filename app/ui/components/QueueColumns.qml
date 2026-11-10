import QtQuick

// 队列表头与行共享列宽（由 Main 实例化一份，QueueRow 通过 QueueColumns 引用）
QtObject {
    id: cols
    readonly property int margin: 10
    readonly property int spacing: 8
    readonly property int seq: 36
    readonly property int preset: 96
    readonly property int status: 240
    readonly property int actions: 120
}
