import os
import yt_dlp
import tempfile
import re
import time
import io
import random
import string
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urlparse
from PIL import Image
import pypdf

app = Flask(__name__)

# إعدادات CORS للسماح بالاتصال من نطاق الموقع
CORS(app, resources={r"/*": {"origins": ["https://saveitpro.co", "https://www.saveitpro.co"]}})

# المنصات المدعومة لتنزيل الفيديوهات
SUPPORTED_PLATFORMS = [
    'YouTube', 'TikTok', 'Instagram', 'Facebook', 'Reddit', 
    'Twitter/X', 'Pinterest', 'Snapchat', 'Twitch', 'Vimeo'
]

TEMP_DIR = tempfile.gettempdir()

def cleanup_old_files():
    """تنظيف الملفات المؤقتة لتفادي امتلاء ذاكرة السيرفر"""
    try:
        current_time = time.time()
        for filename in os.listdir(TEMP_DIR):
            if filename.startswith('saveitpro_'):
                filepath = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getctime(filepath)
                    if file_age > 1800:  # 30 دقيقة
                        os.remove(filepath)
    except Exception:
        pass

# ==================== GENERAL ROUTES ====================

@app.route('/')
def root():
    return jsonify({
        "status": "running",
        "message": "SaveItPro All-In-One API v2.0 is Live!",
        "version": "2.0.0"
    }), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "SaveItPro Backend", "version": "2.0.0"}), 200

# ==================== 1. VIDEO DOWNLOADER ====================

@app.route('/api/download', methods=['POST'])
def download_media():
    try:
        cleanup_old_files()
        data = request.get_json() or {}
        url = data.get('url', '').strip()

        if not url or not url.startswith(('http://', 'https://')):
            return jsonify({"success": False, "error": "Invalid URL"}), 400

        unique_id = os.urandom(6).hex()
        base_filename = f"saveitpro_{unique_id}"

        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(TEMP_DIR, f'{base_filename}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            final_filename = os.path.basename(file_path)

            download_url = f"{request.host_url}api/get/{final_filename}"
            safe_title = re.sub(r'[^a-zA-Z0-9\s_-]', '', info.get('title', 'download'))

            return jsonify({
                "success": True,
                "downloadUrl": download_url,
                "filename": final_filename,
                "title": safe_title
            }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/get/<filename>', methods=['GET'])
def get_file(filename):
    try:
        if '..' in filename or '/' in filename or not filename.startswith('saveitpro_'):
            return jsonify({"error": "Invalid filename"}), 400

        file_path = os.path.join(TEMP_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)

        return jsonify({"error": "File not found or expired"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ==================== 2. REMOVE BG (إزالة الخلفية) ====================

@app.route('/api/tools/remove-bg', methods=['POST'])
def remove_bg():
    try:
        from rembg import remove
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        input_file = request.files['image'].read()
        output_data = remove(input_file)
        return send_file(io.BytesIO(output_data), mimetype='image/png', as_attachment=True, download_name="no-bg.png")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 3. IMG COMPRESS (ضغط الصور) ====================

@app.route('/api/tools/compress-image', methods=['POST'])
def compress_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        file = request.files['image']
        quality = int(request.form.get('quality', 60))
        img = Image.open(file.stream)
        output = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output, format='JPEG', optimize=True, quality=quality)
        output.seek(0)
        return send_file(output, mimetype='image/jpeg', as_attachment=True, download_name="compressed.jpg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 4. PASS GEN (مولد كلمات السر) ====================

@app.route('/api/tools/generate-password', methods=['GET', 'POST'])
def generate_password():
    data = request.get_json() or {}
    length = int(data.get('length', 12))
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = ''.join(random.choice(chars) for _ in range(length))
    return jsonify({"password": password})

# ==================== 5. AGE CALC (حاسبة العمر) ====================

@app.route('/api/tools/calculate-age', methods=['POST'])
def calculate_age():
    try:
        data = request.get_json() or {}
        birthdate_str = data.get('birthdate')
        birth_date = datetime.strptime(birthdate_str, '%Y-%m-%d')
        today = datetime.today()
        years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        months = (today.month - birth_date.month) % 12
        days = (today - birth_date).days
        return jsonify({"years": years, "months": months, "total_days": days})
    except Exception as e:
        return jsonify({"error": "Invalid date format (YYYY-MM-DD)"}), 400

# ==================== 6. TEXT CASE (تحويل النصوص) ====================

@app.route('/api/tools/text-case', methods=['POST'])
def text_case():
    data = request.get_json() or {}
    text = data.get('text', '')
    mode = data.get('mode', 'upper')
    if mode == 'upper':
        result = text.upper()
    elif mode == 'lower':
        result = text.lower()
    elif mode == 'title':
        result = text.title()
    else:
        result = text
    return jsonify({"result": result})

# ==================== 7. MERGE PDF (دمج PDF) ====================

@app.route('/api/tools/merge-pdf', methods=['POST'])
def merge_pdf():
    try:
        files = request.files.getlist('pdfs')
        if not files or len(files) < 2:
            return jsonify({"error": "Please provide at least 2 PDF files"}), 400
        merger = pypdf.PdfWriter()
        for pdf in files:
            merger.append(pdf)
        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)
        return send_file(output, mimetype='application/pdf', as_attachment=True, download_name="merged.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 8. IMG CONVERT (تحويل صيغ الصور) ====================

@app.route('/api/tools/convert-image', methods=['POST'])
def convert_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        file = request.files['image']
        target_format = request.form.get('format', 'png').lower()
        
        img = Image.open(file.stream)
        output = io.BytesIO()
        
        if target_format == 'jpg' or target_format == 'jpeg':
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output, format='JPEG')
            mimetype = 'image/jpeg'
        elif target_format == 'webp':
            img.save(output, format='WEBP')
            mimetype = 'image/webp'
        else:
            img.save(output, format='PNG')
            mimetype = 'image/png'
            
        output.seek(0)
        return send_file(output, mimetype=mimetype, as_attachment=True, download_name=f"converted.{target_format}")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 9. CURRENCY (محول العملات) ====================

@app.route('/api/tools/currency', methods=['POST'])
def convert_currency():
    try:
        data = request.get_json() or {}
        from_curr = data.get('from', 'USD').upper()
        to_curr = data.get('to', 'EUR').upper()
        amount = float(data.get('amount', 1))
        
        res = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_curr}", timeout=5)
        rates = res.json().get('rates', {})
        rate = rates.get(to_curr)
        
        if not rate:
            return jsonify({"error": "Currency not supported"}), 400
            
        converted = round(amount * rate, 2)
        return jsonify({"from": from_curr, "to": to_curr, "amount": amount, "result": converted, "rate": rate})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
