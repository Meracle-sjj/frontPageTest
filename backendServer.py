from flask import Flask, request, jsonify
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

# 存储用户上传的图片信息
user_uploaded_images = {
    'images': []  # 改为列表，支持多张图片
}

@app.route('/')
def index():
    return jsonify({
        'message': '欢迎使用 RGB2TIR 转换服务',
        'endpoints': {
            'upload': 'POST /upload - 上传图片',
            'upload_status': 'GET /upload_status - 检查上传状态', 
            'run_inference': 'POST /run_inference - 运行推理',
            'clear_cache': 'POST /clear_cache - 清除缓存',
            'clear_cuda': 'POST /clear_cuda - 清理CUDA显存'
        }
    })

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'No image uploaded'}), 400
    
    input_dir = "/home/vipuser/Downloads/RGB2TIR/input"
    os.makedirs(input_dir, exist_ok=True)
    
    # 不再清空input目录，支持多张图片累积上传
    # 检查是否已存在同名文件，避免覆盖
    original_filename = file.filename or 'unnamed.jpg'
    file_extension = os.path.splitext(original_filename)[1] or '.jpg'
    base_name = os.path.splitext(original_filename)[0]
    
    # 生成唯一的文件名
    unique_filename = f'{uuid.uuid4().hex}{file_extension}'
    save_path = os.path.join(input_dir, unique_filename)
    
    try:
        file.save(save_path)
        
        # 将新图片信息添加到列表中
        image_info = {
            'filename': unique_filename,
            'original_name': original_filename,
            'upload_time': datetime.now().isoformat(),
            'path': save_path
        }
        
        user_uploaded_images['images'].append(image_info)
        
        return jsonify({
            'msg': f'图片已保存: {unique_filename}',
            'filename': unique_filename,
            'original_name': original_filename,
            'total_images': len(user_uploaded_images['images'])
        })
    except Exception as e:
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

@app.route('/run_inference', methods=['POST'])
def run_inference():
    try:
        # 检查用户是否上传了图片
        if not user_uploaded_images['images']:
            return jsonify({'error': '请先上传图片再执行推理！'}), 400
        
        print(f"开始对 {len(user_uploaded_images['images'])} 张图片执行推理脚本...")
        
        # 检查所有上传的图片文件是否还存在
        missing_files = []
        for img_info in user_uploaded_images['images']:
            if not os.path.exists(img_info['path']):
                missing_files.append(img_info['original_name'])
        
        if missing_files:
            return jsonify({'error': f'以下图片文件不存在，请重新上传：{", ".join(missing_files)}'}), 400
        
        # 检查脚本文件是否存在
        script_path = '/home/vipuser/Downloads/RGB2TIR/run_inference.sh'
        if not os.path.exists(script_path):
            return jsonify({'error': f'脚本文件不存在: {script_path}'}), 500
        
        # 清空输出目录
        output_dir = "/home/vipuser/Downloads/RGB2TIR/output"
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
            cwd='/home/vipuser/Downloads/RGB2TIR',
            env=env
        )
        
        output = result.stdout.decode('utf-8')
        error = result.stderr.decode('utf-8')
        
        print(f"脚本执行完成，返回码: {result.returncode}")
        print(f"输出: {output}")
        if error:
            print(f"错误: {error}")
        
        # 查找生成的结果图片
        result_images = []
        print(f"检查输出目录: {output_dir}")
        
        # 列出输出目录中的所有文件进行调试
        if os.path.exists(output_dir):
            all_files = os.listdir(output_dir)
            print(f"输出目录中的所有文件: {all_files}")
            
            output_files = glob.glob(os.path.join(output_dir, "*"))
            print(f"Glob匹配到的文件: {output_files}")
            
            for output_file in output_files:
                print(f"检查文件: {output_file}")
                if os.path.isfile(output_file):
                    file_ext = output_file.lower()
                    print(f"文件扩展名检查: {file_ext}")
                    if file_ext.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                        try:
                            print(f"读取图片文件: {output_file}")
                            with open(output_file, 'rb') as img_file:
                                img_data = base64.b64encode(img_file.read()).decode('utf-8')
                                result_images.append({
                                    'filename': os.path.basename(output_file),
                                    'data': img_data
                                })
                                print(f"成功读取图片: {os.path.basename(output_file)}")
                        except Exception as e:
                            print(f"读取结果图片失败: {e}")
                    else:
                        print(f"文件不是图片格式: {output_file}")
        else:
            print(f"输出目录不存在: {output_dir}")
        
        print(f"找到 {len(result_images)} 张结果图片")
        
        # 获取所有原始图片的名称
        original_images = [img['original_name'] for img in user_uploaded_images['images']]
        
        return jsonify({
            'output': output, 
            'error': error,
            'returncode': result.returncode,
            'original_images': original_images,
            'total_input_images': len(original_images),
            'result_images': result_images,
            'message': f"推理完成！处理了 {len(original_images)} 张图片: {', '.join(original_images[:3])}{'...' if len(original_images) > 3 else ''}" if result.returncode == 0 else "推理执行出现问题"
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': '脚本执行超时（超过300秒）'}), 500
    except Exception as e:
        print(f"执行推理时发生异常: {str(e)}")
        return jsonify({'error': f'执行异常: {str(e)}'}), 500

@app.route('/upload_status', methods=['GET'])
def upload_status():
    """检查是否有已上传的图片"""
    if user_uploaded_images['images']:
        total_images = len(user_uploaded_images['images'])
        latest_image = user_uploaded_images['images'][-1]  # 最新上传的图片
        all_filenames = [img['original_name'] for img in user_uploaded_images['images']]
        
        return jsonify({
            'has_image': True,
            'total_images': total_images,
            'latest_filename': latest_image['original_name'],
            'latest_upload_time': latest_image['upload_time'],
            'all_filenames': all_filenames
        })
    else:
        return jsonify({'has_image': False})

@app.route('/clear_cache', methods=['POST'])  
def clear_cache():
    """清除上传图片缓存"""
    try:
        # 清除内存中的图片信息
        user_uploaded_images['images'].clear()
        
        # 清空input目录
        input_dir = "/home/vipuser/Downloads/RGB2TIR/input"
        if os.path.exists(input_dir):
            for existing_file in glob.glob(os.path.join(input_dir, "*")):
                if os.path.isfile(existing_file):
                    os.remove(existing_file)
        
        # 清空output目录
        output_dir = "/home/vipuser/Downloads/RGB2TIR/output"
        if os.path.exists(output_dir):
            for existing_file in glob.glob(os.path.join(output_dir, "*")):
                if os.path.isfile(existing_file):
                    os.remove(existing_file)
        
        return jsonify({'message': '缓存已清除，所有上传和输出文件已删除'})
    except Exception as e:
        return jsonify({'error': f'清除缓存失败: {str(e)}'}), 500

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