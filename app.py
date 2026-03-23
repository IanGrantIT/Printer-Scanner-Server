from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import cups

app = Flask(__name__)
CORS(app)

# Base folder = folder where this file lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}
PRINTER_NAME = "Brother_DCP-7040"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "printer_folder": BASE_DIR,
        "upload_folder": UPLOAD_FOLDER
    })


@app.route("/api/print", methods=["POST"])
def print_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    file = request.files["file"]

    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Unsupported file type"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    copies = request.form.get("copies", "1")
    try:
        copies = int(copies)
        if copies < 1:
            copies = 1
        if copies > 50:
            copies = 50
    except ValueError:
        copies = 1

    try:
        conn = cups.Connection()
        options = {"copies": str(copies)}

        job_id = conn.printFile(
            PRINTER_NAME,
            filepath,
            f"Print Portal - {filename}",
            options
        )

        return jsonify({
            "ok": True,
            "message": "Print job submitted",
            "job_id": job_id,
            "printer": PRINTER_NAME,
            "filename": filename,
            "copies": copies
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)