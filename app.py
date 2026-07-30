import os
import yt_dlp
import tempfile
import re
import time
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
                    # مسح الملفات التي مر عليها أكثر من 30 دقيقة (1800 ثانية)
                    file_age = current_time - os.path.getctime(filepath)
                    if file_age > 1800:
                        os.remove(filepath)
    except Exception as e:
        pass # تجاهل الأخطاء لكي لا يتوقف التحميل إذا فشل المسح

# ==================== ROOT ROUTES ====================

@app.route('/')
def root():
    return jsonify({
        "status": "running",
        "message": "SaveItPro API is Live! (Optimized)",
        "version": "1.0.1"
    }), 200

# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "SaveItPro Backend",
        "version": "1.0.1"
    }), 200

# ==================== VALIDATION ====================

@app.route('/api/validate', methods=['POST'])
def validate_url():
    try:
        data = request.get_json()
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
        return jsonify({"valid": False, "error": str(e)}), 500

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
        data = request.get_json()
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
        # تشغيل دالة التنظيف قبل كل عملية تحميل جديدة
        cleanup_old_files()

        data = request.get_json()
        url = data.get('url', '').strip()
        quality = data.get('quality', 'best')
        format_type = data.get('format', 'mp4')

        if not url or not url.startswith(('http://', 'https://')):
            return jsonify({"success": False, "status": "error", "error": "Invalid or no URL provided"}), 400

        # إعداد جودة التحميل
        format_spec = 'best'
        if quality != 'best':
            format_spec = 'worst' if quality == 'worst' else f'best[height<={quality}]'

        # اسم ملف فريد وآمن لتفادي مشاكل Gunicorn
        unique_id = os.urandom(6).hex()
        base_filename = f"saveitpro_{unique_id}"
        
        ydl_opts = {
            'format': format_spec,
            # حفظ الملف مباشرة في TEMP_DIR باسم يبدأ بـ saveitpro
            'outtmpl': os.path.join(TEMP_DIR, f'{base_filename}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15, # تقليل وقت الانتظار لتفادي سقوط السيرفر (Timeout)
            # 'cookiefile': 'cookies.txt', # نزع علامة # إذا كان لديك ملف كوكيز لانستغرام وتيك توك
        }

        # إعدادات الصوت
        if format_type in ['mp3', 'wav']:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3' if format_type == 'mp3' else 'wav',
                'preferredquality': '192' if format_type == 'mp3' else '44100',
            }]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # استخراج اسم الملف النهائي بعد التحميل
            file_path = ydl.prepare_filename(info)
            if format_type in ['mp3', 'wav']:
                # تحديث الامتداد إذا تم تحويله لصوت
                file_path = os.path.splitext(file_path)[0] + f'.{format_type}'
            
            final_filename = os.path.basename(file_path)

            download_url = f"{request.host_url}api/get/{final_filename}"

            # تنظيف العنوان من الرموز العجيبة
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
        error_msg = str(e)
        if 'HTTP Error 429' in error_msg:
            return jsonify({"success": False, "status": "error", "error": "Rate limited. Please wait a moment."}), 429
        elif 'Unsupported URL' in error_msg or 'No video found' in error_msg:
            return jsonify({"success": False, "status": "error", "error": "Invalid URL or unsupported platform."}), 400
        else:
            return jsonify({"success": False, "status": "error", "error": error_msg}), 500

# ==================== FILE SERVING ====================

@app.route('/api/get/<filename>', methods=['GET'])
def get_file(filename):
    try:
        # حماية ضد التلاعب بمسار الملفات
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
        return jsonify({"error": str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "status": "error", "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "status": "error", "error": "Internal server error"}), 500

if __name__ == '__main__':
    pass
