from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QEventLoop
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, 
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QShortcut,
    QLineEdit, QStackedLayout, QScrollArea, QCheckBox, QDialog, QGroupBox, QRadioButton, QTableWidget, QTableWidgetItem
)
from PyQt5.QtGui import QImage, QPixmap, QKeySequence, QPainter, QPen, QColor, QFontMetrics, QLinearGradient

from typing import Literal, Dict, Any
from pathlib import Path
from collections import OrderedDict
import json

import hashlib
import sys
import os
import av
import numpy as np

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for save/load operations
SAVE_DIR = Path("./save_data")
ANNOTATION_FILE = SAVE_DIR / "annotations.json"

class TimelineWidget(QWidget):
    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self.setMinimumHeight(50)
        self.setMouseTracking(True)
        
        # Timeline properties
        self.total_frames = 0
        self.current_frame = 0
        self.scale_factor = 1.0
        self.min_pixels_per_tick = 50
        
        # Cursor properties
        self.cursor_x = 0
        self.is_dragging = False
        self.cursor_width = 2
        
        # Tick intervals to use (in frames)
        self.tick_intervals = [5, 10, 15, 30, 60, 90]
        
        # Colors and styling
        self.timeline_color = QColor(100, 100, 100)
        self.cursor_color = QColor(0, 255, 255)
        self.tick_color = QColor(200, 200, 200)
        self.text_color = QColor(255, 255, 255)

    def set_total_frames(self, total):
        self.total_frames = total
        self.update()
        
    def set_current_frame(self, frame):
        self.current_frame = frame
        # Calculate cursor position
        if self.total_frames > 0:
            self.cursor_x = int((frame / self.total_frames) * self.width())
        self.update()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.update_cursor_position(event.x())
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
    
    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.update_cursor_position(event.x())
    
    def update_cursor_position(self, x):
        # Constrain cursor within widget bounds
        x = max(0, min(x, self.width()))
        
        # Calculate frame based on cursor position
        if self.total_frames > 0:
            frame = int((x / self.width()) * self.total_frames)
            frame = max(0, min(frame, self.total_frames - 1))
            
            # Update cursor position to exact frame position
            update_x = int((frame / self.total_frames) * self.width())
            if update_x != self.cursor_x:
                logger.debug(f"[Timeline] Cursor moved to x={x}, calculated frame={frame}")
                self.cursor_x = update_x
                self.player.seek_to_frame(frame)
        
        self.update()
    
    def wheelEvent(self, event):
        # Handle zoom with mouse wheel
        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.2
        else:
            self.scale_factor /= 1.2
        
        # Limit zoom range
        self.scale_factor = max(0.1, min(10.0, self.scale_factor))
        self.update()
    
    def paintEvent(self, event):
        if self.total_frames == 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw timeline background
        painter.fillRect(0, 0, self.width(), self.height(), self.timeline_color)
        
        # Draw frame grids
        grid_color = QColor(150, 150, 150, 40)  # Very light gray, semi-transparent
        painter.setPen(QPen(grid_color))
        pixels_per_frame = self.width() / self.total_frames
        
        # Only draw frame grids if they are at least 2 pixels apart
        if pixels_per_frame >= 2:
            for frame in range(self.total_frames):
                x = int(frame * pixels_per_frame)
                painter.drawLine(x, 0, x, self.height())
        
        # Calculate appropriate tick interval
        for interval in self.tick_intervals:
            if pixels_per_frame * interval >= self.min_pixels_per_tick:
                tick_interval = interval
                break
        else:
            tick_interval = self.tick_intervals[-1]
        
        # Draw tick marks and frame numbers
        painter.setPen(QPen(self.tick_color))
        font_metrics = QFontMetrics(painter.font())
        
        for frame in range(0, self.total_frames, tick_interval):
            x = int((frame / self.total_frames) * self.width())
            # Draw tick mark
            painter.drawLine(x, self.height() - 10, x, self.height())
            # Draw frame number
            text = str(frame)
            text_width = font_metrics.width(text)
            painter.drawText(x - text_width//2, self.height() - 15, text)
        
        # Draw cursor rectangle
        cursor_width = max(2, int(self.width() / self.total_frames))  # At least 2 pixels wide
        cursor_color = QColor(self.cursor_color)
        cursor_color.setAlpha(128)  # Make it semi-transparent
        
        # Create gradient for cursor
        gradient = QLinearGradient(self.cursor_x, 0, self.cursor_x + cursor_width, 0)
        gradient.setColorAt(0, cursor_color)
        gradient.setColorAt(0.5, cursor_color)
        gradient.setColorAt(1, QColor(cursor_color.red(), cursor_color.green(), cursor_color.blue(), 0))
        
        # Draw cursor rectangle with gradient
        painter.fillRect(
            self.cursor_x, 
            0, 
            cursor_width, 
            self.height(), 
            gradient
        )
        
        # Draw thin cursor line at exact position
        painter.setPen(QPen(self.cursor_color, 1))
        painter.drawLine(self.cursor_x, 0, self.cursor_x, self.height())

class Clip:
    def __init__(self, start_frame, end_frame):
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.selected = False
        self.label: Literal['Accept', 'Reject'] | None = None
        self.reasons: list[str] = []  # Store reasons for Accept/Reject labels
        
    def contains_frame(self, frame):
        """Check if the clip contains the given frame."""
        return self.start_frame <= frame < self.end_frame
        
    def contains_point(self, x, total_width, total_frames):
        """Check if the clip contains the given x coordinate."""
        start_x = int((self.start_frame / total_frames) * total_width)
        end_x = int((self.end_frame / total_frames) * total_width)
        return start_x <= x < end_x

class ClipsWidget(QWidget):
    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self.setMinimumHeight(60)
        
        # Store cut points and clips
        self.cut_points = []  # List of frame numbers where cuts are made
        self.clips = []  # List of Clip objects
        
        # Colors
        self.clip_color = QColor(128, 128, 128, 128)  # Default grey
        self.selected_color = QColor(255, 255, 224, 128)  # Light yellow for selected
        self.selected_border_color = QColor(135, 206, 235, 200)  # Light blue for selected border
        self.accept_color = QColor(144, 238, 144, 128)  # Light green
        self.reject_color = QColor(255, 182, 193, 128)  # Light red
        self.cut_line_color = QColor(255, 255, 255)  # White
        
        # Enable mouse tracking for selection
        self.setMouseTracking(True)
        
    def clear_selection(self):
        """Clear selection of all clips."""
        selection_changed = False
        for clip in self.clips:
            if clip.selected:
                clip.selected = False
                selection_changed = True
        if selection_changed:
            logger.info("[Clips] Cleared all selections")
            self.update()
            self.player.update_clips_details()
    
    def set_selected_clips_label(self, label):
        """Set the label for all selected clips."""
        label_changed = False
        
        # Get current reasons from the first selected clip
        current_reasons = None
        any_selected = False
        for clip in self.clips:
            if clip.selected:
                any_selected = True
                if clip.label == label:  # Only use reasons if the label matches
                    current_reasons = clip.reasons
                break
        
        # If no selected clips, do nothing
        if not any_selected:
            return
        
        # If setting Accept or Reject label, show reason selection dialog
        selected_reasons = []
        if label in ['Accept', 'Reject']:
            dialog = LabelDetailsDialog(self)
            dialog.set_label_type(label, current_reasons)
            
            # Show dialog and wait for result
            if dialog.exec_() == QDialog.Accepted:
                selected_reasons = dialog.selected_reasons
            else:
                return  # User cancelled, don't proceed with labeling
        
        for clip in self.clips:
            if clip.selected:
                clip.label = label
                if label in ['Accept', 'Reject']:
                    clip.reasons = selected_reasons
                else:  # Clear reasons when clearing label
                    clip.reasons = []
                clip.selected = False
                label_changed = True
                
        if label_changed:
            logger.info(f"[Clips] Set selected clips' label to {label} with reasons: {selected_reasons}")
            self.update()
            self.player.update_clips_details()
    
    def mousePressEvent(self, event):
        if not self.player.video_stream:
            return
            
        if event.button() == Qt.LeftButton:
            # Find which clip was clicked
            for clip in self.clips:
                if clip.contains_point(event.x(), self.width(), self.player.video_stream.frames):
                    clip.selected = not clip.selected
                    self.update()
                    self.player.update_clips_details()
                    break
    
    def toggle_cut_point(self, frame):
        """Toggle a cut point at the specified frame."""
        if frame <= 0:  # Cannot cut at frame 0
            return False
            
        # If cut point exists, remove it
        if frame in self.cut_points:
            logger.info(f"[Clips] Removing cut point at frame {frame}")
            self.cut_points.remove(frame)
            self.update_clips()
            self.update()
            self.player.update_clips_details()
            return True
            
        # Otherwise add new cut point
        logger.info(f"[Clips] Adding cut point at frame {frame}")
        self.cut_points.append(frame)
        self.cut_points.sort()
        self.update_clips()
        self.update()
        self.player.update_clips_details()
        return True
    
    def delete_selected_clips_cut_points(self):
        """Delete cut points of selected clips."""
        if not self.clips:
            return
            
        # Find cut points to remove
        points_to_remove = set()
        for clip in self.clips:
            if clip.selected:
                points_to_remove.add(clip.start_frame)
                points_to_remove.add(clip.end_frame)
        
        # Remove the cut points
        if points_to_remove:
            logger.info(f"[Clips] Removing cut points at frames {points_to_remove}")
            self.cut_points = [pt for pt in self.cut_points if pt not in points_to_remove]
            self.update_clips()
            self.update()
            self.player.update_clips_details()
    
    def clear_state(self):
        """Clear all cut points and clips."""
        logger.info("[Clips] Clearing all cut points and clips")
        self.cut_points = []
        
        # Create initial clip spanning the entire video if video is loaded
        if self.player.video_stream:
            total_frames = self.player.video_stream.frames
            self.clips = [Clip(0, total_frames)]
        else:
            self.clips = []
            
        self.update()
        self.player.update_clips_details()
    
    def update_clips(self):
        if not self.player.video_stream:
            return
            
        total_frames = self.player.video_stream.frames
        
        # Create new clips list while preserving selection and label states
        new_clips = []
        old_clips = {(clip.start_frame, clip.end_frame): (clip.selected, clip.label) for clip in self.clips}
        
        # Create clips from cut points
        last_frame = 0
        for cut_point in self.cut_points:
            clip = Clip(last_frame, cut_point)
            # Restore selection and label states if this clip existed before
            if (last_frame, cut_point) in old_clips:
                clip.selected, clip.label = old_clips[(last_frame, cut_point)]
            new_clips.append(clip)
            last_frame = cut_point
            
        # Add final clip
        final_clip = Clip(last_frame, total_frames)
        if (last_frame, total_frames) in old_clips:
            final_clip.selected, final_clip.label = old_clips[(last_frame, total_frames)]
        new_clips.append(final_clip)
        
        self.clips = new_clips
    
    def paintEvent(self, event):
        if not self.player.video_stream:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        total_frames = self.player.video_stream.frames
        width = self.width()
        height = self.height()
        
        # Draw clips
        for clip in self.clips:
            # Calculate clip rectangle
            x1 = int((clip.start_frame / total_frames) * width)
            x2 = int((clip.end_frame / total_frames) * width)
            rect = QRect(x1, 0, x2 - x1, height)
            
            # Draw clip rectangle with appropriate color
            if clip.selected:
                color = self.selected_color
            else:
                match clip.label:
                    case 'Accept':
                        color = self.accept_color
                    case 'Reject':
                        color = self.reject_color
                    case None:
                        color = self.clip_color
                    
            painter.fillRect(rect, color)
            
            # Draw border for selected clips
            if clip.selected:
                painter.setPen(QPen(self.selected_border_color, 3))
                painter.drawRect(rect)
            
            # Draw frame numbers and labels
            painter.setPen(Qt.white)
            text = f"{clip.start_frame}"
            if clip.label is not None:
                text = f"{text} [{clip.label[0]}]"
            painter.drawText(x1 + 5, height - 5, text)
        
        # Draw cut lines
        painter.setPen(QPen(self.cut_line_color, 2))
        for cut_point in self.cut_points:
            x = int((cut_point / total_frames) * width)
            painter.drawLine(x, 0, x, height)

    def get_first_selected_clip_start_frame(self) -> int | None:
        """Get the start frame of the first selected clip."""
        for clip in self.clips:
            if clip.selected:
                return clip.start_frame
        return None

class FileHash:
    @staticmethod
    def checksum(path: Path, blocks: int = 2**16, mode: Literal['sha256', 'md5'] = 'sha256') -> str:
        hash = hashlib.sha256() if mode == 'sha256' else hashlib.md5()
        with open(path, 'rb') as f:
            while chunk := f.read(blocks):
                hash.update(chunk)
        return hash.hexdigest()

class LabelDetailsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Label Details")
        self.setFixedSize(300, 400)
        self.setModal(True)
        
        # Set light theme style
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QCheckBox, QRadioButton {
                color: black;
                padding: 5px;
            }
            QCheckBox:hover, QRadioButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton {
                padding: 5px 15px;
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QScrollArea {
                border: 1px solid #ddd;
                background-color: white;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 0.5em;
                padding-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
        """)
        
        # Predefined reasons for Accept/Reject
        # Format: str for multi-select options, tuple for single-select group
        self.accept_reasons = [
            "Good lighting",
            "Clear subject",
            ("Composition", [
                "Rule of thirds",
                "Leading lines",
                "Symmetrical balance"
            ]),
            "Emotional impact",
            "Key story moment",
            ("Performance", [
                "Natural acting",
                "Strong emotional delivery",
                "Good physical performance"
            ]),
            "Beautiful scenery"
        ]
        
        self.reject_reasons = [
            "Poor lighting",
            "Blurry/unfocused",
            ("Composition issues", [
                "Unbalanced frame",
                "Distracting elements",
                "Poor framing"
            ]),
            "Uninteresting content",
            "Technical issues",
            ("Acting issues", [
                "Overacting",
                "Unconvincing delivery",
                "Poor timing"
            ]),
            "Redundant scene"
        ]
        
        self.selected_reasons = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Container widget
        container = QWidget()
        container.setStyleSheet("background-color: white;")
        self.checkbox_layout = QVBoxLayout(container)
        self.checkbox_layout.setSpacing(5)
        
        # Store all checkboxes and radio buttons for later access
        self.option_widgets = []
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        layout.addLayout(button_layout)
        
    def set_label_type(self, label_type: Literal['Accept', 'Reject'], current_reasons: list[str] = None):
        """Update options based on label type and set current selections"""
        # Clear existing widgets
        for widget in self.option_widgets:
            self.checkbox_layout.removeWidget(widget)
            widget.deleteLater()
        self.option_widgets.clear()
        
        # Add new options based on label type
        reasons = self.accept_reasons if label_type == 'Accept' else self.reject_reasons
        for reason in reasons:
            if isinstance(reason, str):
                # Create checkbox for multi-select option
                cb = QCheckBox(reason)
                if current_reasons and reason in current_reasons:
                    cb.setChecked(True)
                self.option_widgets.append(cb)
                self.checkbox_layout.addWidget(cb)
            else:
                # Create group box with radio buttons for single-select group
                group_name, options = reason
                group = QGroupBox(group_name)
                group_layout = QVBoxLayout()
                group_layout.setSpacing(2)
                group_layout.setContentsMargins(5, 5, 5, 5)
                
                # Create radio buttons
                for option in options:
                    rb = QRadioButton(option)
                    if current_reasons and option in current_reasons:
                        rb.setChecked(True)
                    group_layout.addWidget(rb)
                    self.option_widgets.append(rb)
                
                group.setLayout(group_layout)
                self.checkbox_layout.addWidget(group)
                self.option_widgets.append(group)
        
        # Add stretch at the end to push everything up
        self.checkbox_layout.addStretch()
    
    def get_selected_reasons(self) -> list[str]:
        """Return list of selected reasons"""
        selected = []
        
        for widget in self.option_widgets:
            if isinstance(widget, QCheckBox) and widget.isChecked():
                selected.append(widget.text())
            elif isinstance(widget, QRadioButton) and widget.isChecked():
                selected.append(widget.text())
            # Skip QGroupBox widgets
        
        return selected
    
    def accept(self):
        self.selected_reasons = self.get_selected_reasons()
        super().accept()
        
    def reject(self):
        self.selected_reasons = []
        super().reject()

class ClipsDetailsWidget(QTableWidget):
    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        
        # Set up the table
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Interval", "Label", "Reasons"])
        
        # Set column widths
        self.setColumnWidth(0, 100)  # Interval column
        self.setColumnWidth(1, 50)   # Label column
        self.setColumnWidth(2, 230)  # Reasons column
        
        # Enable alternating row colors
        self.setAlternatingRowColors(True)
        
        # Set selection behavior
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)  # Only allow single row selection
        
        # Make table read-only
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Store reference to clips for selection sync
        self.clips = []
        
        # Connect selection change signal
        self.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Set style
        self.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f7f7f7;
                border: 1px solid #ddd;
                color: black;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #fff0c0;
                color: black;
                font-style: bold;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ddd;
                font-style: bold;
            }
        """)
    
    def on_selection_changed(self):
        """Handle selection changes in the table."""
        # Clear all clip selections first
        for clip in self.clips:
            clip.selected = False
            
        # Set selected state for the selected row's clip
        selected_rows = self.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            self.clips[row].selected = True
            
        # Update ClipsWidget display
        self.player.clips_widget.update()
    
    def update_clips(self, clips, accept_color, reject_color, clip_color, selected_color):
        """Update the table with current clips data."""
        # Store reference to clips
        self.clips = clips
        
        # Block signals during update to prevent selection feedback loop
        self.blockSignals(True)
        
        self.setRowCount(len(clips))
        selected_row = -1
        
        for i, clip in enumerate(clips):
            # Interval
            interval_item = QTableWidgetItem(f"[{clip.start_frame},{clip.end_frame})")
            interval_item.setTextAlignment(Qt.AlignCenter)
            
            # Label
            label_item = QTableWidgetItem(clip.label[0] if clip.label else "")
            label_item.setTextAlignment(Qt.AlignCenter)
            
            # Reasons
            reasons_item = QTableWidgetItem(", ".join(clip.reasons) if clip.reasons else "")
            reasons_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            # Set items
            self.setItem(i, 0, interval_item)
            self.setItem(i, 1, label_item)
            self.setItem(i, 2, reasons_item)
            
            # Set background color based on state
            if clip.selected:
                color = selected_color
                selected_row = i
            else:
                color = {
                    'Accept': accept_color,
                    'Reject': reject_color,
                    None: clip_color
                }[clip.label]
            
            # Apply color to all cells in the row
            for col in range(3):
                self.item(i, col).setBackground(color)
        
        # Update table selection to match clip selection
        if selected_row >= 0:
            self.selectRow(selected_row)
        else:
            self.clearSelection()
            
        self.blockSignals(False)

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.setFixedSize(1440, 800)
        
        # Video playlist variables
        self.video_list = []
        self.current_video_index = -1
        
        # Annotation state
        self.annotations: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        
        # Create save directory if it doesn't exist
        SAVE_DIR.mkdir(exist_ok=True)
        
        # Setup shortcuts
        self.setup_shortcuts()
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Create top container for left and right panels
        top_container = QWidget()
        top_container.setStyleSheet("QWidget { border: 2px solid blue; }")
        layout = QHBoxLayout(top_container)
        
        # Left panel (Video preview area)
        left_panel = QWidget()
        left_panel.setStyleSheet("QWidget { border: 2px solid red; }")
        left_layout = QVBoxLayout(left_panel)
        
        # Video display
        self.video_label = QLabel()
        self.video_label.setMinimumSize(800, 400)  # Set a reasonable minimum size
        self.video_label.setStyleSheet("QLabel { background-color: black; border: 2px solid white; }")
        self.video_label.setAlignment(Qt.AlignCenter)
        
        # Create a container widget for the video label to center it in the layout
        self.video_container = QWidget()  # Make it an instance variable so we can access it later
        self.video_container.setStyleSheet("QWidget { border: 2px solid yellow; }")
        video_container_layout = QHBoxLayout(self.video_container)
        video_container_layout.addStretch()
        video_container_layout.addWidget(self.video_label)
        video_container_layout.addStretch()
        
        left_layout.addWidget(self.video_container)
        
        # Control buttons
        controls_widget = QWidget()
        controls_widget.setStyleSheet("QWidget { border: 2px solid purple; }")
        controls_layout = QHBoxLayout(controls_widget)
        
        # Create a container for the control buttons
        buttons_container = QWidget()
        buttons_container.setStyleSheet("QWidget { border: 2px solid green; }")
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setSpacing(10)
        
        # Add prev/next video buttons and video counter
        self.prev_button = QPushButton("Prev")
        self.next_button = QPushButton("Next")
        self.prev_button.setEnabled(False)  # Disabled by default
        self.next_button.setEnabled(False)  # Disabled by default
        
        # Add video counter label
        self.video_counter = QLabel("0/0")
        self.video_counter.setStyleSheet("QLabel { color: white; background-color: #444444; padding: 2px 8px; border-radius: 4px; }")
        self.video_counter.setFixedWidth(60)
        self.video_counter.setAlignment(Qt.AlignCenter)
        
        self.start_button = QPushButton("⏮")
        self.play_button = QPushButton("▶")
        self.end_button = QPushButton("⏭")
        
        # Frame counter
        self.frame_counter = QLabel("0/0")
        self.frame_counter.setStyleSheet("QLabel { color: white; background-color: #444444; padding: 2px 8px; border-radius: 4px; }")
        self.frame_counter.setFixedWidth(100)
        self.frame_counter.setAlignment(Qt.AlignCenter)
        
        # Speed control
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.setMinimumWidth(70)  # Set minimum width to fit the text
        self.speed_combo.setFixedWidth(70)    # Fix the width to prevent unwanted resizing
        
        buttons_layout.addWidget(self.prev_button)
        buttons_layout.addWidget(self.video_counter)
        buttons_layout.addWidget(self.next_button)

        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.play_button)
        buttons_layout.addWidget(self.end_button)
        buttons_layout.addWidget(self.frame_counter)
        buttons_layout.addWidget(self.speed_combo)
        
        controls_layout.addStretch(1)
        controls_layout.addWidget(buttons_container)
        controls_layout.addStretch(1)
        
        left_layout.addWidget(controls_widget)
        left_layout.addStretch()
        
        # Right panel (Other functions area)
        right_panel = QWidget()
        right_panel.setFixedWidth(600)
        right_panel.setStyleSheet("QWidget { border: 2px solid orange; }")
        right_layout = QVBoxLayout(right_panel)
        
        # Split right panel into two parts
        clips_details_container = QWidget()
        clips_details_container.setStyleSheet("QWidget { border: 1px solid #ddd; }")
        clips_details_layout = QVBoxLayout(clips_details_container)
        
        # Add clips details table
        self.clips_details = ClipsDetailsWidget(self, clips_details_container)
        clips_details_layout.addWidget(self.clips_details)
        
        keyframes_details_container = QWidget()
        keyframes_details_container.setStyleSheet("QWidget { border: 1px solid #ddd; }")
        keyframes_details_layout = QVBoxLayout(keyframes_details_container)
        keyframes_details_layout.addWidget(QLabel("Keyframes Details"))
        
        # Add both parts to right panel
        right_layout.addWidget(clips_details_container, stretch=1)
        right_layout.addWidget(keyframes_details_container, stretch=1)
        
        # Add panels to layout
        layout.addWidget(left_panel)
        layout.addWidget(right_panel)
        
        # Bottom panel (Editing area)
        bottom_panel = QWidget()
        bottom_panel.setFixedHeight(200)
        bottom_panel.setStyleSheet("QWidget { border: 2px solid cyan; }")
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setSpacing(0)  # Remove spacing between containers
        bottom_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        # Timeline container (60px)
        timeline_container = QWidget()
        timeline_container.setFixedHeight(60)
        timeline_container.setStyleSheet("QWidget { border: 1px solid white; background-color: #2b2b2b; }")
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add timeline widget with player reference
        self.timeline_widget = TimelineWidget(self, timeline_container)
        timeline_layout.addWidget(self.timeline_widget)
        
        # Clips container (60px)
        clips_container = QWidget()
        clips_container.setFixedHeight(60)
        clips_container.setStyleSheet("QWidget { border: 1px solid white; background-color: #2b2b2b; }")
        self.clips_layout = QVBoxLayout(clips_container)
        self.clips_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add clips widget
        self.clips_widget = ClipsWidget(self, clips_container)
        self.clips_layout.addWidget(self.clips_widget)
        
        # Keyframes container (80px)
        keyframes_container = QWidget()
        keyframes_container.setFixedHeight(80)
        keyframes_container.setStyleSheet("QWidget { border: 1px solid white; background-color: #2b2b2b; }")
        keyframes_layout = QVBoxLayout(keyframes_container)
        keyframes_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add containers to bottom panel
        bottom_layout.addWidget(timeline_container)
        bottom_layout.addWidget(clips_container)
        bottom_layout.addWidget(keyframes_container)
        
        # Add panels to main layout
        main_layout.addWidget(top_container)
        main_layout.addWidget(bottom_panel)
        
        # Initialize video playback variables
        self.container = None
        self.video_stream = None
        self.audio_stream = None
        self.current_frame = 0
        self.is_playing = False
        self.has_ended = False
        self.playback_speed = 1.0
        
        # Create timer for video playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        # Connect button signals
        self.play_button.clicked.connect(self.toggle_playback)
        self.start_button.clicked.connect(self.goto_start)
        self.end_button.clicked.connect(self.goto_end)
        self.prev_button.clicked.connect(self.play_prev_video)
        self.next_button.clicked.connect(self.play_next_video)
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        
    def setup_shortcuts(self):
        # Command + Left for goto_start
        shortcut_start = QShortcut(QKeySequence("Ctrl+Left"), self)
        shortcut_start.activated.connect(self.goto_start)
        
        # Command + Right for goto_end
        shortcut_end = QShortcut(QKeySequence("Ctrl+Right"), self)
        shortcut_end.activated.connect(self.goto_end)
        
        # Space for play/pause (as a shortcut)
        shortcut_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        shortcut_play.activated.connect(self.toggle_playback)

        def seek_to_delta_frame(delta):
            return lambda: self.seek_to_frame(self.current_frame + delta)

        # Left, Right, Shift+Left, Shift+Right for seek to frame
        shortcut_prev_frame = QShortcut(QKeySequence(Qt.Key_Left), self)
        shortcut_prev_frame.activated.connect(seek_to_delta_frame(-1))

        shortcut_next_frame = QShortcut(QKeySequence(Qt.Key_Right), self)
        shortcut_next_frame.activated.connect(seek_to_delta_frame(1))

        shortcut_prev_frame_shift = QShortcut(QKeySequence("Shift+Left"), self)
        shortcut_prev_frame_shift.activated.connect(seek_to_delta_frame(-10))

        shortcut_next_frame_shift = QShortcut(QKeySequence("Shift+Right"), self)
        shortcut_next_frame_shift.activated.connect(seek_to_delta_frame(10))

        # Add Command+B shortcut for adding cut point
        shortcut_cutpoint = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut_cutpoint.activated.connect(self.toggle_cut_point)
        
        # Add Delete shortcut for removing selected clips' cut points
        shortcut_delete_clips = QShortcut(QKeySequence(Qt.Key_D), self)
        shortcut_delete_clips.activated.connect(self.delete_selected_clips)
        
        # Add shortcuts for clip labeling
        shortcut_clear_selection = QShortcut(QKeySequence(Qt.Key_Escape), self)
        shortcut_clear_selection.activated.connect(self.clear_clip_selection)
        
        shortcut_set_label_accept = QShortcut(QKeySequence(Qt.Key_A), self)
        shortcut_set_label_accept.activated.connect(lambda: self.set_clips_label('Accept'))
        
        shortcut_set_label_reject = QShortcut(QKeySequence(Qt.Key_R), self)
        shortcut_set_label_reject.activated.connect(lambda: self.set_clips_label('Reject'))
        
        shortcut_clear_label = QShortcut(QKeySequence(Qt.Key_C), self)
        shortcut_clear_label.activated.connect(lambda: self.set_clips_label(None))
        
        # Add J shortcut for jumping to selected clip's start
        shortcut_jump_to_clip_start = QShortcut(QKeySequence(Qt.Key_J), self)
        shortcut_jump_to_clip_start.activated.connect(self.jump_to_selected_clip_start)
    
    def load_annotations(self) -> None:
        """Load annotations from file."""
        try:
            if ANNOTATION_FILE.exists():
                with open(ANNOTATION_FILE, 'r') as f:
                    data = json.load(f)
                    self.annotations = OrderedDict(data)
                logger.info(f"[Player] Loaded annotations from {ANNOTATION_FILE}")
        except Exception as e:
            logger.error(f"[Player] Error loading annotations: {e}")
            self.annotations = OrderedDict()

    def save_annotations(self) -> None:
        """Save annotations to file."""
        try:
            # Save current clips state if we have a video loaded
            if self.current_video_index >= 0:
                current_video = str(self.video_list[self.current_video_index])
                self.annotations[current_video] = self.state_to_dict()
            
            with open(ANNOTATION_FILE, 'w') as f:
                json.dump(self.annotations, f, indent=2)
            logger.info(f"[Player] Saved annotations to {ANNOTATION_FILE}")
        except Exception as e:
            logger.error(f"[Player] Error saving annotations: {e}")

    def state_to_dict(self) -> Dict[str, Any]:
        """Convert current clips state to a dictionary format for storage."""
        clips_data = []
        for clip in self.clips_widget.clips:
            clip_data = {
                'start_frame': clip.start_frame,
                'end_frame': clip.end_frame,
                'label': clip.label,
                'reasons': clip.reasons
            }
            clips_data.append(clip_data)
            
        return {
            'checksum': self.video_file_hash,
            'clips': clips_data,
            'cut_points': self.clips_widget.cut_points
        }
    
    def dict_to_state(self, state_dict: Dict[str, Any]) -> None:
        """Load clips state from a dictionary."""
        # Restore cut points and clips
        self.clips_widget.cut_points = state_dict['cut_points'].copy()
        
        # Create clips from saved state
        self.clips_widget.clips = []
        for clip_data in state_dict['clips']:
            clip = Clip(clip_data['start_frame'], clip_data['end_frame'])
            clip.label = clip_data['label']
            clip.reasons = clip_data['reasons']
            self.clips_widget.clips.append(clip)
        
        # Update displays
        self.clips_widget.update()
        self.update_clips_details()
    
    def update_clips_details(self):
        """Update the clips details table."""
        if hasattr(self, 'clips_details'):
            self.clips_details.update_clips(
                self.clips_widget.clips,
                self.clips_widget.accept_color,
                self.clips_widget.reject_color,
                self.clips_widget.clip_color,
                self.clips_widget.selected_color
            )

    def set_video_list(self, video_files):
        """Set the video playlist and load/initialize annotations."""
        self.video_list = video_files
        self.current_video_index = -1
        
        # Load existing annotations
        self.load_annotations()
        
        self.update_navigation_buttons()
        # Update counter with total videos
        self.video_counter.setText(f"0/{len(self.video_list)}")

    def play_video_at_index(self, index):
        """Play the video at the specified index in the playlist."""
        if 0 <= index < len(self.video_list):
            # Save current clips state before switching
            if self.current_video_index >= 0:
                self.save_current_state()
            
            # Update index and open video first
            self.current_video_index = index
            video_path = str(self.video_list[index])
            
            # Step 1: Open video to get video_stream
            self.open_video(self.video_list[index])
            
            # Step 2: Calculate checksum
            self.video_file_hash = FileHash.checksum(self.video_list[index])
            logger.info(f"[Player] Playing video at index {index}, file:{video_path}, SHA-256:{self.video_file_hash}")
            
            # Step 3 & 4: Check and handle state
            if video_path in self.annotations:
                saved_state = self.annotations[video_path]
                
                # Verify checksum
                if saved_state['checksum'] == self.video_file_hash:
                    # Load saved state if checksum matches
                    logger.info(f"[Player] Loading saved state for {video_path}")
                    self.dict_to_state(saved_state)
                else:
                    # Create new state if checksum doesn't match
                    logger.warning(f"[Player] Video file has changed! Old hash: {saved_state['checksum']}, New hash: {self.video_file_hash}")
                    self.clips_widget.clear_state()
                    self.annotations[video_path] = self.state_to_dict()
            else:
                # Create new state if no previous annotation exists
                logger.info(f"[Player] Creating new state for {video_path}")
                self.clips_widget.clear_state()
                self.annotations[video_path] = self.state_to_dict()
            
            # Reset playback controls
            self.play_button.setText("▶")
            self.has_ended = False
            
            # Update navigation buttons and counter
            self.update_navigation_buttons()
            self.video_counter.setText(f"{self.current_video_index + 1}/{len(self.video_list)}")

    def play_prev_video(self):
        """Play the previous video in the playlist."""
        if self.current_video_index > 0:
            self.play_video_at_index(self.current_video_index - 1)
    
    def play_next_video(self):
        """Play the next video in the playlist."""
        if self.current_video_index < len(self.video_list) - 1:
            self.play_video_at_index(self.current_video_index + 1)
    
    def update_navigation_buttons(self):
        """Update the enabled state of navigation buttons."""
        self.prev_button.setEnabled(self.current_video_index > 0)
        self.next_button.setEnabled(self.current_video_index < len(self.video_list) - 1)
    
    def open_video(self, file_path):
        """Modified to handle both direct file path and Path objects."""
        try:
            # Convert Path object to string if necessary
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            self.container = av.open(file_path)
            self.video_stream = self.container.streams.video[0]
            self.video_stream_frame_per_timestamp = self.video_stream.average_rate * self.video_stream.time_base
            if len(self.container.streams.audio) > 0:
                self.audio_stream = self.container.streams.audio[0]
            
            # Get video dimensions
            width = self.video_stream.width
            height = self.video_stream.height
            
            # Initialize frame counter
            self.current_frame = 0
            total_frames = self.video_stream.frames
            self.frame_counter.setText(f"0/{total_frames}")
            
            # Update timeline
            self.timeline_widget.set_total_frames(total_frames)
            self.timeline_widget.set_current_frame(0)
            
            # Get the actual size of the video container
            container_width = self.video_container.width()
            container_height = self.video_container.height()
            
            # Calculate scaling factor to fit in the container area
            # Account for layout margins and spacing
            available_width = container_width
            available_height = container_height
            
            scale_w = available_width / width
            scale_h = available_height / height
            scale = min(scale_w, scale_h)  # Use the smaller scale to fit both dimensions
            
            # Calculate new dimensions
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # Update video label size
            self.video_label.setFixedSize(new_width, new_height)
            
            self.has_ended = False  # Reset end flag when opening new video
            self.play_button.setText("▶")  # Reset play button text
            self.update_frame()
        except Exception as e:
            logger.error(f"Error opening video: {e}")
    
    def update_frame(self):
        if not self.container:
            return
            
        try:
            frame = None
            # Get frames until we reach the target frame or end of stream
            for f in self.container.decode(video=0):
                frame = f
                pts = frame.pts  # Presentation timestamp
                # Convert pts to frame number using average_rate and time_base
                # NOTE: frame's physical time (in seconds) is `frame_index / average_rate + start_time * time_base`
                # there are two parts:
                #   1. frame_index / average_rate   # unit: second
                #   2. start_time * time_base       # unit: second
                #       i.e. `pts * time_base = frame_index / average_rate + start_time * time_base`
                #       let: `frame_per_timestamp = average_rate * time_base`
                #        => `pts = frame_index / frame_per_timestamp + start_time`
                #        => `frame_index = int((pts - start_time) * frame_per_timestamp)`
                frame_no = int((pts - self.video_stream.start_time) * self.video_stream_frame_per_timestamp)
                logger.debug(f"[Player] Decoded frame pts={pts}, frame_no={frame_no}, target={self.current_frame}")
                
                if frame_no >= self.current_frame:
                    break
            # frame = next(self.container.decode(video=0))
            
            # If no frame is available, we've reached the end
            if frame is None:
                logger.info("[Player] No frame available after seek")
                self.is_playing = False
                self.has_ended = True  # Set the ended flag
                self.play_button.setText("⟳")  # Change to replay symbol
                self.timer.stop()
                return
                
            logger.debug(f"[Player] Frame decoded and about to display, current_frame={self.current_frame}")
            
            # Convert frame to QImage
            image = frame.to_ndarray(format='rgb24')
            h, w = image.shape[:2]
            bytes_per_line = 3 * w
            image = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Scale image to fit the label exactly (we've already calculated the correct size)
            scaled_pixmap = QPixmap.fromImage(image).scaled(
                self.video_label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)
            logger.debug("[Player] Frame displayed successfully")
            
            # Only increment frame counter during normal playback
            if self.is_playing:
                self.current_frame += 1
                self.frame_counter.setText(f"{self.current_frame}/{self.video_stream.frames}")
                self.timeline_widget.set_current_frame(self.current_frame)
                
        except Exception as e:
            logger.error(f"Error updating frame: {e}")
            self.timer.stop()
    
    def toggle_playback(self):
        if self.has_ended:  # If video has ended, restart from beginning
            self.goto_start()
            self.has_ended = False
            self.is_playing = True
            self.play_button.setText("⏸")
            self.timer.start(int(1000 / (self.video_stream.average_rate * self.playback_speed)))
            return

        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_button.setText("⏸")
            self.timer.start(int(1000 / (self.video_stream.average_rate * self.playback_speed)))
        else:
            self.play_button.setText("▶")
            self.timer.stop()
    
    def goto_start(self):
        """Go to the first frame of the video."""
        if self.container:
            self.has_ended = False  # Reset the ended flag
            self.seek_to_frame(0)
            self.play_button.setText("▶")
    
    def goto_end(self):
        """Go to the last frame of the video."""
        if self.container:
            total_frames = self.video_stream.frames
            if total_frames > 0:
                self.has_ended = True
                self.is_playing = False
                self.seek_to_frame(total_frames - 1)
                self.play_button.setText("⟳")
                self.timer.stop()
    
    def change_speed(self, speed_text):
        self.playback_speed = float(speed_text.replace('x', ''))
        if self.is_playing:
            self.timer.setInterval(int(1000 / (self.video_stream.average_rate * self.playback_speed)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # If we have a video loaded, recalculate its size when the window is resized
        if self.container and self.video_stream:
            # Get video dimensions
            width = self.video_stream.width
            height = self.video_stream.height
            
            # Get the actual size of the video container
            container_width = self.video_container.width()
            container_height = self.video_container.height()
            
            # Calculate scaling factor to fit in the container area
            available_width = container_width
            available_height = container_height
            
            scale_w = available_width / width
            scale_h = available_height / height
            scale = min(scale_w, scale_h)
            
            # Calculate new dimensions
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # Update video label size
            self.video_label.setFixedSize(new_width, new_height)

    def seek_to_frame(self, frame_index):
        """Seek to a specific frame index."""
        if not self.container or not self.video_stream:
            return
            
        try:
            # Ensure frame_index is within valid range
            total_frames = self.video_stream.frames
            if frame_index < 0 or frame_index >= total_frames:
                return
                
            # Convert frame index to timestamp using average_rate and time_base
            timestamp = frame_index / self.video_stream_frame_per_timestamp
            logger.debug(f"[Player] Seeking to frame {frame_index}, timestamp={timestamp}")
            # Seek to the nearest keyframe before the target frame
            offset = int(timestamp) + self.video_stream.start_time
            self.container.seek(offset, stream=self.video_stream)
            
            # Update frame counter
            self.current_frame = frame_index
            self.frame_counter.setText(f"{frame_index}/{total_frames}")
            self.timeline_widget.set_current_frame(frame_index)
            logger.debug(f"[Player] Current frame updated to {self.current_frame}")
            
            # Update has_ended based on frame position
            if frame_index < total_frames - 1:
                self.has_ended = False
                if not self.is_playing:
                    self.play_button.setText("▶")
            else:
                self.has_ended = True
                self.play_button.setText("⟳")
            
            # Display the frame
            self.update_frame()
            
        except Exception as e:
            logger.error(f"Error seeking to frame: {e}")

    def toggle_cut_point(self):
        """Toggle a cut point at the current frame position."""
        if not self.container or self.is_playing:
            return
        
        if self.clips_widget.toggle_cut_point(self.current_frame):
            logger.info(f"[Player] Toggled cut point at frame {self.current_frame}")
        else:
            logger.info(f"[Player] Could not toggle cut point at frame {self.current_frame}")

    def delete_selected_clips(self):
        """Delete cut points of selected clips."""
        if self.container and not self.is_playing:
            logger.info(f"[Player] Deleting selected clips' cut points")
            self.clips_widget.delete_selected_clips_cut_points()

    def clear_clip_selection(self):
        """Clear selection of all clips."""
        if self.container and not self.is_playing:
            self.clips_widget.clear_selection()
    
    def set_clips_label(self, label):
        """Set the label for selected clips."""
        if self.container and not self.is_playing:
            self.clips_widget.set_selected_clips_label(label)

    def save_current_state(self) -> None:
        """Save the current state to annotations and file."""
        if self.current_video_index >= 0:
            current_video = str(self.video_list[self.current_video_index])
            self.annotations[current_video] = self.state_to_dict()
            self.save_annotations()

    def closeEvent(self, event):
        """Handle application close event."""
        # Always save state on exit
        self.save_current_state()
        event.accept()

    def jump_to_selected_clip_start(self):
        """Jump to the start frame of the first selected clip."""
        if self.container and not self.is_playing:
            start_frame = self.clips_widget.get_first_selected_clip_start_frame()
            if start_frame is not None:
                logger.info(f"[Player] Jumping to selected clip's start frame: {start_frame}")
                self.seek_to_frame(start_frame)
            else:
                logger.info("[Player] No clip selected to jump to")

if __name__ == '__main__':
    # FOLDER_PATH = "/Users/qiufeng/Downloads/project-v/movii-db/annotate_samples/Life Of Pi (2012) [2160p] [4K] [BluRay] [5.1] [YTS.MX]/clips_nolimit/"
    # FOLDER_PATH = "/Users/qiufeng/Documents/code/imdb-crawler/youtube-crawler/assets/Rifun_official [UCnTiJ-n2KZrXYOI7tqBvP0A]/Highlight/"
    FOLDER_PATH = "/Users/qiufeng/Documents/code/imdb-crawler/youtube-crawler/assets/Rifun_official [UCnTiJ-n2KZrXYOI7tqBvP0A]/test_ffmpeg_i_frame/"
    files = [Path(FOLDER_PATH) / p for p in os.listdir(FOLDER_PATH) if p.endswith(".mp4")]
    
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    
    # Set up the video playlist
    player.set_video_list(files)
    player.play_video_at_index(0)  # Start with the first video
    
    sys.exit(app.exec_())