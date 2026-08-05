import os
import tempfile
import io
import random
import string
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import pypdf

app = Flask(__name__)

# إعدادات CORS للسماح بالاتصال من نطاق الموقع
CORS(app, resources={r"/*": {"origins": ["https://saveitpro.co", "https://www.saveitpro.co"]}})

# ==================== GENERAL & ABOUT ROUTES ====================

@app.route('/')
def root():
    return jsonify({
        "status": "running",
        "message": "SaveItPro API v2.0 is Live",
        "version": "2.0.0"
    }), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "SaveItPro Backend"}), 200

@app.route('/api/about', methods=['GET'])
def get_about_info():
    """مسار يرجع معلومات القصة، الشعار، الاتصال، وسياسة الخصوصية"""
    return jsonify({
        "app_name": "SaveItPro",
        "slogan": "Fast, Secure & Free Privacy-First Digital Tools",
        "founder": {
            "name": "Houssem Ghenimi",
            "role": "Independent Web Developer & Founder",
            "story": "I split my days between installing B13 drywall on construction sites and writing code. The daily endurance and work ethic I've built are poured directly into SaveItPro, offering fast, completely free, and privacy-focused digital tools to users around the globe.",
            "whatsapp": "+213662192505",
            "whatsapp_link": "https://wa.me/213662192505"
        },
        "privacy": {
            "title": "Strict Zero Data Retention",
            "description": "Your files are never stored, viewed, or shared. All processing happens during your active session and is wiped immediately upon completion. What happens on SaveItPro, stays on your device."
        }
    }), 200

# ==================== ACTIVE TOOLS ====================

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

@app.route('/api/tools/generate-password', methods=['GET', 'POST'])
def generate_password():
    data = request.get_json() or {}
    length = int(data.get('length', 12))
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = ''.join(random.choice(chars) for _ in range(length))
    return jsonify({"password": password})

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

@app.route('/api/tools/convert-image', methods=['POST'])
def convert_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        file = request.files['image']
        target_format = request.form.get('format', 'png').lower()
        
        img = Image.open(file.stream)
        output = io.BytesIO()
        
        if target_format in ['jpg', 'jpeg']:
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
