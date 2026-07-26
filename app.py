import os, yt_dlp, tempfile
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route('/download', methods=['POST'])
def download_video():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        temp_dir = tempfile.mkdtemp()
        ydl_opts = {'format': 'best', 'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'), 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            return jsonify({'success': True, 'download_url': f"{request.host_url}get/{os.path.basename(file_path)}"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get/<filename>')
def get_file(filename):
    return send_file(os.path.join(tempfile.gettempdir(), filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
