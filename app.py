from flask import Flask,render_template,request,send_file,redirect,url_for,flash,after_this_request
from pypdf import PdfReader,PdfWriter
from PIL import Image,ImageOps
import tempfile,subprocess,shutil,os,io,json
app=Flask(__name__); app.secret_key=os.environ.get("SECRET_KEY","pdf-tools-v3"); app.config["MAX_CONTENT_LENGTH"]=150*1024*1024
def ext(n): return os.path.splitext(n or "")[1].lower()
def clean(p): shutil.rmtree(p,ignore_errors=True)
def image_pdf(f):
 f.stream.seek(0); im=ImageOps.exif_transpose(Image.open(f.stream))
 if im.mode in ("RGBA","LA"):
  bg=Image.new("RGB",im.size,"white"); bg.paste(im,mask=im.getchannel("A")); im=bg
 elif im.mode!="RGB": im=im.convert("RGB")
 b=io.BytesIO(); im.save(b,"PDF",resolution=150); b.seek(0); return b
@app.route("/")
def home(): return render_template("index.html")
@app.route("/merge",methods=["POST"])
def merge():
 files=[f for f in request.files.getlist("files") if ext(f.filename) in {".pdf",".png",".jpg",".jpeg"}]
 if len(files)<2: flash("Please select at least 2 files."); return redirect(url_for("home"))
 try:
  order=json.loads(request.form.get("file_order","[]"))
  if sorted(order)==list(range(len(files))): files=[files[i] for i in order]
 except: pass
 tmp=tempfile.mkdtemp(); out=os.path.join(tmp,"merged.pdf")
 try:
  w=PdfWriter()
  for f in files:
   r=PdfReader(f.stream if ext(f.filename)==".pdf" else image_pdf(f))
   for p in r.pages:w.add_page(p)
  with open(out,"wb") as x:w.write(x)
  w.close()
 except Exception as e: clean(tmp); flash("Merge failed: "+str(e)); return redirect(url_for("home"))
 @after_this_request
 def c(r): clean(tmp); return r
 return send_file(out,as_attachment=True,download_name="merged.pdf")
@app.route("/compress",methods=["POST"])
def compress():
 f=request.files.get("pdf"); q=request.form.get("quality","ebook")
 if not f or ext(f.filename)!=".pdf": flash("Please select a PDF."); return redirect(url_for("home"))
 gs=shutil.which("gs")
 if not gs: flash("Ghostscript was not found."); return redirect(url_for("home"))
 tmp=tempfile.mkdtemp(); inp=os.path.join(tmp,"in.pdf"); out=os.path.join(tmp,"compressed.pdf"); f.save(inp); old=os.path.getsize(inp)
 setting={"printer":"/printer","ebook":"/ebook","screen":"/screen"}.get(q,"/ebook")
 cmd=[gs,"-sDEVICE=pdfwrite","-dCompatibilityLevel=1.4",f"-dPDFSETTINGS={setting}","-dNOPAUSE","-dQUIET","-dBATCH",f"-sOutputFile={out}",inp]
 try:
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
  if r.returncode or not os.path.exists(out): raise Exception((r.stderr or r.stdout)[-300:])
  if os.path.getsize(out)>=old: clean(tmp); flash("This PDF is already well compressed."); return redirect(url_for("home"))
 except Exception as e: clean(tmp); flash("Compression failed: "+str(e)); return redirect(url_for("home"))
 @after_this_request
 def c(r): clean(tmp); return r
 return send_file(out,as_attachment=True,download_name="compressed.pdf")
@app.route("/page-count",methods=["POST"])
def count():
 try:return {"pages":len(PdfReader(request.files["pdf"].stream).pages)}
 except:return {"error":"Could not read PDF."},400
@app.route("/organize",methods=["POST"])
def organize():
 f=request.files.get("pdf")
 try:
  ops=json.loads(request.form.get("operations","[]")); r=PdfReader(f.stream); w=PdfWriter()
  for item in ops:
   p=r.pages[int(item["page"])]; rot=int(item.get("rotation",0))%360
   if rot:p.rotate(rot)
   w.add_page(p)
  tmp=tempfile.mkdtemp(); out=os.path.join(tmp,"organized.pdf")
  with open(out,"wb") as x:w.write(x)
  w.close()
 except Exception as e: flash("Organize failed: "+str(e)); return redirect(url_for("home"))
 @after_this_request
 def c(resp): clean(tmp); return resp
 return send_file(out,as_attachment=True,download_name="organized.pdf")
if __name__=="__main__": app.run(debug=True)
