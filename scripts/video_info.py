from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import subprocess
import json
import pandas as pd
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_video_info(video_path: Path) -> Dict:
    """
    使用ffprobe获取视频文件的编码、分辨率、帧率和时长信息
    """
    try:
        # 构建ffprobe命令
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(video_path)
        ]
        
        # 执行命令并获取输出
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        # 初始化默认值
        info = {
            'filename': str(video_path),
            'codec': 'unknown',
            'width': 0,
            'height': 0,
            'fps': 0.0,
            'duration': 0.0
        }
        
        # 从视频流中提取信息
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                info['codec'] = stream.get('codec_name', 'unknown')
                info['width'] = int(stream.get('width', 0))
                info['height'] = int(stream.get('height', 0))
                # 计算帧率
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = map(float, fps_str.split('/'))
                    info['fps'] = num/den if den != 0 else 0.0
                
        # 从格式信息中获取时长
        if 'format' in data and 'duration' in data['format']:
            info['duration'] = float(data['format']['duration'])
        
        logger.debug(f"Processing: {video_path}")
        return info
    except Exception as e:
        logger.error(f"Error processing {video_path}: {str(e)}")
        return None


def process_video_with_progress(video_path: Path) -> Dict:
    """
    包装函数，用于在ThreadPoolExecutor中处理单个视频
    """
    return get_video_info(video_path)


def scan_videos(root_dir: Path, max_workers: int = 16) -> List[Dict]:
    """
    扫描目录下所有的mp4文件并收集信息，使用多线程加速处理
    """
    # 首先收集所有视频文件路径
    video_paths = list(root_dir.rglob('*.mp4'))
    video_infos = []
    
    if not video_paths:
        logger.warning("未找到任何视频文件")
        return video_infos
    
    # 使用ThreadPoolExecutor进行并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 使用tqdm创建进度条
        for info in tqdm(
            executor.map(process_video_with_progress, video_paths),
            total=len(video_paths),
            desc="Processing videos",
            unit="video"
        ):
            if info:
                video_infos.append(info)
    
    return video_infos


if __name__ == '__main__':
    # 设置要扫描的根目录
    root_dir = Path('example_data-v250206.1')  # 可以根据需要修改目录
    
    # 扫描所有视频文件
    logger.info("开始扫描视频文件...")
    video_infos = scan_videos(root_dir)
    
    # 将结果转换为DataFrame并保存为CSV
    if video_infos:
        df = pd.DataFrame(video_infos)
        
        # 保存结果到CSV文件，使用utf-8编码
        output_file = 'video_metadata.csv'
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        # 打印一些基本统计信息
        logger.info("\n基本统计信息:")
        logger.info(f"总视频数: {len(df)}")
        logger.info(f"总时长: {df['duration'].sum()/3600:.2f} 小时")
        logger.info(f"平均时长: {df['duration'].mean()/60:.2f} 分钟")
        logger.info(f"最短视频: {df['duration'].min()/60:.2f} 分钟")
        logger.info(f"最长视频: {df['duration'].max()/60:.2f} 分钟")
        logger.info(f"\n结果已保存到: {output_file}")
    else:
        logger.error("未找到任何视频文件或处理过程中出现错误")