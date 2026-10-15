"""A small, local-only Eisenhower Matrix desktop widget."""

from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QByteArray, QMimeData, QPoint, Qt
from PyQt6.QtGui import QBrush, QColor, QDrag, QDropEvent, QDragEnterEvent, QDragMoveEvent
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


QUADRANTS = (
    ("DO", "Urgent + Important", "#f87171"),
    ("SCHEDULE", "Not Urgent + Important", "#60a5fa"),
    ("DELEGATE", "Urgent + Not Important", "#fbbf24"),
    ("ELIMINATE", "Not Urgent + Not Important", "#a78bfa"),
)
ID_ROLE = Qt.ItemDataRole.UserRole
SAVED_TITLE_ROLE = Qt.ItemDataRole.UserRole + 1


def database_path() -> Path:
    """Return a stable, per-user location suitable for a packaged application."""
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "EisenhowerWidget" / "tasks_data.db"


class InlineTaskEditor(QLineEdit):
    def __init__(
        self,
        parent: QWidget,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self.setPlaceholderText("Type a task and press Enter")
        self.returnPressed.connect(self._submit)

    def _submit(self) -> None:
        self._on_submit(self.text())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
            event.accept()
            return
        super().keyPressEvent(event)


class TaskTree(QTreeWidget):
    TASK_MIME_TYPE = "application/x-eisenhower-task"
    _active_drags: dict[str, tuple[TaskTree, QTreeWidgetItem]] = {}

    def __init__(self, quadrant_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.quadrant_id = quadrant_id
        self._editor: InlineTaskEditor | None = None
        self._editor_parent: QTreeWidgetItem | None = None
        self._busy = False
        self._persist_callback: Callable[[], None] | None = None

        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setIndentation(18)
        self.setUniformRowHeights(True)
        self.setEditTriggers(QTreeWidget.EditTrigger.EditKeyPressed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.itemChanged.connect(self._item_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_persist_callback(self, callback: Callable[[], None]) -> None:
        self._persist_callback = callback

    def mouseDoubleClickEvent(self, event) -> None:
        self._show_inline_editor(event.position().toPoint())
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Insert:
            self._show_inline_editor(QPoint(8, self.viewport().height() - 34))
            event.accept()
            return
        super().keyPressEvent(event)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        item = self.currentItem()
        if item is None:
            return

        token = uuid.uuid4().hex
        self._active_drags[token] = (self, item)
        mime_data = QMimeData()
        mime_data.setData(self.TASK_MIME_TYPE, QByteArray(token.encode("ascii")))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        try:
            drag.exec(
                supported_actions & Qt.DropAction.MoveAction,
                Qt.DropAction.MoveAction,
            )
        finally:
            self._active_drags.pop(token, None)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._accept_cross_quadrant_drag(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._accept_cross_quadrant_drag(event)

    def _accept_cross_quadrant_drag(self, event) -> None:
        mime_data = event.mimeData()
        if not mime_data.hasFormat(self.TASK_MIME_TYPE):
            event.ignore()
            return

        token = bytes(mime_data.data(self.TASK_MIME_TYPE)).decode("ascii")
        source = self._active_drags.get(token)
        if source is None or source[0] is self:
            event.ignore()
            return

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        mime_data = event.mimeData()
        if not mime_data.hasFormat(self.TASK_MIME_TYPE):
            event.ignore()
            return

        token = bytes(mime_data.data(self.TASK_MIME_TYPE)).decode("ascii")
        source = self._active_drags.get(token)
        if source is None or source[0] is self:
            event.ignore()
            return

        source_tree, item = source
        source_parent = item.parent()
        if source_parent is None:
            source_index = source_tree.indexOfTopLevelItem(item)
            if source_index < 0:
                event.ignore()
                return
            moved_item = source_tree.takeTopLevelItem(source_index)
        else:
            source_index = source_parent.indexOfChild(item)
            if source_index < 0:
                event.ignore()
                return
            moved_item = source_parent.takeChild(source_index)

        self.addTopLevelItem(moved_item)
        self.scrollToItem(moved_item)
        self._style_item(moved_item)
        if self._persist_callback is not None:
            self._persist_callback()
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def _show_inline_editor(
        self, position: QPoint, parent_item: QTreeWidgetItem | None = None
    ) -> None:
        self._close_editor()
        self._editor_parent = parent_item
        editor = InlineTaskEditor(
            self.viewport(), self._add_from_editor, self._close_editor
        )
        self._editor = editor

        available_width = max(80, self.viewport().width() - 16)
        width = min(280, available_width)
        x = min(max(4, position.x()), max(4, self.viewport().width() - width - 4))
        y = min(
            max(4, position.y()),
            max(4, self.viewport().height() - editor.sizeHint().height() - 4),
        )
        editor.setGeometry(x, y, width, editor.sizeHint().height())
        editor.show()
        editor.setFocus()

    def _close_editor(self) -> None:
        editor = self._editor
        self._editor = None
        self._editor_parent = None
        if editor is not None:
            editor.deleteLater()

    def _add_from_editor(self, title: str) -> None:
        clean_title = title.strip()
        parent_item = self._editor_parent
        self._close_editor()
        if not clean_title:
            return

        item = QTreeWidgetItem()
        item.setText(0, clean_title)
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        item.setCheckState(0, Qt.CheckState.Unchecked)
        item.setData(0, SAVED_TITLE_ROLE, clean_title)
        if parent_item is None:
            self.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
            parent_item.setExpanded(True)
        self._style_item(item)
        self.scrollToItem(item)
        if self._persist_callback is not None:
            self._persist_callback()

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.itemAt(position)
        if item is None:
            return

        self.setCurrentItem(item)
        menu = QMenu(self)
        add_subtask = menu.addAction("Add Subtask")
        rename = menu.addAction("Rename Task")
        selected = menu.exec(self.viewport().mapToGlobal(position))
        if selected is add_subtask:
            self._show_inline_editor(
                QPoint(24, self.visualItemRect(item).bottom() + 2), item
            )
        elif selected is rename:
            self.editItem(item, 0)

    def _item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._busy:
            return

        title = item.text(column)
        if not title.strip():
            self._busy = True
            item.setText(column, item.data(0, SAVED_TITLE_ROLE) or "Untitled task")
            self._busy = False
        else:
            item.setData(0, SAVED_TITLE_ROLE, title)

        self._style_item(item)
        self._reorder_siblings(item)
        if self._persist_callback is not None:
            self._persist_callback()

    def _style_item(self, item: QTreeWidgetItem) -> None:
        font = item.font(0)
        completed = item.checkState(0) == Qt.CheckState.Checked
        font.setStrikeOut(completed)
        item.setFont(0, font)
        item.setForeground(
            0, QBrush(QColor("#8c929d" if completed else "#e7eaf0"))
        )

    def _reorder_siblings(self, changed_item: QTreeWidgetItem) -> None:
        parent = changed_item.parent()
        if parent is None:
            siblings = [
                self.topLevelItem(index)
                for index in range(self.topLevelItemCount())
            ]
        else:
            siblings = [parent.child(index) for index in range(parent.childCount())]

        ordered = sorted(
            siblings,
            key=lambda sibling: sibling.checkState(0) == Qt.CheckState.Checked,
        )
        if siblings == ordered:
            return

        self._busy = True
        if parent is None:
            for index in range(self.topLevelItemCount() - 1, -1, -1):
                self.takeTopLevelItem(index)
            for sibling in ordered:
                self.addTopLevelItem(sibling)
        else:
            for index in range(parent.childCount() - 1, -1, -1):
                parent.takeChild(index)
            for sibling in ordered:
                parent.addChild(sibling)
        self._busy = False


class DragHeader(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class EisenhowerWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Eisenhower Matrix")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(720, 500)
        self.resize(820, 600)

        self._db_path = database_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize_database()
        self.quadrant_colors = self._load_quadrant_colors()

        self.trees: list[TaskTree] = []
        self.quadrant_title_labels: list[QLabel] = []
        self.quadrant_markers: list[QFrame] = []
        self._build_ui()
        self._load_tasks()

    def _initialize_database(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quadrant_id INTEGER NOT NULL CHECK (quadrant_id BETWEEN 0 AND 3),
                    parent_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    is_completed INTEGER NOT NULL DEFAULT 0
                        CHECK (is_completed IN (0, 1)),
                    position_order INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quadrant_settings (
                    quadrant_id INTEGER PRIMARY KEY CHECK (quadrant_id BETWEEN 0 AND 3),
                    title_color TEXT NOT NULL
                )
                """
            )
            self._connection.executemany(
                """
                INSERT OR IGNORE INTO quadrant_settings (quadrant_id, title_color)
                VALUES (?, ?)
                """,
                [
                    (quadrant_id, color)
                    for quadrant_id, (_, _, color) in enumerate(QUADRANTS)
                ],
            )

    def _load_quadrant_colors(self) -> list[str]:
        colors = [color for _, _, color in QUADRANTS]
        for quadrant_id, color in self._connection.execute(
            "SELECT quadrant_id, title_color FROM quadrant_settings"
        ):
            if 0 <= quadrant_id < len(colors) and QColor(color).isValid():
                colors[quadrant_id] = color
        return colors

    def _choose_quadrant_color(self, quadrant_id: int) -> None:
        name = QUADRANTS[quadrant_id][0].title()
        color = QColorDialog.getColor(
            QColor(self.quadrant_colors[quadrant_id]),
            self,
            f"Choose {name} title color",
        )
        if not color.isValid():
            return

        color_name = color.name()
        try:
            with self._connection:
                self._connection.execute(
                    """
                    UPDATE quadrant_settings SET title_color = ?
                    WHERE quadrant_id = ?
                    """,
                    (color_name, quadrant_id),
                )
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Could not save settings",
                f"The title color could not be saved:\n{self._db_path}\n\n{error}",
            )
            return

        self.quadrant_colors[quadrant_id] = color_name
        self.quadrant_title_labels[quadrant_id].setStyleSheet(
            f"color: {color_name}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; text-align: left; border: none; padding: 0;"
        )
        self.quadrant_markers[quadrant_id].setStyleSheet(
            f"background: {color_name}; border-radius: 4px;"
        )

    def _build_ui(self) -> None:
        root = QFrame(self)
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 12, 16, 16)
        root_layout.setSpacing(12)

        header = DragHeader(root)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(3, 0, 3, 0)
        title = QWidget(header)
        title_layout = QVBoxLayout(title)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_text = QLabel("EISENHOWER MATRIX")
        title_text.setObjectName("windowTitle")
        subtitle = QLabel("Double-click a quadrant to add a task")
        subtitle.setObjectName("subtitle")
        title_layout.addWidget(title_text)
        title_layout.addWidget(subtitle)
        header_layout.addWidget(title, 1)
        menu_button = QPushButton("\u2630")
        menu_button.setObjectName("menuButton")
        menu_button.setToolTip("Settings")
        menu_button.setFixedSize(30, 30)
        menu_button.clicked.connect(self._show_settings_menu)
        header_layout.addWidget(menu_button)
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setToolTip("Close")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)
        header_layout.addWidget(close_button)
        root_layout.addWidget(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for quadrant_id, (name, description, _) in enumerate(QUADRANTS):
            card = self._create_card(quadrant_id, name, description)
            grid.addWidget(card, quadrant_id // 2, quadrant_id % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        root_layout.addLayout(grid, 1)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(root)
        self.setStyleSheet(
            """
            QWidget { color: #e7eaf0; font-family: "Segoe UI"; }
            QFrame#root { background: rgba(17, 22, 32, 238); border: 1px solid rgba(255,255,255,30); border-radius: 18px; }
            QFrame#quadrantCard { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,18); border-radius: 13px; }
            QLabel#windowTitle { color: #f3f4f6; font-size: 13px; font-weight: 700; }
            QLabel#subtitle { color: #929baa; font-size: 11px; }
            QPushButton#menuButton { color: #aab1bd; background: transparent; border: none; border-radius: 8px; font-size: 18px; }
            QPushButton#menuButton:hover { color: white; background: rgba(255,255,255,24); }
            QPushButton#closeButton { color: #aab1bd; background: transparent; border: none; border-radius: 8px; font-size: 20px; }
            QPushButton#closeButton:hover { color: white; background: rgba(255,255,255,24); }
            QLabel { border: none; background: transparent; }
            QTreeWidget { color: #e7eaf0; background: transparent; border: none; outline: none; padding: 4px 2px; }
            QTreeWidget::item { min-height: 27px; padding: 2px 3px; border-radius: 5px; }
            QTreeWidget::item:hover { background: rgba(255,255,255,12); }
            QTreeWidget::item:selected { background: rgba(96,165,250,45); }
            QTreeWidget::branch { background: transparent; }
            QLineEdit { color: #f3f4f6; background: #252d3b; border: 1px solid #65738a; border-radius: 6px; padding: 5px 7px; }
            QMenu { color: #e7eaf0; background: #252d3b; border: 1px solid #414b5b; }
            QMenu::item:selected { background: #3b4b63; }
            """
        )

    def _show_settings_menu(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return

        menu = QMenu(self)
        colors_menu = menu.addMenu("Change colors")
        if colors_menu is not None:
            for quadrant_id, (name, _, _) in enumerate(QUADRANTS):
                action = colors_menu.addAction(f"{name.title()} title color…")
                if action is None:
                    continue

                def choose_color(selected_id: int) -> Callable[[], None]:
                    def open_dialog() -> None:
                        self._choose_quadrant_color(selected_id)

                    return open_dialog

                action.triggered.connect(choose_color(quadrant_id))
        menu.addSeparator()
        reset_action = menu.addAction("Reset user data")
        if reset_action is not None:
            reset_action.triggered.connect(self._confirm_reset_user_data)
        about_action = menu.addAction("About")
        if about_action is not None:
            about_action.triggered.connect(self._show_about)
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _confirm_reset_user_data(self) -> None:
        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setWindowTitle("Reset user data")
        confirmation.setText(
            "Delete all tasks and subtasks, and reset all quadrant title colors?"
        )
        confirmation.setInformativeText("This action cannot be undone.")
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirmation.exec() == QMessageBox.StandardButton.Yes:
            self._reset_user_data()

    def _reset_user_data(self) -> None:
        default_colors = [color for _, _, color in QUADRANTS]
        try:
            with self._connection:
                self._connection.execute("DELETE FROM tasks")
                self._connection.execute(
                    "DELETE FROM sqlite_sequence WHERE name = 'tasks'"
                )
                self._connection.executemany(
                    """
                    UPDATE quadrant_settings SET title_color = ?
                    WHERE quadrant_id = ?
                    """,
                    [
                        (color, quadrant_id)
                        for quadrant_id, color in enumerate(default_colors)
                    ],
                )
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Could not reset user data",
                f"Your tasks and settings were not reset:\n{self._db_path}\n\n{error}",
            )
            return

        self._loading = True
        for tree in self.trees:
            tree.clear()
        self._loading = False
        self.quadrant_colors = default_colors
        for quadrant_id, color in enumerate(default_colors):
            self.quadrant_title_labels[quadrant_id].setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: 700; "
                "letter-spacing: 1px; text-align: left; border: none; padding: 0;"
            )
            self.quadrant_markers[quadrant_id].setStyleSheet(
                f"background: {color}; border-radius: 4px;"
            )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Eisenhower Matrix",
            """
            <h3>Eisenhower Matrix</h3>
            <p>A lightweight, local-only task tracker for organizing work by
            urgency and importance. Tasks and settings stay in a local SQLite
            database on this computer.</p>
            <p>Licensed under the GNU General Public License, either version 3
            or (at your option) any later version (GPL-3.0-or-later). The license terms are available at
            <a href="https://www.gnu.org/licenses/gpl-3.0.html">gnu.org/licenses/gpl-3.0.html</a>.</p>
            """,
        )

    def _create_card(
        self, quadrant_id: int, name: str, description: str
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("quadrantCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(4)

        heading_row = QHBoxLayout()
        marker = QFrame()
        marker.setFixedSize(8, 8)
        selected_color = self.quadrant_colors[quadrant_id]
        marker.setStyleSheet(
            f"background: {selected_color}; border-radius: 4px;"
        )
        heading_row.addWidget(marker)

        heading = QLabel(name)
        heading.setStyleSheet(
            f"color: {selected_color}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; text-align: left; border: none; padding: 0;"
        )
        heading_row.addWidget(heading)
        heading_row.addStretch()
        layout.addLayout(heading_row)
        self.quadrant_title_labels.append(heading)
        self.quadrant_markers.append(marker)

        detail = QLabel(description)
        detail.setStyleSheet(
            "color: #aab1bd; font-size: 11px; text-align: left; border: none; padding: 0;"
        )
        layout.addWidget(detail)

        tree = TaskTree(quadrant_id, card)
        tree.setStyleSheet("QTreeWidget { border: none; }")
        tree.set_persist_callback(self._persist_all)
        self.trees.append(tree)
        layout.addWidget(tree, 1)
        return card

    def _load_tasks(self) -> None:
        self._loading = True
        rows = self._connection.execute(
            """
            SELECT id, quadrant_id, parent_id, title, is_completed
            FROM tasks
            ORDER BY quadrant_id, parent_id, position_order, id
            """
        ).fetchall()
        items_by_id: dict[int, QTreeWidgetItem] = {}
        for task_id, quadrant_id, parent_id, title, is_completed in rows:
            item = QTreeWidgetItem()
            item.setText(0, title)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEditable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            item.setCheckState(
                0,
                Qt.CheckState.Checked if is_completed else Qt.CheckState.Unchecked,
            )
            item.setData(0, ID_ROLE, task_id)
            item.setData(0, SAVED_TITLE_ROLE, title)
            parent_item = items_by_id.get(parent_id) if parent_id is not None else None
            if parent_item is None:
                self.trees[quadrant_id].addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            items_by_id[task_id] = item
            self.trees[quadrant_id]._style_item(item)
        self._loading = False

    def _persist_all(self) -> None:
        if getattr(self, "_loading", False):
            return

        items: list[tuple[QTreeWidgetItem, int, int | None, int]] = []

        def collect(
            tree: TaskTree,
            item: QTreeWidgetItem,
            parent_id: int | None,
            position: int,
        ) -> None:
            items.append((item, tree.quadrant_id, parent_id, position))
            task_id = item.data(0, ID_ROLE)
            for index in range(item.childCount()):
                collect(tree, item.child(index), task_id, index)

        for tree in self.trees:
            for index in range(tree.topLevelItemCount()):
                collect(tree, tree.topLevelItem(index), None, index)

        known_ids = {
            item.data(0, ID_ROLE)
            for item, _, _, _ in items
            if item.data(0, ID_ROLE) is not None
        }
        try:
            with self._connection:
                existing_ids = [
                    row[0] for row in self._connection.execute("SELECT id FROM tasks")
                ]
                for task_id in existing_ids:
                    if task_id not in known_ids:
                        self._connection.execute(
                            "DELETE FROM tasks WHERE id = ?", (task_id,)
                        )

                for item, quadrant_id, parent_id, position in items:
                    task_id = item.data(0, ID_ROLE)
                    values = (
                        quadrant_id,
                        parent_id,
                        item.text(0),
                        int(item.checkState(0) == Qt.CheckState.Checked),
                        position,
                    )
                    if task_id is None:
                        cursor = self._connection.execute(
                            """
                            INSERT INTO tasks
                                (quadrant_id, parent_id, title, is_completed, position_order)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            values,
                        )
                        item.setData(0, ID_ROLE, cursor.lastrowid)
                    else:
                        self._connection.execute(
                            """
                            UPDATE tasks
                            SET quadrant_id = ?, parent_id = ?, title = ?,
                                is_completed = ?, position_order = ?
                            WHERE id = ?
                            """,
                            (*values, task_id),
                        )
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Could not save tasks",
                f"Changes could not be saved to:\n{self._db_path}\n\n{error}",
            )

    def closeEvent(self, event) -> None:
        self._connection.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    widget = EisenhowerWidget()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
