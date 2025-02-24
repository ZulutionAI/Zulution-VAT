# 视频标注工具

视频播放器和标注工具，支持简单的视频片段分割、标签标注和关键帧标记。

## 版本信息

- 版本：0.2.1
- 发布日期：2025-02-24

## 功能特点

- 支持可变速度的视频播放控制
- 通过断点进行片段分割
- 片段标签标注（接受/拒绝）并支持自定义原因
- 关键帧标记和导航
- 选定片段的循环播放
- 支持批量处理的播放列表
- 自动状态保存和加载

## 快捷键指南

(在Windows系统中，使用`Ctrl`键；在macOS系统中，使用`Command`键)

### 播放控制
- `空格键` - 播放/暂停
- `Command + 左箭头` - 跳转到视频开始
- `Command + 右箭头` - 跳转到视频结束
- `L` - 切换选定片段的循环播放

### 帧导航
- `左箭头` - 上一帧
- `右箭头` - 下一帧
- `Shift + 左箭头` - 后退10帧
- `Shift + 右箭头` - 前进10帧
- `J` - 跳转到选定片段的起始帧
- `Shift + ,` - 跳转到上一个断点
- `Shift + .` - 跳转到下一个断点
- `,` - 跳转到上一个关键帧
- `.` - 跳转到下一个关键帧

### 片段管理
- `Esc` - 清除所有片段选择
- `A` - 将选定片段标记为接受（片段将被标记为绿色）
- `R` - 将选定片段标记为拒绝（片段将被标记为红色）
- `C` - 清除选定片段的标签
- `D` - 删除片段，将删除选定片段的起始和结束断点

### 断点
- `Command + B` - 在当前帧切换断点

### 关键帧
- `K` - 确认（或取消）当前帧为关键帧

## 配置

工具使用 `config.toml` 文件进行配置：
- 程序基本信息
- 可自定义的接受/拒绝原因

## 使用方法

1. 启动应用程序，创建新的标注文件或打开已有的标注文件
2. 选择视频文件所在目录（程序将自动扫描目录中的视频文件）
3. 使用播放控制导航视频，使用`空格键`播放/暂停
4. 使用`Command + B`添加断点并分割视频片段
5. 使用鼠标点击选择片段，使用`Esc`清除选择
6. 使用`A` / `R`标记选定片段，使用`C`清除片段标签
7. 使用`K`添加（或删除）选定片段的关键帧，使用`,`和`.`导航关键帧
8. 使用`J`跳转到选定片段的起始帧
9. 使用`L`切换选定片段的循环播放
10. 所有更改都会自动保存

## 状态管理

工具会自动保存以下信息：
- 片段，包括标签和接受/拒绝原因、关键帧帧号
- 定义片段起始和结束的断点帧号
- 用于完整性验证的视频文件SHA-256校验和

状态保存在配置的标注文件中，重新打开视频时会自动加载。

---

# Video Annotation Tool

A video player and annotation tool that allows for easy video clip segmentation, labeling, and keyframe marking.

## Versions

- Version: 0.2.1
- Release Date: 2025-02-24

## Features

- Video playback with variable speed control
- Clip segmentation with break points
- Clip labeling (Accept/Reject) with customizable reasons
- Keyframe marking and navigation
- Loop playback for selected clips
- Playlist support for batch processing
- Automatic state saving and loading

## Shortcuts Guide

(In Windows, use `Ctrl` key; in macOS, use `Command` key)

### Playback Control
- `Space` - Play/Pause
- `Command + Left` - Go to video start
- `Command + Right` - Go to video end
- `L` - Toggle loop playback for selected clips

### Frame Navigation
- `Left Arrow` - Previous frame
- `Right Arrow` - Next frame
- `Shift + Left` - Jump 10 frames backward
- `Shift + Right` - Jump 10 frames forward
- `J` - Jump to selected clip's start frame
- `Shift + ,` - Go to previous break point
- `Shift + .` - Go to next break point
- `,` - Go to previous keyframe
- `.` - Go to next keyframe

### Clip Management
- `Esc` - Clear all clips selection
- `A` - Label selected clips as Accept
- `R` - Label selected clips as Reject
- `C` - Clear label of selected clips
- `D` - Delete clips, will delete start and end break points of selected clips

### Break Points
- `Command + B` - Toggle break point at current frame

### Keyframes
- `K` - Toggle keyframe at current frame

## Configuration

The tool uses a `config.toml` file for configuration:  
- Basic information of the program  
- Customizable Accept/Reject reasons  

## Usage

1. Launch the application, create a new annotation file or open an existing annotation file
2. Select the directory containing video files (the program will automatically scan the directory for video files)
3. Use playback controls to navigate through video, use `Space` to play/pause
4. Use `Command + B` to add break points and segment video into clips
5. Use mouse click to select clips, use `Esc` to clear selection
6. Use `A` / `R` to label selected clips, use `C` to clear label of selected clips
7. Use `K` to add (or remove) keyframes for selected clips, use `,` and `.` to navigate through keyframes
8. Use `J` to jump to the start frame of selected clips
9. Use `L` to toggle loop playback for selected clips
10. All changes are automatically saved

## State Management

The tool automatically saves the following information:  
- Clips, with labels and accept / reject reasons, keyframe frame indices  
- Break points, which define the start and end of clips  
- Video file SHA-256 checksums for integrity verification  

States are saved in the configured annotation file and loaded automatically when reopening videos. 