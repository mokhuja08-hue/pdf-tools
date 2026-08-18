
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageOps
import tempfile
import subprocess
import shutil
import os
import io
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pdf-tools-v5")
app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg"}

def ext(name):
    return os.path.splitext(name or "")[1].lower()

def clean(path):
    shutil.rmtree(path, ignore_errors=True)

def image_to_pdf(uploaded):
    uploaded.stream.seek(0)
    im = ImageOps.exif_transpose(Image.open(uploaded.stream))

    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, "white")
        alpha = im.getchannel("A")
        bg.paste(im, mask=alpha)
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")

    out = io.BytesIO()
    im.save(out, format="PDF", resolution=150)
    out.seek(0)
    return out

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/merge", methods=["POST"])
def merge():
    files = [f for f in request.files.getlist("files") if f and ext(f.filename) in ALLOWED]

    if len(files) < 2:
        return jsonify({"ok": False, "error": "Select at least 2 files."}), 400

    try:
        order = json.loads(request.form.get("file_order", "[]"))
        if sorted(order) == list(range(len(files))):
            files = [files[i] for i in order]
    except Exception:
        pass

    tmp = tempfile.mkdtemp(prefix="pdfmerge_")
    output = os.path.join(tmp, "merged.pdf")

    try:
        writer = PdfWriter()

        for f in files:
            if ext(f.filename) == ".pdf":
                f.stream.seek(0)
                reader = PdfReader(f.stream)
            else:
                reader = PdfReader(image_to_pdf(f))

            for page in reader.pages:
                writer.add_page(page)

        with open(output, "wb") as out:
            writer.write(out)

        writer.close()

    except Exception as e:
        clean(tmp)
        return jsonify({"ok": False, "error": f"Merge failed: {e}"}), 500

    @after_this_request
    def cleanup(response):
        clean(tmp)
        return response

    return send_file(
        output,
        as_attachment=True,
        download_name="merged.pdf",
        mimetype="application/pdf"
    )

@app.route("/compress", methods=["POST"])
def compress():
    f = request.files.get("pdf")
    quality = request.form.get("quality", "ebook")

    if not f or ext(f.filename) != ".pdf":
        return jsonify({"ok": False, "error": "Select a PDF file."}), 400

    gs = shutil.which("gs")
    if not gs:
        return jsonify({"ok": False, "error": "Ghostscript was not found on the server."}), 500

    setting = {
        "printer": "/printer",
        "ebook": "/ebook",
        "screen": "/screen"
    }.get(quality, "/ebook")

    tmp = tempfile.mkdtemp(prefix="pdfcompress_")
    inp = os.path.join(tmp, "input.pdf")
    out = os.path.join(tmp, "compressed.pdf")
    f.save(inp)
    original = os.path.getsize(inp)

    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={out}",
        inp
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

        if result.returncode != 0 or not os.path.exists(out):
            msg = (result.stderr or result.stdout or "Unknown Ghostscript error")[-350:]
            raise Exception(msg)

        compressed = os.path.getsize(out)

        if compressed >= original:
            clean(tmp)
            return jsonify({
                "ok": False,
                "error": "This PDF is already well compressed. A new file would not be smaller."
            }), 400

    except subprocess.TimeoutExpired:
        clean(tmp)
        return jsonify({"ok": False, "error": "Compression timed out."}), 500
    except Exception as e:
        clean(tmp)
        return jsonify({"ok": False, "error": f"Compression failed: {e}"}), 500

    @after_this_request
    def cleanup(response):
        clean(tmp)
        return response

    return send_file(
        out,
        as_attachment=True,
        download_name="compressed.pdf",
        mimetype="application/pdf"
    )

@app.route("/page-count", methods=["POST"])
def page_count():
    f = request.files.get("pdf")

    if not f or ext(f.filename) != ".pdf":
        return jsonify({"ok": False, "error": "Select a PDF."}), 400

    try:
        reader = PdfReader(f.stream)
        return jsonify({"ok": True, "pages": len(reader.pages)})
    except Exception:
        return jsonify({"ok": False, "error": "Could not read this PDF."}), 400

@app.route("/organize", methods=["POST"])
def organize():
    f = request.files.get("pdf")

    if not f or ext(f.filename) != ".pdf":
        return jsonify({"ok": False, "error": "Select a PDF."}), 400

    try:
        operations = json.loads(request.form.get("operations", "[]"))

        if not operations:
            return jsonify({"ok": False, "error": "Load pages first."}), 400

        reader = PdfReader(f.stream)
        writer = PdfWriter()

        for item in operations:
            page_index = int(item["page"])
            rotation = int(item.get("rotation", 0)) % 360

            page = reader.pages[page_index]

            if rotation:
                page.rotate(rotation)

            writer.add_page(page)

        tmp = tempfile.mkdtemp(prefix="pdforganize_")
        out = os.path.join(tmp, "organized.pdf")

        with open(out, "wb") as fp:
            writer.write(fp)

        writer.close()

    except Exception as e:
        try:
            clean(tmp)
        except Exception:
            pass

        return jsonify({"ok": False, "error": f"Organize failed: {e}"}), 500

    @after_this_request
    def cleanup(response):
        clean(tmp)
        return response

    return send_file(
        out,
        as_attachment=True,
        download_name="organized.pdf",
        mimetype="application/pdf"
    )

@app.errorhandler(413)
def too_large(_):
    return jsonify({"ok": False, "error": "Upload exceeds the 150 MB limit."}), 413

if __name__ == "__main__":
    app.run(debug=True)
