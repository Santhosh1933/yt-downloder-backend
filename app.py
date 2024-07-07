from flask import Flask, request, jsonify, send_from_directory, url_for
from pytube import YouTube
from pytube.exceptions import RegexMatchError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import os
import shutil
import tempfile
from datetime import datetime, timedelta

app = Flask(__name__)

# Create a temporary directory for downloads
download_dir = tempfile.mkdtemp()

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def get_file_size(stream):
    try:
        # Get the file size in bytes
        file_size = stream.filesize
        # Convert bytes to megabytes (MB)
        file_size_mb = file_size / (1024 * 1024)
        return f"{file_size_mb:.2f} MB"
    except Exception as e:
        print(f"Error getting file size: {e}")
        return "Unknown"

@app.route('/')
def index():
    return 'Hello, World!'

@app.route('/get_video_qualities', methods=['GET'])
def get_video_qualities():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        yt = YouTube(url)
        video_streams = yt.streams.filter(progressive=True).all()
        qualities = [{
            'itag': stream.itag,
            'resolution': stream.resolution,
            'mime_type': stream.mime_type,
            'file_size': get_file_size(stream)
        } for stream in video_streams]
        return jsonify({'title': yt.title, 'qualities': qualities})
    except RegexMatchError:
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_video', methods=['GET'])
def download_video():
    url = request.args.get('url')
    itag = request.args.get('itag')
    if not url or not itag:
        return jsonify({'error': 'URL and itag are required'}), 400
    
    try:
        yt = YouTube(url)
        video_stream = yt.streams.get_by_itag(int(itag))
        download_path = os.path.join(download_dir, yt.title + ".mp4")
        video_stream.download(output_path=download_dir, filename=yt.title + ".mp4")

        # Schedule deletion of the file after 1 hour
        delete_time = datetime.now() + timedelta(hours=1)
        scheduler.add_job(delete_file, DateTrigger(run_date=delete_time), args=[download_path])

        download_url = url_for('serve_video', filename=yt.title + ".mp4", _external=True)
        return jsonify({'message': 'Download successful', 'title': yt.title, 'resolution': video_stream.resolution, 'file_size': get_file_size(video_stream), 'path': download_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/downloads/<filename>', methods=['GET'])
def serve_video(filename):
    return send_from_directory(download_dir, filename)

def delete_file(path):
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted file: {path}")

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=8000)
    finally:
        scheduler.shutdown()
        shutil.rmtree(download_dir)
