from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, 
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QShortcut, QLineEdit, QStackedLayout
)
from PyQt5.QtGui import QImage, QPixmap, QKeySequence
from pathlib import Path

import sys
import os
import av
import numpy as np

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
        self.speed_combo.addItems(["1.0x", "1.5x", "2.0x", "4.0x"])
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
        bottom_layout.addWidget(QLabel("编辑功能区域"))
        
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
            self.frame_counter.setText(f"{self.current_frame}/{self.video_stream.frames}")
            
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
            print(f"Error opening video: {e}")
    
    def update_frame(self):
        if not self.container:
            return
            
        try:
            frame = None
            # Try to get the next frame
            for f in self.container.decode(video=0):
                frame = f
                break
            
            # If no frame is available, we've reached the end
            if frame is None:
                self.is_playing = False
                self.has_ended = True  # Set the ended flag
                self.play_button.setText("⟳")  # Change to replay symbol
                self.timer.stop()
                return
                
            # Update frame counter
            self.frame_counter.setText(f"{self.current_frame}/{self.video_stream.frames}")
            self.current_frame += 1
            
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
                
        except Exception as e:
            print(f"Error updating frame: {e}")
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
        if self.container:
            self.container.seek(0)
            self.has_ended = False  # Reset the ended flag
            self.current_frame = 0
            self.frame_counter.setText(f"{self.current_frame}/{self.video_stream.frames}")
            self.update_frame()
    
    def goto_end(self):
        if self.container:
            # Get total number of frames
            total_frames = self.container.streams.video[0].frames
            if total_frames > 0:  # If we know the total frames
                # Seek to a few frames before the end to ensure we can decode the last frame
                self.container.seek(total_frames - 2)
                # Decode remaining frames to reach the end
                for frame in self.container.decode(video=0):
                    last_frame = frame
                # Convert and display the last frame
                image = last_frame.to_ndarray(format='rgb24')
                h, w = image.shape[:2]
                bytes_per_line = 3 * w
                image = QImage(image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                scaled_pixmap = QPixmap.fromImage(image).scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
                # Update state
                self.is_playing = False
                self.has_ended = True
                self.current_frame = total_frames - 1
                self.frame_counter.setText(f"{self.current_frame}/{total_frames}")
                self.play_button.setText("⟳")
                self.timer.stop()
    
    def change_speed(self, speed_text):
        self.playback_speed = float(speed_text.replace('x', ''))
        if self.is_playing:
            self.timer.setInterval(int(1000 / (self.video_stream.average_rate * self.playback_speed)))
    
    def keyPressEvent(self, event):
        # We can remove the old shortcut handling since we're using QShortcut now
        super().keyPressEvent(event)

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
                
            # Calculate timestamp based on frame index and frame rate
            timestamp = float(frame_index) / float(self.video_stream.average_rate)
            self.container.seek(int(timestamp * 1000000))  # seek takes microseconds
            
            # Update frame counter
            self.current_frame = frame_index
            self.frame_counter.setText(f"{frame_index}/{total_frames}")
            
            # Display the frame
            self.update_frame()
            
        except Exception as e:
            print(f"Error seeking to frame: {e}")

if __name__ == '__main__':
    # FOLDER_PATH = "/Users/qiufeng/Documents/code/imdb-crawler/youtube-crawler/assets/Rifun_official [UCnTiJ-n2KZrXYOI7tqBvP0A]/Highlight/"
    FOLDER_PATH = "/Users/qiufeng/Downloads/project-v/movii-db/annotate_samples/Life Of Pi (2012) [2160p] [4K] [BluRay] [5.1] [YTS.MX]/clips_nolimit/"
    files = [Path(FOLDER_PATH) / p for p in os.listdir(FOLDER_PATH) if p.endswith(".mp4")]
    
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    
    # Set up the video playlist
    player.set_video_list(files)
    player.play_video_at_index(0)  # Start with the first video
    
    sys.exit(app.exec_())