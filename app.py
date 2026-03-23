from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import cups
import subprocess
import time
import shutil

app = Flask(__name__)
CORS(app)

# Base folder = folder where this file lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SCAN_FOLDER = os.path.join(BASE_DIR, "scans")

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}
PRINTER_NAME = "Brother_DCP-7040"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SCAN_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_scanimage_path():
    path = shutil.which("scanimage")
    return path if path else "/usr/bin/scanimage"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "printer_folder": BASE_DIR,
        "upload_folder": UPLOAD_FOLDER,
        "scan_folder": SCAN_FOLDER
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


@app.route("/api/scan", methods=["POST"])
def scan_file():
    data = request.get_json(silent=True) or {}

    scan_format = data.get("format", "png").lower()
    mode = data.get("mode", "Color")
    resolution = str(data.get("resolution", "300"))

    if scan_format not in {"png", "jpg", "jpeg", "tif", "pnm"}:
        return jsonify({
            "ok": False,
            "error": "Unsupported scan format. Use png, jpg, jpeg, tif, or pnm."
        }), 400

    timestamp = int(time.time())
    filename = f"scan-{timestamp}.{scan_format}"
    filepath = os.path.join(SCAN_FOLDER, filename)

    scanimage_path = get_scanimage_path()

    cmd = [
        scanimage_path,
        "--format", scan_format,
        "--mode", mode,
        "--resolution", resolution
    ]

    try:
        with open(filepath, "wb") as out_file:
            result = subprocess.run(
                cmd,
                stdout=out_file,
                stderr=subprocess.PIPE,
                check=False
            )

        if result.returncode != 0:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

            error_text = result.stderr.decode("utf-8", errors="ignore").strip()
            return jsonify({
                "ok": False,
                "error": f"Scan failed: {error_text or 'unknown scanner error'}"
            }), 500

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return jsonify({
                "ok": False,
                "error": "Scan failed or returned empty file"
            }), 500

        file_url = f"http://192.168.1.64:5001/scans/{filename}"
        thumbnail_url = file_url if scan_format in {"png", "jpg", "jpeg"} else None

        return jsonify({
            "ok": True,
            "message": "Scan complete",
            "filename": filename,
            "downloadUrl": file_url,
            "thumbnailUrl": thumbnail_url
        })

    except FileNotFoundError:
        return jsonify({
            "ok": False,
            "error": "scanimage is not installed"
        }), 500

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route("/scans/<path:filename>", methods=["GET"])
def serve_scan(filename):
    return send_from_directory(SCAN_FOLDER, filename, as_attachment=False)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)