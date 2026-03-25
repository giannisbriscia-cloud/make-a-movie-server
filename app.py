from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, tempfile, os, uuid, json
app = Flask(__name__)
CORS(app)
@app.route("/health")
def health():
    return jsonify({"status": "ok"})
@app.route("/merge", methods=["POST"])
def merge():
    try:
        files = request.files.getlist("clips")
        soundtrack = request.files.get("soundtrack")
        ss = float(request.form.get("soundtrack_start", 0))
        fo = float(request.form.get("fade_out", 4))
        order = request.form.get("order", "")
        if not files: return jsonify({"error": "no clips"}), 400
        d = tempfile.mkdtemp()
        oi = [int(x) for x in order.split(",")] if order else list(range(len(files)))
        sv = {}
        for i,f in enumerate(files):
            p = os.path.join(d,f"c{i}.webm"); f.save(p); sv[i]=p
        cp = [sv[i] for i in oi if i in sv]
        lp = os.path.join(d,"list.txt")
        open(lp,"w").write("".join(f"file '{p}'
" for p in cp))
        mp = os.path.join(d,"merged.mp4")
        subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",lp,"-c","copy",mp],check=True,capture_output=True)
        op = os.path.join(d,f"out_{uuid.uuid4().hex[:8]}.mp4")
        if soundtrack:
            sp = os.path.join(d,"st.mp3"); soundtrack.save(sp)
            dur = float(json.loads(subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",mp],capture_output=True,text=True).stdout)["format"]["duration"])
            fs = max(0, dur - fo)
            subprocess.run(["ffmpeg","-y","-i",mp,"-ss",str(ss),"-i",sp,"-filter_complex",f"[1:a]atrim=start={ss},asetpts=PTS-STARTPTS,afade=t=out:st={fs}:d={fo}[sa];[0:a][sa]amix=inputs=2:duration=first[aout]","-map","0:v","-map","[aout]","-c:v","copy","-c:a","aac","-shortest",op],check=True,capture_output=True)
        else: op=mp
        return send_file(op,mimetype="video/mp4",as_attachment=True,download_name="make-a-movie.mp4")
    except Exception as e: return jsonify({"error": str(e)}), 500
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
