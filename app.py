import os
import yt_dlp
import tempfile
import re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Supported platforms
SUPPORTED_PLATFORMS = [
    'YouTube',
    'TikTok',
    'Instagram',
    'Facebook',
    'Reddit',
    'Twitter/X',
    'Pinterest',
    'Snapchat',
    'Twitch',
    'Vimeo'
]

# Temporary storage for downloaded files
TEMP_DIR = tempfile.gettempdir()
DOWNLOADS = {}

# ==================== ROOT ROUTES ====================

@app.route('/')
def root():
    """Root endpoint - confirms API is running."""
    return jsonify({
        "status": "running",
        "message": "SaveItPro API is Live!",
        "version": "1.0.0"
    }), 200

# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "SaveItPro Backend",
        "version": "1.0.0"
    }), 200

# ==================== VALIDATION ====================

@app.route('/api/validate', methods=['POST'])
def validate_url():
    """Validate if URL is from a supported platform."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"valid": False, "error": "No URL provided"}), 400

        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return jsonify({"valid": False, "error": "Invalid URL format"}), 400

        # Check if URL is from supported platform
        domain = urlparse(url).netloc.lower()
        
        supported_domains = [
            'youtube.com', 'youtu.be',
            'tiktok.com', 'vm.tiktok.com',
            'instagram.com', 'instagr.am',
            'facebook.com', 'fb.watch',
            'reddit.com', 'redd.it',
            'twitter.com', 'x.com', 't.co',
            'pinterest.com', 'pin.it',
            'snapchat.com',
            'twitch.tv',
            'vimeo.com'
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
    """Get list of supported platforms."""
    return jsonify({
        "platforms": SUPPORTED_PLATFORMS,
        "count": len(SUPPORTED_PLATFORMS)
    }), 200

# ==================== QUALITY OPTIONS ====================

@app.route('/api/qualities', methods=['POST'])
def get_qualities():
    """Get available quality options for a URL."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"qualities": ["best", "1080", "720", "480", "360"]}), 200

        # Default quality options
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
    """Download media from URL."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        quality = data.get('quality', 'best')
        format_type = data.get('format', 'mp4')

        if not url:
            return jsonify({
                "success": False,
                "status": "error",
                "error": "No URL provided"
            }), 400

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            return jsonify({
                "success": False,
                "status": "error",
                "error": "Invalid URL format"
            }), 400

        # Create temporary directory for this download
        download_temp_dir = os.path.join(TEMP_DIR, f"saveitpro_{os.urandom(4).hex()}")
        os.makedirs(download_temp_dir, exist_ok=True)

        # Configure yt-dlp options
        format_spec = 'best'
        if quality != 'best':
            if quality == 'worst':
                format_spec = 'worst'
            else:
                # Map quality to format spec (e.g., "1080" -> "best[height<=1080]")
                format_spec = f'best[height<={quality}]'

        # Handle format conversion
        if format_type == 'mp3':
            format_spec = 'bestaudio/best'
            postprocessor_args = ['-acodec', 'libmp3lame', '-aq', '4']
        elif format_type == 'wav':
            format_spec = 'bestaudio/best'
            postprocessor_args = ['-acodec', 'pcm_s16le', '-ar', '44100']
        else:
            postprocessor_args = []

        ydl_opts = {
            'format': format_spec,
            'outtmpl': os.path.join(download_temp_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
        }

        # Add audio-only options for audio formats
        if format_type in ['mp3', 'wav']:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3' if format_type == 'mp3' else 'wav',
                'preferredquality': '192' if format_type == 'mp3' else '44100',
            }]

        # Download using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            filename = os.path.basename(file_path)
            
            # Sanitize filename: remove special characters and keep only alphanumeric, dash, underscore, dot
            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
            safe_filename = re.sub(r'_+', '_', safe_filename)  # Replace multiple underscores with single
            
            # Ensure filename is not empty and has valid extension
            if not safe_filename or '.' not in safe_filename:
                ext = os.path.splitext(filename)[1] or '.mp4'
                safe_filename = f"download_{os.urandom(4).hex()}{ext}"

            # Store download info with safe filename
            DOWNLOADS[safe_filename] = {
                'path': file_path,
                'title': info.get('title', 'download'),
                'format': format_type
            }

            # Generate download URL
            download_url = f"{request.host_url}api/get/{safe_filename}"

            return jsonify({
                "success": True,
                "status": "success",
                "downloadUrl": download_url,
                "filename": safe_filename,
                "title": info.get('title', 'download'),
                "message": "Download ready"
            }), 200

    except Exception as e:
        error_msg = str(e)
        
        # Handle specific errors
        if 'HTTP Error 429' in error_msg:
            return jsonify({
                "success": False,
                "status": "error",
                "error": "Rate limited. Please wait a moment and try again."
            }), 429
        elif 'Unsupported URL' in error_msg or 'No video found' in error_msg:
            return jsonify({
                "success": False,
                "status": "error",
                "error": "Invalid URL or unsupported platform."
            }), 400
        else:
            return jsonify({
                "success": False,
                "status": "error",
                "error": error_msg
            }), 500

# ==================== FILE SERVING ====================

@app.route('/api/get/<filename>', methods=['GET'])
def get_file(filename):
    """Serve downloaded file."""
    try:
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename:
            return jsonify({"error": "Invalid filename"}), 400

        if filename in DOWNLOADS:
            file_path = DOWNLOADS[filename]['path']
            if os.path.exists(file_path):
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=filename
                )

        return jsonify({"error": "File not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        "success": False,
        "status": "error",
        "error": "Endpoint not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        "success": False,
        "status": "error",
        "error": "Internal server error"
    }), 500

# ==================== MAIN ====================
if __name__ == '__main__':
    # Gunicorn will handle running the app on Render
    # For local development, uncomment below:
    # port = int(os.environ.get('PORT', 10000))
    # app.run(host='0.0.0.0', port=port, debug=False)
    pass
