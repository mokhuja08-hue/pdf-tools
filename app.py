
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, after_this_request
from pypdf import PdfReader, PdfWriter
import tempfile
import subprocess
import shutil
import os

app = Flask(__name__)
app.secret_key = "pdf-toolbox"
app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024

def is_pdf(filename):
    return bool(filename and filename.lower().endswith(".pdf"))

def cleanup_dir(path):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/merge", methods=["POST"])
def merge():
    files = [f for f in request.files.getlist("pdfs") if is_pdf(f.filename)]
    if len(files) < 2:
        flash("Please select at least 2 PDF files.")
        return redirect(url_for("home"))

    tmp = tempfile.mkdtemp(prefix="pdfmerge_")
    output = os.path.join(tmp, "merged.pdf")

    try:
        writer = PdfWriter()
        for file in files:
            reader = PdfReader(file.stream)
            for page in reader.pages:
                writer.add_page(page)
        with open(output, "wb") as f:
            writer.write(f)
        writer.close()
    except Exception as e:
        cleanup_dir(tmp)
        flash("Could not merge these PDF files.")
        return redirect(url_for("home"))

    @after_this_request
    def clean(response):
        cleanup_dir(tmp)
        return response

    return send_file(output, as_attachment=True, download_name="merged.pdf",
                     mimetype="application/pdf")

@app.route("/compress", methods=["POST"])
def compress():
    file = request.files.get("pdf")
    quality = request.form.get("quality", "ebook")

    if not file or not is_pdf(file.filename):
        flash("Please select a PDF file.")
        return redirect(url_for("home"))

    gs = shutil.which("gs")
    if not gs:
        flash("Ghostscript was not found. In Terminal run: brew install ghostscript")
        return redirect(url_for("home"))

    settings = {
        "printer": "/printer",
        "ebook": "/ebook",
        "screen": "/screen",
    }
    pdf_setting = settings.get(quality, "/ebook")

    tmp = tempfile.mkdtemp(prefix="pdfcompress_")
    input_path = os.path.join(tmp, "input.pdf")
    output_path = os.path.join(tmp, "compressed.pdf")
    file.save(input_path)
    original_size = os.path.getsize(input_path)

    command = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={pdf_setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_path}",
        input_path,
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode != 0 or not os.path.exists(output_path):
            message = (result.stderr or result.stdout or "Unknown Ghostscript error").strip()
            cleanup_dir(tmp)
            flash("Compression failed: " + message[-350:])
            return redirect(url_for("home"))

        compressed_size = os.path.getsize(output_path)

        # Don't return a larger file as "compressed".
        if compressed_size >= original_size:
            cleanup_dir(tmp)
            flash("This PDF is already well compressed. The new file would not be smaller.")
            return redirect(url_for("home"))

    except subprocess.TimeoutExpired:
        cleanup_dir(tmp)
        flash("Compression took too long and was stopped.")
        return redirect(url_for("home"))
    except Exception as e:
        cleanup_dir(tmp)
        flash("Compression failed: " + str(e))
        return redirect(url_for("home"))

    @after_this_request
    def clean(response):
        cleanup_dir(tmp)
        return response

    response = send_file(
        output_path,
        as_attachment=True,
        download_name="compressed.pdf",
        mimetype="application/pdf",
    )
    response.headers["X-Original-Size"] = str(original_size)
    response.headers["X-Compressed-Size"] = str(compressed_size)
    return response

@app.errorhandler(413)
def too_large(_):
    flash("The PDF is larger than the 150 MB limit.")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
