from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, 
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QShortcut, QLineEdit, QStackedLayout
)
from PyQt5.QtGui import QImage, QPixmap, QKeySequence, QPainter, QPen, QColor, QFontMetrics, QLinearGradient
from pathlib import Path

import sys
import os
import av
import numpy as np

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.setFixedSize(1440, 800)
        
        # Video playlist variables
        self.video_list = []
        self.current_video_index = -1
        
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
        right_panel.setFixedWidth(400)
        right_panel.setStyleSheet("QWidget { border: 2px solid orange; }")
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("其他功能区域"))
        
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
        
        # Timeline container (upper half)
        timeline_container = QWidget()
        timeline_container.setFixedHeight(100)
        timeline_container.setStyleSheet("QWidget { border: 1px solid white; background-color: #2b2b2b; }")
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add timeline widget with player reference
        self.timeline_widget = TimelineWidget(self, timeline_container)
        timeline_layout.addWidget(self.timeline_widget)
        
        # Markers container (lower half)
        markers_container = QWidget()
        markers_container.setFixedHeight(100)
        markers_container.setStyleSheet("QWidget { border: 1px solid white; background-color: #2b2b2b; }")
        markers_layout = QVBoxLayout(markers_container)
        markers_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add containers to bottom panel
        bottom_layout.addWidget(timeline_container)
        bottom_layout.addWidget(markers_container)
        
        # Add panels to main layout
        main_layout.addWidget(top_container)
        main_layout.addWidget(bottom_panel)
        
        # Video playback variables
        self.container = None
        self.video_stream = None
        self.audio_stream = None
        self.is_playing = False
        self.current_frame = 0
        self.playback_speed = 1.0
        self.has_ended = False  # New flag to track if video has ended
        
        # Timer for video playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        # Connect signals
        self.play_button.clicked.connect(self.toggle_playback)
        self.start_button.clicked.connect(self.goto_start)
        self.end_button.clicked.connect(self.goto_end)
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        
        # Connect playlist signals
        self.prev_button.clicked.connect(self.play_previous)
        self.next_button.clicked.connect(self.play_next)
        
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
    
    def set_video_list(self, video_files):
        """Set the video playlist and enable/disable navigation buttons."""
        self.video_list = video_files
        self.current_video_index = -1
        self.update_navigation_buttons()
        # Update counter with total videos
        self.video_counter.setText(f"0/{len(self.video_list)}")
    
    def play_video_at_index(self, index):
        """Play the video at the specified index in the playlist."""
        if 0 <= index < len(self.video_list):
            # Stop current playback if any
            if self.is_playing:
                self.timer.stop()
                self.is_playing = False
            
            # Update index and open new video
            logger.info(f"[Player] Playing video at index {index}, file:{self.video_list[index]}")
            self.current_video_index = index
            self.open_video(self.video_list[index])
            
            # Reset playback controls
            self.play_button.setText("▶")
            self.has_ended = False
            
            # Update navigation buttons and counter
            self.update_navigation_buttons()
            self.video_counter.setText(f"{self.current_video_index + 1}/{len(self.video_list)}")
            
            # Note: We don't reset speed_combo as per requirement
    
    def play_previous(self):
        """Play the previous video in the playlist."""
        if self.current_video_index > 0:
            self.play_video_at_index(self.current_video_index - 1)
    
    def play_next(self):
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
                frame_no = int(pts * self.video_stream.average_rate * self.video_stream.time_base)
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
            timestamp = frame_index / (self.video_stream.average_rate * self.video_stream.time_base)
            logger.debug(f"[Player] Seeking to frame {frame_index}, timestamp={timestamp}")
            # Seek to the nearest keyframe before the target frame
            offset = int(timestamp)
            self.container.seek(offset, stream=self.video_stream)
            
            # Update frame counter
            self.current_frame = frame_index
            self.frame_counter.setText(f"{frame_index}/{total_frames}")
            self.timeline_widget.set_current_frame(frame_index)
            logger.debug(f"[Player] Current frame updated to {self.current_frame}")
            
            # Display the frame
            self.update_frame()
            
        except Exception as e:
            logger.error(f"Error seeking to frame: {e}")

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