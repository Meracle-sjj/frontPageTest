from flask import Flask, request, jsonify, send_from_directory, redirect, send_file, Response
from flask_cors import CORS
import uuid
import subprocess
import os
import json
from datetime import datetime
import glob
import base64
import io
import zipfile
import mimetypes
import re


app = Flask(__name__)
# 设置最大上传文件大小为 1GB
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB
CORS(app)

# 存储不同模块的上传图片信息
uploaded_data = {
    'infrared': {'images': []},     # 红外模块
    'image': {'images': []},        # 图像模块  
    'lidar': {'images': []},        # 雷达模块
    'video': {'images': []}         # 视频模块
}

# 模块配置
MODULE_CONFIG = {
    'infrared': {
        'name': '红外数据合成模块',
        'input_dir': '/home/vipuser/Downloads/RGB2TIR/input',
        'output_dir': '/home/vipuser/Downloads/RGB2TIR/output',
        'script_path': '/home/vipuser/Downloads/RGB2TIR/run_inference.sh',
        'supported_formats': ['.jpg', '.jpeg', '.png', '.bmp']
    },
    'image': {
        'name': '图像数据合成模块',
        'input_dir': '/home/vipuser/Downloads/ImageSynthesis/input',
        'output_dir': '/home/vipuser/Downloads/ImageSynthesis/output', 
        'script_path': '/home/vipuser/Downloads/ImageSynthesis/run_inference.sh',
        'supported_formats': ['.jpg', '.jpeg', '.png', '.bmp']
    },
    'lidar': {
        'name': '雷达数据合成模块',
        'input_dir': '/home/vipuser/Downloads/LidarSynthesis/input',
        'output_dir': '/home/vipuser/Downloads/LidarSynthesis/output',
        'script_path': '/home/vipuser/Downloads/LidarSynthesis/run_inference.sh', 
        'supported_formats': ['.pcd', '.las', '.xyz', '.ply']
    },
    'video': {
        'name': '视频数据合成模块',
        'input_dir': '/home/vipuser/Downloads/MAP-Net/input',
        'output_dir': '/home/vipuser/Downloads/MAP-Net/result',
        'script_path': '/home/vipuser/Downloads/MAP-Net/run_mapnet.sh',
        'supported_formats': ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
    }
}

@app.route('/')
def home():
    """重定向到主页面"""
    return redirect('/index.html')

@app.route('/index.html')
def index_page():
    """提供主页面"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """提供静态文件服务"""
    if filename.endswith(('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.mp4')):
        return send_from_directory('.', filename)
    else:
        return "File not found", 404

@app.route('/result/videos/<filename>')
def serve_video_results(filename):
    """提供视频结果文件服务"""
    video_output_dir = '/home/vipuser/Downloads/MAP-Net/result/videos'
    # 也检查主结果目录
    main_output_dir = '/home/vipuser/Downloads/MAP-Net/result'
    
    # 首先检查 videos 子目录
    if os.path.exists(os.path.join(video_output_dir, filename)):
        return send_from_directory(video_output_dir, filename)
    # 然后检查主目录
    elif os.path.exists(os.path.join(main_output_dir, filename)):
        return send_from_directory(main_output_dir, filename)
    else:
        return "Video file not found", 404

@app.route('/api/')
def api_info():
    """API信息接口"""
    return jsonify({
        'message': '欢迎使用数据合成平台后端服务',
        'platform': '中科大测试项目 - 多模态数据合成平台',
        'version': '1.0',
        'services': {
            'infrared_generation': {
                'name': '红外数据合成模块',
                'responsible': '杨涵青',
                'intro_page': '/infra_index.html',
                'trial_page': '/trial.html',
                'status': 'active'
            }
        },
        'api_endpoints': {
            'upload': 'POST /upload - 上传图片（红外生成服务）',
            'upload_status': 'GET /upload_status - 检查上传状态', 
            'run_inference': 'POST /run_inference - 运行红外生成推理',
            'clear_cache': 'POST /clear_cache - 清除缓存',
            'clear_cuda': 'POST /clear_cuda - 清理CUDA显存'
        }
    })

@app.route('/platform_status', methods=['GET'])
def platform_status():
    """获取平台各模块的状态信息"""
    return jsonify({
        'platform_name': '中科大测试项目 - 多模态数据合成平台',
        'last_updated': '2024-08-05',
        'modules': {
            'image_synthesis': {
                'name': '图像数据合成模块',
                'responsible': '李齐彪',
                'status': 'working',
                'intro_page': 'image_index.html',
                'trial_available': False
            },
            'lidar_synthesis': {
                'name': '雷达数据合成模块', 
                'responsible': '黄非凡',
                'status': 'working',
                'intro_page': 'lidar_index.html',
                'trial_available': False
            },
            'video_synthesis': {
                'name': '视频数据合成模块',
                'responsible': '杨涵青', 
                'status': 'active',
                'intro_page': 'video_index.html',
                'trial_page': 'image_trial.html',
                'trial_available': True
            },
            'infrared_synthesis': {
                'name': '红外数据合成模块',
                'responsible': '杨涵青',
                'status': 'active',
                'intro_page': 'infra_index.html',
                'trial_page': 'trial.html',
                'trial_available': True
            }
        }
    })

# 通用上传函数
def handle_module_upload(module_name):
    """处理指定模块的文件上传"""
    if module_name not in MODULE_CONFIG:
        return jsonify({'error': f'不支持的模块: {module_name}'}), 400
    
    file = request.files.get('file') or request.files.get('image')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400
    
    config = MODULE_CONFIG[module_name]
    input_dir = config['input_dir']
    supported_formats = config['supported_formats']
    
    # 创建输入目录
    os.makedirs(input_dir, exist_ok=True)
    
    # 检查文件格式
    original_filename = file.filename or 'unnamed'
    file_extension = os.path.splitext(original_filename)[1].lower()
    
    if file_extension not in supported_formats:
        return jsonify({
            'error': f'{config["name"]}不支持此文件格式。支持的格式: {", ".join(supported_formats)}'
        }), 400
    
    # 生成唯一的文件名
    unique_filename = f'{uuid.uuid4().hex}{file_extension}'
    save_path = os.path.join(input_dir, unique_filename)
    
    try:
        file.save(save_path)
        
        # 将新文件信息添加到对应模块的列表中
        file_info = {
            'filename': unique_filename,
            'original_name': original_filename,
            'upload_time': datetime.now().isoformat(),
            'path': save_path,
            'module': module_name
        }
        
        uploaded_data[module_name]['images'].append(file_info)
        
        return jsonify({
            'msg': f'文件已保存到{config["name"]}: {unique_filename}',
            'filename': unique_filename,
            'original_name': original_filename,
            'module': module_name,
            'total_images': len(uploaded_data[module_name]['images'])
        })
    except Exception as e:
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

# 模块化的上传API路由
@app.route('/upload/<module_name>', methods=['POST'])
def upload_to_module(module_name):
    """模块化上传接口"""
    return handle_module_upload(module_name)

# 为了向后兼容，保持原有的 /upload 接口（默认为红外模块）
@app.route('/upload', methods=['POST'])
def upload():
    """红外数据合成模块 - 上传图片接口（向后兼容）"""
    return handle_module_upload('infrared')

@app.route('/run_inference', methods=['POST'])
def run_inference():
    """红外数据合成模块 - 执行RGB到红外转换推理（向后兼容）"""
    return run_module_inference('infrared')

@app.route('/run_inference/<module_name>', methods=['POST'])
def run_module_inference(module_name):
    """模块化推理接口"""
    if module_name not in MODULE_CONFIG:
        return jsonify({'error': f'不支持的模块: {module_name}'}), 400
    
    config = MODULE_CONFIG[module_name]
    
    try:
        # 检查用户是否上传了文件
        if not uploaded_data[module_name]['images']:
            return jsonify({'error': f'请先上传文件到{config["name"]}再执行推理！'}), 400
        
        print(f"开始对 {len(uploaded_data[module_name]['images'])} 个文件执行{config['name']}推理...")
        
        # 检查所有上传的文件是否还存在
        missing_files = []
        for file_info in uploaded_data[module_name]['images']:
            if not os.path.exists(file_info['path']):
                missing_files.append(file_info['original_name'])
        
        if missing_files:
            return jsonify({'error': f'以下文件不存在，请重新上传：{", ".join(missing_files)}'}), 400
        
        # 检查脚本文件是否存在
        script_path = config['script_path']
        if not os.path.exists(script_path):
            return jsonify({'error': f'脚本文件不存在: {script_path}'}), 500
        
        # 清空输出目录
        output_dir = config['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        for existing_file in glob.glob(os.path.join(output_dir, "*")):
            if os.path.isfile(existing_file):
                os.remove(existing_file)
        
        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)
        
        # 添加CUDA显存清理的环境变量
        env = os.environ.copy()
        env['CUDA_EMPTY_CACHE'] = '1'
        env['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'
        
        result = subprocess.run(
            ['/bin/bash', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,  # 增加超时时间到10分钟
            cwd=os.path.dirname(script_path),
            env=env
        )
        
        output = result.stdout.decode('utf-8')
        error = result.stderr.decode('utf-8')
        
        print(f"脚本执行完成，返回码: {result.returncode}")
        print(f"输出: {output}")
        if error:
            print(f"错误: {error}")
        
        # 查找生成的结果文件
        result_files = []
        print(f"检查输出目录: {output_dir}")
        
        # 扫描输出目录中的文件
        if os.path.exists(output_dir):
            for file_path in glob.glob(os.path.join(output_dir, "**/*"), recursive=True):
                if os.path.isfile(file_path):
                    relative_path = os.path.relpath(file_path, output_dir)
                    filename = os.path.basename(file_path)
                    file_size = os.path.getsize(file_path)
                    
                    # 对于视频模块，检查是否为视频文件
                    if module_name == 'video':
                        # 检查文件扩展名
                        _, ext = os.path.splitext(filename.lower())
                        if ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']:
                            result_files.append({
                                'filename': filename,
                                'relative_path': relative_path,
                                'full_path': file_path,
                                'size': file_size
                            })
                    else:
                        # 对于其他模块，添加所有文件
                        result_files.append({
                            'filename': filename,
                            'relative_path': relative_path,
                            'full_path': file_path,
                            'size': file_size
                        })
            
            print(f"找到 {len(result_files)} 个结果文件: {[f['filename'] for f in result_files]}")
        
        # 获取所有原始文件的名称
        original_files = [file['original_name'] for file in uploaded_data[module_name]['images']]
        
        # 为了向后兼容，红外模块使用旧的字段名
        result_key = 'result_images' if module_name == 'infrared' else 'result_files'
        original_key = 'original_images' if module_name == 'infrared' else 'original_files'
        total_key = 'total_input_images' if module_name == 'infrared' else 'total_input_files'
        
        response_data = {
            'output': output, 
            'error': error,
            'returncode': result.returncode,
            original_key: original_files,
            total_key: len(original_files),
            result_key: result_files,
            'module': module_name,
            'message': f"{config['name']}处理完成！处理了 {len(original_files)} 个文件: {', '.join(original_files[:3])}{'...' if len(original_files) > 3 else ''}" if result.returncode == 0 else f"{config['name']}执行出现问题"
        }
        
        return jsonify(response_data)
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': f'{config["name"]}脚本执行超时（超过10分钟）'}), 500
    except Exception as e:
        print(f"执行{config['name']}推理时发生异常: {str(e)}")
        return jsonify({'error': f'执行异常: {str(e)}'}), 500

@app.route('/upload_status', methods=['GET'])
@app.route('/upload_status/<module_name>', methods=['GET'])
def upload_status(module_name='infrared'):
    """检查指定模块是否有已上传的文件"""
    if module_name not in MODULE_CONFIG:
        return jsonify({'error': f'不支持的模块: {module_name}'}), 400
    
    if uploaded_data[module_name]['images']:
        total_files = len(uploaded_data[module_name]['images'])
        latest_file = uploaded_data[module_name]['images'][-1]  # 最新上传的文件
        all_filenames = [file['original_name'] for file in uploaded_data[module_name]['images']]
        
        return jsonify({
            'has_files': True,
            'module': module_name,
            'module_name': MODULE_CONFIG[module_name]['name'],
            'total_files': total_files,
            'latest_filename': latest_file['original_name'],
            'latest_upload_time': latest_file['upload_time'],
            'all_filenames': all_filenames
        })
    else:
        return jsonify({
            'has_files': False,
            'module': module_name,
            'module_name': MODULE_CONFIG[module_name]['name']
        })

@app.route('/clear_cache', methods=['POST'])  
@app.route('/clear_cache/<module_name>', methods=['POST'])
def clear_cache(module_name='infrared'):
    """清除指定模块的上传文件缓存"""
    if module_name not in MODULE_CONFIG:
        return jsonify({'error': f'不支持的模块: {module_name}'}), 400
    
    config = MODULE_CONFIG[module_name]
    
    import shutil
    try:
        # 清除内存中的文件信息
        uploaded_data[module_name]['images'].clear()

        # 递归清空 input 目录
        input_dir = config['input_dir']
        if os.path.exists(input_dir):
            for item in os.listdir(input_dir):
                item_path = os.path.join(input_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

        # 递归清空 output 目录
        output_dir = config['output_dir']
        if os.path.exists(output_dir):
            for item in os.listdir(output_dir):
                item_path = os.path.join(output_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

        # 清理转换后的视频文件
        converted_dir = '/home/vipuser/Downloads/MAP-Net/converted'
        if os.path.exists(converted_dir):
            for item in os.listdir(converted_dir):
                item_path = os.path.join(converted_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

        # 清理转换后的输出视频文件
        converted_output_dir = '/home/vipuser/Downloads/MAP-Net/converted_output'
        if os.path.exists(converted_output_dir):
            for item in os.listdir(converted_output_dir):
                item_path = os.path.join(converted_output_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

        return jsonify({
            'message': f'{config["name"]}缓存已清除，所有上传、输出和转换后的视频文件已删除',
            'module': module_name
        })
    except Exception as e:
        return jsonify({'error': f'清除{config["name"]}缓存失败: {str(e)}'}), 500
from flask import send_file
import io
import zipfile

# 批量打包下载 output/result 目录下所有内容
@app.route('/download_all_result/<module_name>', methods=['GET'])
def download_all_result(module_name):
    """打包下载指定模块的 output/result 目录所有内容（zip）"""
    if module_name not in MODULE_CONFIG:
        return jsonify({'error': f'不支持的模块: {module_name}'}), 400
    config = MODULE_CONFIG[module_name]
    output_dir = config['output_dir']
    if not os.path.exists(output_dir):
        return jsonify({'error': '结果目录不存在'}), 404
    
    # 添加调试信息
    print(f"正在打包目录: {output_dir}")
    
    # 检查目录中的文件
    all_files = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            abs_path = os.path.join(root, file)
            if os.path.isfile(abs_path) and os.path.getsize(abs_path) > 0:
                all_files.append(abs_path)
                print(f"找到文件: {abs_path} (大小: {os.path.getsize(abs_path)} bytes)")
    
    if not all_files:
        return jsonify({'error': '结果目录中没有文件'}), 404
    
    # 创建一个新的BytesIO对象，避免缓存问题
    mem_zip = io.BytesIO()
    
    try:
        with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for abs_path in all_files:
                rel_path = os.path.relpath(abs_path, output_dir)
                try:
                    # 确保文件真的存在并且可读
                    with open(abs_path, 'rb') as f:
                        file_data = f.read()
                    zf.writestr(rel_path, file_data)
                    print(f"已添加到zip: {rel_path} (数据大小: {len(file_data)} bytes)")
                except Exception as e:
                    print(f"添加文件失败: {abs_path}, 错误: {e}")
        
        mem_zip.seek(0)
        zip_size = len(mem_zip.getvalue())
        print(f"生成的zip文件大小: {zip_size} bytes")
        
        if zip_size < 1000:  # 如果zip文件太小，可能有问题
            print(f"警告：生成的zip文件异常小: {zip_size} bytes")
        
        # 使用时间戳避免缓存
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"{module_name}_results_{timestamp}.zip"
        
        return send_file(
            mem_zip, 
            mimetype='application/zip', 
            as_attachment=True, 
            attachment_filename=zip_filename,
            cache_timeout=0  # 禁用缓存
        )
    except Exception as e:
        print(f"创建zip文件时发生错误: {e}")
        return jsonify({'error': f'打包失败: {str(e)}'}), 500

# 下载推荐数据集
@app.route('/download_dataset/video', methods=['GET'])
def download_video_dataset():
    """下载视频模块的推荐数据集"""
    dataset_dir = '/home/vipuser/Downloads/MAP-Net/dataset/video'
    
    if not os.path.exists(dataset_dir):
        return jsonify({'error': '数据集目录不存在'}), 404
    
    # 添加调试信息
    print(f"正在打包数据集目录: {dataset_dir}")
    
    # 检查目录中的文件
    all_files = []
    for root, dirs, files in os.walk(dataset_dir):
        for file in files:
            abs_path = os.path.join(root, file)
            if os.path.isfile(abs_path) and os.path.getsize(abs_path) > 0:
                all_files.append(abs_path)
                print(f"找到数据集文件: {abs_path} (大小: {os.path.getsize(abs_path)} bytes)")
    
    if not all_files:
        return jsonify({'error': '数据集目录中没有文件'}), 404
    
    # 创建一个新的BytesIO对象，避免缓存问题
    mem_zip = io.BytesIO()
    
    try:
        with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for abs_path in all_files:
                rel_path = os.path.relpath(abs_path, dataset_dir)
                try:
                    # 确保文件真的存在并且可读
                    with open(abs_path, 'rb') as f:
                        file_data = f.read()
                    zf.writestr(rel_path, file_data)
                    print(f"已添加数据集到zip: {rel_path} (数据大小: {len(file_data)} bytes)")
                except Exception as e:
                    print(f"添加数据集文件失败: {abs_path}, 错误: {e}")
        
        mem_zip.seek(0)
        zip_size = len(mem_zip.getvalue())
        print(f"生成的数据集zip文件大小: {zip_size} bytes")
        
        if zip_size < 1000:  # 如果zip文件太小，可能有问题
            print(f"警告：生成的数据集zip文件异常小: {zip_size} bytes")
        
        # 使用时间戳避免缓存
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"video_dataset_{timestamp}.zip"
        
        return send_file(
            mem_zip, 
            mimetype='application/zip', 
            as_attachment=True, 
            attachment_filename=zip_filename,
            cache_timeout=0  # 禁用缓存
        )
    except Exception as e:
        print(f"创建数据集zip文件时发生错误: {e}")
        return jsonify({'error': f'数据集打包失败: {str(e)}'}), 500

@app.route('/clear_cuda', methods=['POST'])
def clear_cuda():
    """清理CUDA显存"""
    try:
        result = subprocess.run([
            'python3', '-c', 
            'import torch; import gc; '
            'torch.cuda.empty_cache() if torch.cuda.is_available() else None; '
            'gc.collect(); print("CUDA显存已清理")'
        ], capture_output=True, text=True, cwd='/home/vipuser/Downloads/RGB2TIR')
        
        return jsonify({
            'message': 'CUDA显存清理完成',
            'output': result.stdout,
            'error': result.stderr if result.stderr else None
        })
    except Exception as e:
        return jsonify({'error': f'清理CUDA显存失败: {str(e)}'}), 500

@app.route('/convert_video/<filename>')
def convert_video(filename):
    """将视频转换为网页兼容的H.264格式"""
    try:
        input_path = os.path.join('/home/vipuser/Downloads/MAP-Net/input', filename)
        # 创建转换后的文件存储目录
        converted_dir = '/home/vipuser/Downloads/MAP-Net/converted'
        os.makedirs(converted_dir, exist_ok=True)
        
        # 生成转换后的文件名
        base_name = os.path.splitext(filename)[0]
        converted_filename = f"{base_name}_converted.mp4"
        output_path = os.path.join(converted_dir, converted_filename)
        
        # 检查原文件是否存在
        if not os.path.exists(input_path):
            return jsonify({'error': '原视频文件不存在'}), 404
            
        # 检查是否已经转换过
        if os.path.exists(output_path):
            return send_from_directory(converted_dir, converted_filename)
        
        # 使用ffmpeg转换视频为网页兼容格式
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',  # 使用H.264编码
            '-c:a', 'aac',      # 使用AAC音频编码
            '-movflags', '+faststart',  # 优化网页播放
            '-preset', 'medium',  # 平衡质量和速度
            '-crf', '23',       # 质量设置
            '-y',               # 覆盖输出文件
            output_path
        ]
        
        print(f"开始转换视频: {input_path} -> {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5分钟超时
        
        if result.returncode == 0:
            print(f"视频转换成功: {converted_filename}")
            return send_from_directory(converted_dir, converted_filename)
        else:
            print(f"视频转换失败: {result.stderr}")
            return jsonify({'error': f'视频转换失败: {result.stderr}'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': '视频转换超时'}), 500
    except Exception as e:
        print(f"视频转换异常: {str(e)}")
        return jsonify({'error': f'视频转换异常: {str(e)}'}), 500

@app.route('/list_input_videos')
def list_input_videos():
    """列出输入目录中的所有视频文件"""
    try:
        input_dir = '/home/vipuser/Downloads/MAP-Net/input'
        if not os.path.exists(input_dir):
            return jsonify({'videos': [], 'message': '输入目录不存在'})
        
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        videos = []
        
        for file in os.listdir(input_dir):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                file_path = os.path.join(input_dir, file)
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)
                
                videos.append({
                    'filename': file,
                    'size': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'modified_time': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # 按修改时间排序
        videos.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return jsonify({
            'videos': videos,
            'count': len(videos)
        })
        
    except Exception as e:
        return jsonify({'error': f'获取视频列表失败: {str(e)}'}), 500

@app.route('/list_output_videos')
def list_output_videos():
    """列出输出目录中的所有视频文件"""
    try:
        output_dir = '/home/vipuser/Downloads/MAP-Net/result/videos'
        if not os.path.exists(output_dir):
            return jsonify({'videos': [], 'message': '输出目录不存在'})
        
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        videos = []
        
        for file in os.listdir(output_dir):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                file_path = os.path.join(output_dir, file)
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)
                
                videos.append({
                    'filename': file,
                    'size': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'modified_time': datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # 按修改时间排序
        videos.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return jsonify({
            'videos': videos,
            'count': len(videos)
        })
        
    except Exception as e:
        return jsonify({'error': f'获取输出视频列表失败: {str(e)}'}), 500

@app.route('/input_video/<filename>')
def serve_input_video(filename):
    """提供输入视频文件服务"""
    input_dir = '/home/vipuser/Downloads/MAP-Net/input'
    file_path = os.path.join(input_dir, filename)
    
    if os.path.exists(file_path):
        return send_from_directory(input_dir, filename)
    else:
        return "Input video file not found", 404

@app.route('/convert_output_video/<filename>')
def convert_output_video(filename):
    """将输出视频转换为网页兼容的H.264格式"""
    try:
        input_path = os.path.join('/home/vipuser/Downloads/MAP-Net/result/videos', filename)
        # 创建转换后的文件存储目录
        converted_dir = '/home/vipuser/Downloads/MAP-Net/converted_output'
        os.makedirs(converted_dir, exist_ok=True)
        
        # 生成转换后的文件名
        base_name = os.path.splitext(filename)[0]
        converted_filename = f"{base_name}_output_converted.mp4"
        output_path = os.path.join(converted_dir, converted_filename)
        
        # 检查原文件是否存在
        if not os.path.exists(input_path):
            return jsonify({'error': '输出视频文件不存在'}), 404
            
        # 检查是否已经转换过
        if os.path.exists(output_path):
            return send_from_directory(converted_dir, converted_filename)
        
        # 使用ffmpeg转换视频为网页兼容格式
        cmd = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',  # 使用H.264编码
            '-c:a', 'aac',      # 使用AAC音频编码
            '-movflags', '+faststart',  # 优化网页播放
            '-preset', 'medium',  # 平衡质量和速度
            '-crf', '23',       # 质量设置
            '-y',               # 覆盖输出文件
            output_path
        ]
        
        print(f"开始转换输出视频: {input_path} -> {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5分钟超时
        
        if result.returncode == 0:
            print(f"输出视频转换成功: {converted_filename}")
            return send_from_directory(converted_dir, converted_filename)
        else:
            print(f"输出视频转换失败: {result.stderr}")
            return jsonify({'error': f'输出视频转换失败: {result.stderr}'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': '输出视频转换超时'}), 500
    except Exception as e:
        print(f"输出视频转换异常: {str(e)}")
        return jsonify({'error': f'输出视频转换异常: {str(e)}'}), 500

# 任务管理 - 用于跟踪长时间运行的任务
running_tasks = {}

# 清除激光雷达缓存文件
@app.route('/clear_lidar_cache', methods=['POST'])
def clear_lidar_cache():
    """清除激光雷达生成的缓存文件"""
    try:
        data = request.get_json() or {}
        # 默认缓存路径
        default_cache_path = '/home/vipuser/home/huangff/lidargen-main/kitti_pretrained/unconditional_samples'
        cache_path = data.get('cache_path', default_cache_path)
        
        deleted_count = 0
        
        # 检查路径是否存在
        if not os.path.exists(cache_path):
            return jsonify({
                'success': True,
                'message': f'缓存目录不存在: {cache_path}',
                'deleted_count': 0
            })
        
        # 检查是否是目录
        if not os.path.isdir(cache_path):
            return jsonify({
                'success': False,
                'error': f'指定路径不是目录: {cache_path}'
            }), 400
        
        # 删除目录下的所有文件和子目录
        import shutil
        for item in os.listdir(cache_path):
            item_path = os.path.join(cache_path, item)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    deleted_count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_count += 1
            except Exception as e:
                print(f"删除文件/目录失败 {item_path}: {str(e)}")
                continue
        
        return jsonify({
            'success': True,
            'message': f'激光雷达缓存清除成功，删除了 {deleted_count} 个文件/目录',
            'deleted_count': deleted_count,
            'cache_path': cache_path
        })
        
    except Exception as e:
        print(f"清除激光雷达缓存失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'清除缓存失败: {str(e)}'
        }), 500

# 生成激光雷达可视化图片
@app.route('/run_lidar_visualization', methods=['POST'])
def run_lidar_visualization():
    """执行激光雷达可视化图片生成脚本"""
    try:
        # 检查缓存目录是否存在文件
        cache_path = '/home/vipuser/home/huangff/lidargen-main/kitti_pretrained/unconditional_samples'
        if not os.path.exists(cache_path):
            return jsonify({
                'success': False,
                'error': f'缓存目录不存在: {cache_path}'
            }), 404
        
        # 检查目录是否有文件
        files_in_cache = []
        for item in os.listdir(cache_path):
            item_path = os.path.join(cache_path, item)
            if os.path.isfile(item_path):
                files_in_cache.append(item)
        
        if not files_in_cache:
            return jsonify({
                'success': False,
                'error': '缓存目录中没有找到文件，请先执行激光雷达数据生成'
            }), 400
        
        # 脚本路径
        script_path = '/home/vipuser/home/huangff/lidargen-main/run_gen2ply.sh'
        
        # 检查脚本是否存在
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'error': f'可视化脚本文件不存在: {script_path}'
            }), 404
        
        # 直接执行脚本（同步执行）
        print(f"执行激光雷达可视化脚本: {script_path}")
        print(f"发现 {len(files_in_cache)} 个文件待处理: {files_in_cache[:3]}{'...' if len(files_in_cache) > 3 else ''}")
        
        try:
            result = subprocess.run(
                ['bash', script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,  # 5分钟超时
                cwd=os.path.dirname(script_path),  # 设置工作目录
                text=True
            )
            
            output = result.stdout
            error = result.stderr
            
            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': f'可视化生成完成！处理了 {len(files_in_cache)} 个文件',
                    'files_count': len(files_in_cache),
                    'output': output,
                    'error': error if error else None
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'脚本执行失败 (返回码: {result.returncode})',
                    'output': output,
                    'stderr': error
                }), 500
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error': '脚本执行超时（超过5分钟）'
            }), 500
        
    except Exception as e:
        print(f"执行激光雷达可视化脚本失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'执行失败: {str(e)}'
        }), 500

# 获取激光雷达可视化结果
@app.route('/get_lidar_visualization_results', methods=['GET'])
def get_lidar_visualization_results():
    """获取激光雷达可视化结果图片"""
    try:
        ply_img_dir = '/home/vipuser/home/huangff/lidargen-main/kitti_pretrained/unconditional_samples/ply_img'
        range_img_dir = '/home/vipuser/home/huangff/lidargen-main/kitti_pretrained/unconditional_samples/range_img'
        
        # 检查目录是否存在
        if not os.path.exists(ply_img_dir):
            return jsonify({
                'success': False,
                'error': f'3D点云图片目录不存在: {ply_img_dir}'
            }), 404
        
        if not os.path.exists(range_img_dir):
            return jsonify({
                'success': False,
                'error': f'范围信息图片目录不存在: {range_img_dir}'
            }), 404
        
        # 获取图片列表
        ply_images = []
        range_images = []
        
        # 扫描ply_img目录
        for i in range(20):  # 假设最多有20张图片（0-19）
            for ext in ['.png', '.jpg', '.jpeg']:
                ply_file = os.path.join(ply_img_dir, f'{i}{ext}')
                if os.path.exists(ply_file):
                    ply_images.append({
                        'index': i,
                        'filename': f'{i}{ext}',
                        'path': ply_file
                    })
                    break
        
        # 扫描range_img目录
        for i in range(20):  # 假设最多有20张图片（0-19）
            for ext in ['.png', '.jpg', '.jpeg']:
                range_file = os.path.join(range_img_dir, f'{i}{ext}')
                if os.path.exists(range_file):
                    range_images.append({
                        'index': i,
                        'filename': f'{i}{ext}',
                        'path': range_file
                    })
                    break
        
        # 创建对应的图片对
        image_pairs = []
        ply_dict = {img['index']: img for img in ply_images}
        range_dict = {img['index']: img for img in range_images}
        
        # 找出共同的索引
        common_indices = set(ply_dict.keys()) & set(range_dict.keys())
        
        for index in sorted(common_indices):
            image_pairs.append({
                'index': index,
                'ply_image': ply_dict[index],
                'range_image': range_dict[index]
            })
        
        if not image_pairs:
            return jsonify({
                'success': False,
                'error': '没有找到对应的可视化结果图片'
            }), 404
        
        return jsonify({
            'success': True,
            'message': f'找到 {len(image_pairs)} 对可视化结果图片',
            'image_pairs': image_pairs,
            'ply_count': len(ply_images),
            'range_count': len(range_images)
        })
        
    except Exception as e:
        print(f"获取可视化结果失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'获取结果失败: {str(e)}'
        }), 500

# 提供可视化图片文件服务
@app.route('/lidar_visualization/<path:subpath>')
def serve_lidar_visualization(subpath):
    """提供激光雷达可视化图片文件服务"""
    try:
        base_dir = '/home/vipuser/home/huangff/lidargen-main/kitti_pretrained/unconditional_samples'
        file_path = os.path.join(base_dir, subpath)
        
        # 安全检查，确保路径在允许的目录内
        if not file_path.startswith(base_dir):
            return "Access denied", 403
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_file(file_path)
        else:
            return "File not found", 404
            
    except Exception as e:
        print(f"提供可视化图片失败: {str(e)}")
        return "Internal server error", 500

# 执行激光雷达生成脚本
@app.route('/run_lidar_script', methods=['POST'])
def run_lidar_script():
    """执行激光雷达数据生成脚本"""
    try:
        # 检查是否已有任务在运行
        active_tasks = [task_id for task_id, task in running_tasks.items() if not task.get('completed', False)]
        if active_tasks:
            return jsonify({
                'success': False,
                'error': f'已有任务正在运行 (ID: {active_tasks[0]})，请先停止当前任务'
            }), 409
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 脚本路径
        script_path = '/home/vipuser/home/huangff/lidargen-main/run_gen.sh'
        
        # 检查脚本是否存在
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'error': f'脚本文件不存在: {script_path}'
            }), 404
        
        # 检查脚本是否可执行
        if not os.access(script_path, os.X_OK):
            return jsonify({
                'success': False,
                'error': f'脚本文件没有执行权限: {script_path}'
            }), 403
        
        # 启动后台进程
        print(f"启动激光雷达生成脚本: {script_path}")
        # 使用stdbuf强制无缓冲输出
        process = subprocess.Popen(
            ['stdbuf', '-oL', '-eL', 'bash', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=0,  # 无缓冲
            preexec_fn=os.setsid,  # 创建新的进程组
            env=dict(os.environ, PYTHONUNBUFFERED='1')  # 强制Python无缓冲输出
        )
        
        # 存储任务信息
        running_tasks[task_id] = {
            'process': process,
            'output': '',
            'start_time': datetime.now().isoformat(),
            'completed': False,
            'success': False,
            'pid': process.pid
        }
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '激光雷达生成脚本已启动',
            'pid': process.pid
        })
        
    except Exception as e:
        print(f"启动激光雷达脚本失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'启动失败: {str(e)}'
        }), 500

# 获取任务输出
@app.route('/get_task_output/<task_id>', methods=['GET'])
def get_task_output(task_id):
    """获取指定任务的输出"""
    if task_id not in running_tasks:
        return jsonify({
            'error': '任务不存在',
            'output': '',
            'completed': True,
            'success': False
        }), 404
    
    task = running_tasks[task_id]
    process = task['process']
    
    try:
        # 使用非阻塞方式读取输出
        import select
        
        # 检查是否有可读数据
        if hasattr(select, 'select'):
            ready, _, _ = select.select([process.stdout], [], [], 0)
            if ready:
                # 逐行读取可用的输出
                while True:
                    try:
                        line = process.stdout.readline()
                        if not line:
                            break
                        task['output'] += line
                    except Exception:
                        break
        else:
            # 对于不支持select的系统，使用readline
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    task['output'] += line
            except Exception:
                pass
        
        # 检查进程是否结束
        if process.poll() is not None:
            # 进程已结束，读取剩余输出
            try:
                remaining_output = process.stdout.read()
                if remaining_output:
                    task['output'] += remaining_output
            except Exception:
                pass
            
            task['completed'] = True
            task['success'] = (process.returncode == 0)
            task['end_time'] = datetime.now().isoformat()
            
            print(f"激光雷达任务 {task_id} 完成，返回码: {process.returncode}")
        
        return jsonify({
            'output': task['output'],
            'completed': task['completed'],
            'success': task['success'] if task['completed'] else None,
            'start_time': task['start_time']
        })
        
    except Exception as e:
        print(f"获取任务输出失败: {str(e)}")
        return jsonify({
            'error': f'获取输出失败: {str(e)}',
            'output': task.get('output', ''),
            'completed': True,
            'success': False
        }), 500

# 停止任务
@app.route('/stop_task/<task_id>', methods=['POST'])
def stop_task(task_id):
    """停止指定的任务"""
    if task_id not in running_tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = running_tasks[task_id]
    process = task['process']
    
    try:
        # 检查进程是否还在运行
        if process.poll() is None:
            # 进程还在运行，尝试终止它
            print(f"正在终止任务 {task_id}，PID: {task.get('pid', 'unknown')}")
            
            try:
                # 首先尝试优雅地终止进程组
                os.killpg(os.getpgid(process.pid), 15)  # SIGTERM
                print(f"发送 SIGTERM 到进程组 {process.pid}")
                
                # 等待进程终止，最多等待3秒
                try:
                    process.wait(timeout=3)
                    print(f"任务 {task_id} 已正常终止")
                except subprocess.TimeoutExpired:
                    # 如果进程没有在3秒内终止，强制杀死进程组
                    print(f"任务 {task_id} 未能正常终止，强制杀死进程组")
                    os.killpg(os.getpgid(process.pid), 9)  # SIGKILL
                    process.wait()
                    print(f"任务 {task_id} 已被强制终止")
                    
            except ProcessLookupError:
                # 进程已经不存在
                print(f"进程 {process.pid} 已经不存在")
            except OSError as e:
                print(f"终止进程时出错: {e}")
                # 尝试直接杀死主进程
                try:
                    process.kill()
                    process.wait()
                except:
                    pass
            
            # 标记任务为已完成但不成功
            task['completed'] = True
            task['success'] = False
            task['end_time'] = datetime.now().isoformat()
            task['output'] += '\n\n=== 任务已被用户中断 ===\n'
            
            return jsonify({
                'success': True,
                'message': '任务已成功停止'
            })
        else:
            # 进程已经结束
            task['completed'] = True
            task['success'] = (process.returncode == 0)
            return jsonify({
                'success': True,
                'message': '任务已经结束'
            })
            
    except Exception as e:
        print(f"停止任务失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'停止任务失败: {str(e)}'
        }), 500

@app.route('/api/gpu_status', methods=['GET'])
def get_gpu_status():
    """获取GPU状态信息，包括显存使用情况"""
    try:
        import nvidia_ml_py3 as nvml
        nvml.nvmlInit()
        
        # 获取GPU设备数量
        device_count = nvml.nvmlDeviceGetCount()
        gpu_info = []
        
        for i in range(device_count):
            handle = nvml.nvmlDeviceGetHandleByIndex(i)
            
            # 获取GPU名称
            name = nvml.nvmlDeviceGetName(handle).decode('utf-8')
            
            # 获取显存信息
            memory_info = nvml.nvmlDeviceGetMemoryInfo(handle)
            total_memory = memory_info.total
            used_memory = memory_info.used
            free_memory = memory_info.free
            
            # 获取GPU利用率
            try:
                utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = utilization.gpu
            except:
                gpu_util = -1
            
            # 获取温度
            try:
                temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
            except:
                temp = -1
            
            # 获取功率使用情况
            try:
                power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # 转换为瓦特
            except:
                power = -1
            
            gpu_info.append({
                'id': i,
                'name': name,
                'memory': {
                    'total': total_memory,
                    'used': used_memory,
                    'free': free_memory,
                    'total_gb': round(total_memory / (1024**3), 2),
                    'used_gb': round(used_memory / (1024**3), 2),
                    'free_gb': round(free_memory / (1024**3), 2),
                    'usage_percent': round((used_memory / total_memory) * 100, 1)
                },
                'utilization': gpu_util,
                'temperature': temp,
                'power': power
            })
        
        nvml.nvmlShutdown()
        
        return jsonify({
            'success': True,
            'gpu_count': device_count,
            'gpus': gpu_info,
            'timestamp': datetime.now().isoformat()
        })
        
    except ImportError:
        # 如果没有安装nvidia-ml-py3，尝试使用nvidia-smi命令
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                gpu_info = []
                
                for i, line in enumerate(lines):
                    if line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 6:
                            try:
                                total_mb = float(parts[2])
                                used_mb = float(parts[3])
                                free_mb = float(parts[4])
                                
                                # 解析利用率
                                try:
                                    util_val = float(parts[5]) if parts[5] not in ['[Not Supported]', '[N/A]'] else -1
                                except (ValueError, IndexError):
                                    util_val = -1
                                
                                # 解析温度
                                try:
                                    temp_val = float(parts[6]) if len(parts) > 6 and parts[6] not in ['[Not Supported]', '[N/A]'] else -1
                                except (ValueError, IndexError):
                                    temp_val = -1
                                
                                # 解析功耗
                                try:
                                    power_val = float(parts[7]) if len(parts) > 7 and parts[7] not in ['[Not Supported]', '[N/A]'] else -1
                                except (ValueError, IndexError):
                                    power_val = -1
                                
                                gpu_info.append({
                                    'id': i,
                                    'name': parts[1],
                                    'memory': {
                                        'total': int(total_mb * 1024 * 1024),
                                        'used': int(used_mb * 1024 * 1024),
                                        'free': int(free_mb * 1024 * 1024),
                                        'total_gb': round(total_mb / 1024, 2),
                                        'used_gb': round(used_mb / 1024, 2),
                                        'free_gb': round(free_mb / 1024, 2),
                                        'usage_percent': round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0
                                    },
                                    'utilization': util_val,
                                    'temperature': temp_val,
                                    'power': power_val
                                })
                            except (ValueError, IndexError) as e:
                                print(f"解析GPU信息失败: {e}, 行内容: {line}")
                                continue
                
                return jsonify({
                    'success': True,
                    'gpu_count': len(gpu_info),
                    'gpus': gpu_info,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'nvidia-smi command failed',
                    'stderr': result.stderr
                }), 500
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error': 'nvidia-smi command timeout'
            }), 500
        except FileNotFoundError:
            return jsonify({
                'success': False,
                'error': 'NVIDIA GPU not detected or nvidia-smi not available'
            }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to get GPU status: {str(e)}'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get GPU status: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8800)