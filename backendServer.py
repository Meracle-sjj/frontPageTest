from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import uuid
import subprocess
import os
import json
from datetime import datetime
import glob
import base64

app = Flask(__name__)
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
        'input_dir': '/home/vipuser/Downloads/VideoSynthesis/input',
        'output_dir': '/home/vipuser/Downloads/VideoSynthesis/output',
        'script_path': '/home/vipuser/Downloads/VideoSynthesis/run_inference.sh',
        'supported_formats': ['.mp4', '.avi', '.mov', '.mkv']
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
                'status': 'working',
                'intro_page': 'video_index.html',
                'trial_available': False
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
        
        if os.path.exists(output_dir):
            all_files = os.listdir(output_dir)
            print(f"输出目录中的所有文件: {all_files}")
            
            output_files = glob.glob(os.path.join(output_dir, "*"))
            print(f"Glob匹配到的文件: {output_files}")
            
            for output_file in output_files:
                print(f"检查文件: {output_file}")
                if os.path.isfile(output_file):
                    try:
                        print(f"读取文件: {output_file}")
                        with open(output_file, 'rb') as file:
                            file_data = base64.b64encode(file.read()).decode('utf-8')
                            result_files.append({
                                'filename': os.path.basename(output_file),
                                'data': file_data
                            })
                            print(f"成功读取文件: {os.path.basename(output_file)}")
                    except Exception as e:
                        print(f"读取结果文件失败: {e}")
        else:
            print(f"输出目录不存在: {output_dir}")
        
        print(f"找到 {len(result_files)} 个结果文件")
        
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
    
    try:
        # 清除内存中的文件信息
        uploaded_data[module_name]['images'].clear()
        
        # 清空input目录
        input_dir = config['input_dir']
        if os.path.exists(input_dir):
            for existing_file in glob.glob(os.path.join(input_dir, "*")):
                if os.path.isfile(existing_file):
                    os.remove(existing_file)
        
        # 清空output目录
        output_dir = config['output_dir']
        if os.path.exists(output_dir):
            for existing_file in glob.glob(os.path.join(output_dir, "*")):
                if os.path.isfile(existing_file):
                    os.remove(existing_file)
        
        return jsonify({
            'message': f'{config["name"]}缓存已清除，所有上传和输出文件已删除',
            'module': module_name
        })
    except Exception as e:
        return jsonify({'error': f'清除{config["name"]}缓存失败: {str(e)}'}), 500

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