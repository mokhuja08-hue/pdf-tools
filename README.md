
# PDF Tools v2 — Windows 95 Edition

Uses Ghostscript for real PDF compression.

## Replace your old version

You can simply use this folder instead of the previous one.

## Run

Open this folder in Terminal:

```bash
cd /path/to/pdf_tool_win95_v2
```

Activate your existing virtual environment if you already created it:

```bash
source ~/.venv/bin/activate
```

Install the small Python requirements:

```bash
pip install -r requirements.txt
```

Check Ghostscript:

```bash
gs --version
```

If that says command not found:

```bash
brew install ghostscript
```

Start:

```bash
python app.py
```

Then visit:

http://127.0.0.1:5000

## Compression modes

- High Quality: Ghostscript /printer
- Balanced: Ghostscript /ebook
- Smallest File: Ghostscript /screen
