"""下载任务列表模型，供 QML ListView 使用。"""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Property, Qt, Signal, Slot

ROLES = ["taskId", "url", "title", "status", "progress", "speed", "eta",
         "size", "message", "filepath", "preset", "item"]
_DEFAULTS = {"taskId": 0, "progress": 0.0}
_ROLE_IDS = {name: Qt.UserRole + 1 + i for i, name in enumerate(ROLES)}


class TaskModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    # ---- Qt model API ----
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self):
        return {rid: QByteArray(name.encode()) for name, rid in _ROLE_IDS.items()}

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        name = ROLES[role - Qt.UserRole - 1] if Qt.UserRole < role <= Qt.UserRole + len(ROLES) else None
        if name is None:
            return None
        return self._rows[index.row()].get(name, _DEFAULTS.get(name, ""))

    @Property(int, notify=countChanged)
    def count(self):
        return len(self._rows)

    # ---- updates from DownloadManager ----
    @Slot(int, dict)
    def add(self, task_id: int, fields: dict):
        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append({"taskId": task_id, **fields})
        self.endInsertRows()
        self.countChanged.emit()

    @Slot(int, dict)
    def update(self, task_id: int, fields: dict):
        row = self._find(task_id)
        if row < 0:
            return
        self._rows[row].update(fields)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, [_ROLE_IDS[k] for k in fields if k in _ROLE_IDS])

    @Slot(int)
    def remove(self, task_id: int):
        row = self._find(task_id)
        if row < 0:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._rows[row]
        self.endRemoveRows()
        self.countChanged.emit()

    def get(self, task_id: int) -> dict:
        row = self._find(task_id)
        return dict(self._rows[row]) if row >= 0 else {}

    def _find(self, task_id: int) -> int:
        for i, r in enumerate(self._rows):
            if r["taskId"] == task_id:
                return i
        return -1
