#!/usr/bin/env python3
"""
视频格式转换脚本
将不兼容的视频格式转换为浏览器友好的H.264编码MP4格式
"""

import os
import subprocess
import json
import shutil
from pathlib import Path

def get_video_info(video_path):
    """获取视频文件信息"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"无法获取视频信息 {video_path}: {e}")
        return None

def needs_conversion(video_info):
    """检查视频是否需要转换"""
    if not video_info or 'streams' not in video_info:
        return True
    
    for stream in video_info['streams']:
        if stream.get('codec_type') == 'video':
            codec = stream.get('codec_name', '').lower()
            # 检查是否为浏览器兼容的编码
            if codec not in ['h264', 'avc']:
                return True
    return False

def convert_video(input_path, output_path):
    """转换视频为H.264编码"""
    try:
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',          # 使用H.264编码
            '-preset', 'medium',         # 编码速度与质量平衡
            '-crf', '23',               # 质量设置（18-28，数值越低质量越高）
            '-c:a', 'aac',              # 音频编码（如果有音频）
            '-movflags', '+faststart',   # 优化网络播放
            '-pix_fmt', 'yuv420p',      # 像素格式兼容性
            '-y',                       # 覆盖输出文件
            output_path
        ]
        
        print(f"转换视频: {input_path} -> {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # 验证转换后的文件
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"转换成功: {output_path}")
            return True
        else:
            print(f"转换失败: 输出文件无效")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg错误: {e.stderr}")
        return False
    except Exception as e:
        print(f"转换失败 {input_path}: {e}")
        return False

def convert_videos_in_directory(source_dir, target_dir=None):
    """转换指定目录中的视频"""
    if target_dir is None:
        target_dir = os.path.join(source_dir, 'converted')
    
    if not os.path.exists(source_dir):
        print(f"源目录不存在: {source_dir}")
        return 0
    
    # 创建目标目录
    os.makedirs(target_dir, exist_ok=True)
    
    # 获取所有视频文件
    video_files = [f for f in os.listdir(source_dir) 
                   if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')) 
                   and os.path.isfile(os.path.join(source_dir, f))]
    
    if not video_files:
        print("没有找到视频文件")
        return 0
    
    print(f"找到 {len(video_files)} 个视频文件")
    
    converted_count = 0
    for video_file in video_files:
        input_path = os.path.join(source_dir, video_file)
        
        # 检查视频信息
        video_info = get_video_info(input_path)
        
        if needs_conversion(video_info):
            # 生成输出文件名
            name, ext = os.path.splitext(video_file)
            output_file = f"{name}_h264.mp4"
            output_path = os.path.join(target_dir, output_file)
            
            # 转换视频
            if convert_video(input_path, output_path):
                converted_count += 1
                
        else:
            # 即使是兼容格式，也复制到converted目录以保持一致
            name, ext = os.path.splitext(video_file)
            output_file = f"{name}_h264.mp4"
            output_path = os.path.join(target_dir, output_file)
            
            try:
                shutil.copy2(input_path, output_path)
                print(f"视频已经是兼容格式，复制到输出目录: {video_file}")
                converted_count += 1
            except Exception as e:
                print(f"复制文件失败: {e}")
    
    print(f"转换完成! 成功处理 {converted_count} 个视频文件")
    print(f"转换后的文件保存在: {target_dir}")
    return converted_count

def main():
    """主函数 - 处理输入和输出目录的视频转换"""
    import sys
    
    # 默认处理MAP-Net的输入和输出目录
    input_dir = '/home/vipuser/Downloads/MAP-Net/input'
    output_videos_dir = '/home/vipuser/Downloads/MAP-Net/result/videos'
    
    # 如果提供了命令行参数，使用指定的目录
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    if len(sys.argv) > 2:
        output_videos_dir = sys.argv[2]
    
    print("=" * 50)
    print("开始视频格式转换")
    print("=" * 50)
    
    total_converted = 0
    
    # 转换输入目录的视频
    if os.path.exists(input_dir):
        print(f"\n处理输入目录: {input_dir}")
        input_converted_dir = os.path.join(input_dir, 'converted')
        count = convert_videos_in_directory(input_dir, input_converted_dir)
        total_converted += count
        print(f"输入目录转换完成，共处理 {count} 个文件")
    else:
        print(f"输入目录不存在: {input_dir}")
    
    # 转换输出目录的视频
    if os.path.exists(output_videos_dir):
        print(f"\n处理输出目录: {output_videos_dir}")
        output_converted_dir = os.path.join(output_videos_dir, 'converted')
        count = convert_videos_in_directory(output_videos_dir, output_converted_dir)
        total_converted += count
        print(f"输出目录转换完成，共处理 {count} 个文件")
    else:
        print(f"输出目录不存在: {output_videos_dir}")
    
    print("=" * 50)
    print(f"视频转换任务完成！总共处理了 {total_converted} 个视频文件")
    print("=" * 50)
        
        if needs_conversion(video_info):
            # 生成输出文件名
            name, ext = os.path.splitext(video_file)
            output_file = f"{name}_h264.mp4"
            output_path = os.path.join(converted_dir, output_file)
            
            # 转换视频
            if convert_video(input_path, output_path):
                converted_count += 1
                
                # 可选：替换原文件（谨慎操作）
                # backup_path = os.path.join(video_dir, f"{name}_original{ext}")
                # shutil.move(input_path, backup_path)
                # shutil.move(output_path, input_path)
                
        else:
            print(f"视频已经是兼容格式: {video_file}")
    
    print(f"转换完成! 成功转换 {converted_count} 个视频文件")
    print(f"转换后的文件保存在: {converted_dir}")

if __name__ == "__main__":
    main()
