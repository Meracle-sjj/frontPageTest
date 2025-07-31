from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
app = Flask(__name__)
CORS(app)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'No image uploaded'}), 400
    import os
    input_dir = "/root/RGB2TIR/input"
    os.makedirs(input_dir, exist_ok=True)
    filename = file.filename or f'{uuid.uuid4().hex}.jpg'
    save_path = os.path.join(input_dir, filename)
    try:
        file.save(save_path)
        return jsonify({'msg': f'图片已保存: {save_path}'})
    except Exception as e:
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8800)