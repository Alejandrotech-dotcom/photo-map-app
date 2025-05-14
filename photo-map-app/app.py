# app.py
import os
import sys
from flask import Flask, render_template, request, redirect, send_from_directory
import zipfile
import uuid
import shutil

try:
    from utils.generate_map_core import generate_map
except ImportError:
    from .utils.generate_map_core import generate_map

try:
    from utils.generate_map_core_China import generate_map_china
except ImportError:
    from .utils.generate_map_core_China import generate_map_china

# 关键：兼容 PyInstaller 的 BASE 路径
BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath("."))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'static'),
                        template_folder=os.path.join(BASE_DIR, 'templates'))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
MAP_FOLDER = os.path.join(BASE_DIR, 'static', 'map_output')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MAP_FOLDER, exist_ok=True)


@app.route('/')
def index():
    session_id = request.args.get("session_id")
    if session_id:
        filename = f"map_{session_id}.html"
        file_path = os.path.join(MAP_FOLDER, filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🧹 用户返回主页，已删除地图: {filename}")
        except Exception as e:
            print(f"❌ 删除地图文件失败: {e}")
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    if not files:
        return "未选择任何文件", 400

    # 获取地图区域选择
    region = request.form.get('region', 'china')  # 默认值为 'china'

    session_id = str(uuid.uuid4())
    extract_path = os.path.join(UPLOAD_FOLDER, session_id)
    os.makedirs(extract_path)

    zip_found = False
    for f in files:
        filename = f.filename
        if filename.lower().endswith('.zip'):
            zip_found = True
            zip_path = os.path.join(extract_path, filename)
            f.save(zip_path)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
            except zipfile.BadZipFile:
                cleanup_dir(extract_path)
                return "上传的 ZIP 文件无效", 400
        else:
            f.save(os.path.join(extract_path, filename))

    region = request.form.get('region')
    if region == 'global':
        html_str = generate_map(extract_path)
    else:
        html_str = generate_map_china(extract_path)

    output_path = os.path.join(MAP_FOLDER, f"map_{session_id}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_str)

    cleanup_dir(extract_path)

    return redirect(f"/map/{session_id}")



@app.route('/map/<session_id>')
def map_view(session_id):
    map_file = f"map_{session_id}.html"
    return render_template("map_view.html", map_file=map_file)

@app.route('/download/<session_id>')
def download(session_id):
    filename = f"map_{session_id}.html"
    return send_from_directory(MAP_FOLDER, filename, as_attachment=True)

def cleanup_dir(path):
    try:
        shutil.rmtree(path)
        print("完成清理")
    except Exception as e:
        print(f"清理目录失败: {e}")

if __name__ == '__main__':
    app.run(debug=True)
