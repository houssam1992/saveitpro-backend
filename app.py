import os
import yt_dlp
import tempfile
import re
import time
import traceback
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Supported platforms
SUPPORTED_PLATFORMS = [
    'YouTube', 'TikTok', 'Instagram', 'Facebook', 'Reddit', 
    'Twitter/X', 'Pinterest', 'Snapchat', 'Twitch', 'Vimeo'
]

# Temporary storage directory
TEMP_DIR = tempfile.gettempdir()

def cleanup_old_files():
    """دالة لمسح الملفات القديمة لتفادي امتلاء مساحة السيرفر"""
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

# ==================== ROOT ROUTES ====================

@app.route('/')
def root():
    return jsonify({
        "status": "running",
        "message": "SaveItPro API is Live! (Debug Mode)",
        "version": "1.0.2"
    }), 200

# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "SaveItPro Backend",
        "version": "1.0.2"
    }), 200

# ==================== VALIDATION ====================

@app.route('/api/validate', methods=['POST'])
def validate_url():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"valid": False, "error": "No URL provided"}), 400

        if not url.startswith(('http://', 'https://')):
            return jsonify({"valid": False, "error": "Invalid URL format"}), 400

        domain = urlparse(url).netloc.lower()
        
        supported_domains = [
            'youtube.com', 'youtu.be', 'tiktok.com', 'vm.tiktok.com',
            'instagram.com', 'instagr.am', 'facebook.com', 'fb.watch',
            'reddit.com', 'redd.it', 'twitter.com', 'x.com', 't.co',
            'pinterest.com', 'pin.it', 'snapchat.com', 'twitch.tv', 'vimeo.com'
        ]

        is_valid = any(supported_domain in domain for supported_domain in supported_domains)

        return jsonify({
            "valid": is_valid,
            "domain": domain,
            "message": "URL is valid" if is_valid else "Platform not supported"
        }), 200

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 400

# ==================== PLATFORMS ====================

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    return jsonify({
        "platforms": SUPPORTED_PLATFORMS,
        "count": len(SUPPORTED_PLATFORMS)
    }), 200

# ==================== QUALITY OPTIONS ====================

@app.route('/api/qualities', methods=['POST'])
def get_qualities():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"qualities": ["best", "1080", "720", "480", "360"]}), 200

        qualities = ["best", "2160", "1440", "1080", "720", "480", "360", "worst"]

        return jsonify({
            "qualities": qualities,
            "default": "best"
        }), 200

    except Exception as e:
        return jsonify({"qualities": ["best", "1080", "720", "480", "360"], "error": str(e)}), 200

# ==================== DOWNLOAD ====================

@app.route('/api/download', methods=['POST'])
def download_media():
    try:
        cleanup_old_files()

        data = request.get_json() or {}
        url = data.get('url', '').strip()

        if not url or not url.startswith(('http://', 'https://')):
            return jsonify({"success": False, "status": "error", "error": "Invalid or no URL provided"}), 400

        unique_id = os.urandom(6).hex()
        base_filename = f"saveitpro_{unique_id}"

        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(TEMP_DIR, f'{base_filename}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 15,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            final_filename = os.path.basename(file_path)

            download_url = f"{request.host_url}api/get/{final_filename}"
            safe_title = re.sub(r'[^a-zA-Z0-9\s_-]', '', info.get('title', 'download'))

            return jsonify({
                "success": True,
                "status": "success",
                "downloadUrl": download_url,
                "filename": final_filename,
                "title": safe_title,
                "message": "Download ready"
            }), 200

    except Exception as e:
        # طباعة تفاصيل الخطأ الكاملة لمرفق الإحصائيات وسجلات السيرفر
        error_details = traceback.format_exc()
        print("=== CRITICAL DOWNLOAD ERROR ===")
        print(error_details)
        print("===============================")
        
        return jsonify({
            "success": False,
            "status": "error",
            "error": str(e),
            "traceback": error_details
        }), 500

# ==================== FILE SERVING ====================

@app.route('/api/get/<filename>', methods=['GET'])
def get_file(filename):
    try:
        if '..' in filename or '/' in filename or not filename.startswith('saveitpro_'):
            return jsonify({"error": "Invalid filename"}), 400

        file_path = os.path.join(TEMP_DIR, filename)
        
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename
            )

        return jsonify({"error": "File not found or expired"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "status": "error", "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "status": "error",
        "error": "Internal server error",
        "details": str(error)
    }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
