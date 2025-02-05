from typing import List
from tqdm import tqdm
from pathlib import Path

import numpy as np
import cv2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_normalized_flow(prev_frame: np.ndarray, curr_frame: np.ndarray, resize_ratio: int = 4) -> np.ndarray:
    # Resize frames
    h, w = prev_frame.shape[:2]
    new_h, new_w = h // resize_ratio, w // resize_ratio
    prev_frame = cv2.resize(prev_frame, (new_w, new_h))
    curr_frame = cv2.resize(curr_frame, (new_w, new_h))
    
    # Convert frames to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
    
    # Calculate optical flow on resized frames
    flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    
    # Calculate flow magnitude
    magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
    
    # Normalize by diagonal length of the resized frame
    diagonal_length = np.sqrt(new_h**2 + new_w**2)
    normalized_magnitude = magnitude / diagonal_length
    
    return normalized_magnitude

def preprocess_video(video_path: Path, resize_ratio: int = 4) -> List[float]:
    # Open video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Could not open video file: {video_path}")
        raise ValueError("Could not open video file")
    
    # Calculate flow between each frame and its previous frame
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    prev_frame = None
    flow = []
    for frame_idx in tqdm(range(total_frames), desc="Calculating flow"):
        ret, frame = cap.read()
        if not ret:
            break
        
        # Calculate flow between current frame and previous frame
        if prev_frame is not None:
            flow_magnitude = calculate_normalized_flow(prev_frame, frame, resize_ratio)
            max_flow = np.max(flow_magnitude)
            flow.append(max_flow)

        prev_frame = frame.copy()

    cap.release()

    logger.info(f"[cvflow] Calculated optical-flow data for {video_path}, length={len(flow)}")
    return flow
