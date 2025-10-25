from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import markdown
from weasyprint import HTML
import io
import cv2
import numpy as np
from lama_cleaner.model_manager import ModelManager
from lama_cleaner.schema import Config

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'md', 'txt', 'png', 'jpg', 'jpeg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Lama Cleaner model
model_manager = ModelManager(name="lama", device="cpu")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/convert', methods=['POST'])
def convert_markdown():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    md_content = file.read().decode('utf-8')
    html_content = markdown.markdown(md_content, extensions=['extra', 'codehilite'])
    
    css = """
    body { font-family: Arial, sans-serif; margin: 40px; }
    code { background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
    pre { background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
    """
    
    html_with_css = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>{css}</style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    pdf_buffer = io.BytesIO()
    HTML(string=html_with_css).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='converted.pdf')

@app.route('/clean-image', methods=['POST'])
def clean_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    if 'mask' not in request.files:
        return jsonify({'error': 'No mask provided'}), 400
    
    image_file = request.files['image']
    mask_file = request.files['mask']
    
    # Read image and mask
    image_bytes = np.frombuffer(image_file.read(), np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    
    mask_bytes = np.frombuffer(mask_file.read(), np.uint8)
    mask = cv2.imdecode(mask_bytes, cv2.IMREAD_GRAYSCALE)
    
    # Process with Lama Cleaner
    config = Config(
        ldm_steps=20,
        ldm_sampler='plms',
        hd_strategy='Original',
        hd_strategy_crop_margin=128,
        hd_strategy_crop_trigger_size=800,
        hd_strategy_resize_limit=800,
    )
    
    result = model_manager(image, mask, config)
    
    # Encode result to bytes
    _, buffer = cv2.imencode('.png', result)
    result_buffer = io.BytesIO(buffer)
    result_buffer.seek(0)
    
    return send_file(result_buffer, mimetype='image/png', as_attachment=True, download_name='cleaned.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
