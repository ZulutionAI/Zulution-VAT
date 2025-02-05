# Video Annotation Tool

A PyQt-based video player and annotation tool that allows for easy video clip segmentation, labeling, and keyframe marking.

## Features

- Video playback with variable speed control
- Clip segmentation with break points
- Clip labeling (Accept/Reject) with customizable reasons
- Keyframe marking and navigation
- Loop playback for selected clips
- Playlist support for batch processing
- Automatic state saving and loading

## Shortcuts Guide

### Playback Control
- `Space` - Play/Pause
- `Command + Left` - Go to video start
- `Command + Right` - Go to video end
- `L` - Toggle loop playback for selected clips

### Clip Management
- `Up Arrow` - Previous clip
- `Down Arrow` - Next clip
- `Esc` - Clear all clips selection
- `J` - Jump to selected clip's start frame
- `A` - Label selected clips as Accept
- `R` - Label selected clips as Reject
- `C` - Clear label of selected clips

### Frame Navigation
- `Left Arrow` - Previous frame
- `Right Arrow` - Next frame
- `Shift + Left` - Jump 10 frames backward
- `Shift + Right` - Jump 10 frames forward

### Break Points Navigation
- `Command + B` - Toggle break point at current frame
- `Shift + ,` - Go to previous break point
- `Shift + .` - Go to next break point
- `D` - Delete clips, will delete start and end break points of selected clips

### Keyframes Navigation
- `K` - Toggle keyframe at current frame
- `,` - Go to previous keyframe
- `.` - Go to next keyframe
- `Command + G` - Generate keyframes, or clear keyframes for selected clip

## Configuration

The tool uses a `config.toml` file for configuration:  
- Input path for video files  
- Annotation file location  
- Customizable Accept/Reject reasons  

## Usage

1. Launch the application
2. Videos from the configured input directory will be loaded automatically
3. Use playback controls to navigate through video
4. Use `Command + B` to add break points and segment video into clips
5. Select clips and use `A` / `R` to label them
6. Add keyframes using `K` when needed
7. All changes are automatically saved

## State Management

The tool automatically saves the following information:  
- Break points  
- Clip labels and accept / reject reasons  
- Keyframes  
- Video file checksums for integrity verification  

States are saved in the configured annotation file and loaded automatically when reopening videos. 