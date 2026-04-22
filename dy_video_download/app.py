from flask import Flask, request, jsonify, render_template
from Vibrato import Vibrato

app = Flask(__name__)
vibrato = Vibrato()

@app.route('/')
def index():
    """Render the main search page."""
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    """Search videos by keyword."""
    keyword = request.args.get('keyword')
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400

    try:
        results = vibrato.search_videos(keyword, min_likes=1000)
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Error in /search: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    """Download video by URL."""
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        vibrato.url = url
        vid, parsedAddr, _ = vibrato._Vibrato__get_real_url()
        return jsonify({"message": "Download successful", "video_id": vid, "download_url": parsedAddr})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)