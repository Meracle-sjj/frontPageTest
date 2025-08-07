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

        return jsonify({
            'message': f'{config["name"]}缓存已清除，所有上传和输出文件已删除',
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8800)