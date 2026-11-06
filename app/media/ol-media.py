#!/usr/bin/env python3
"""OpenLand media toolkit (runs inside the built-in Linux computer).

Everything here is real: images/videos come from real generators, edits are rendered by ffmpeg.
Outputs go to /root/OpenLand/media. Each command prints one JSON line on success.

  ol-media setup                       install ffmpeg (static arm64 build) + fonts on first use
  ol-media image  "prompt" [--w 768 --h 1344 --seed N --model flux]
  ol-media video  "prompt" [--secs 3 --w 512 --h 704 --image path]   LTX-Video (open source) via public Space
  ol-media motion IMAGE --preset push_in [--secs 4 --w 1080 --h 1920]  camera-motion clip from a still (ffmpeg, NOT AI video)
  ol-media stock  images|audio "query" [--n 6 --download]
  ol-media shorts --style hormozi IN1 [IN2 ...] [--hook "text" --music file --max 60 --no-captions]
  ol-media render PROJECT.json [--out file.mp4 --preview]
  ol-media captions IN [--model base.en]   -> .srt + word json
  ol-media local list|install ID|remove ID|add URL NAME|gen "prompt" [--model ID --steps 8 --w 512 --h 512]
  ol-media serve                       http://127.0.0.1:8765/ serves /root/OpenLand for previews
"""
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request, shutil, random, math, argparse, hashlib

HOME = '/root/OpenLand'
MEDIA = HOME + '/media'
STOCK = HOME + '/stock'
BIN = '/opt/openland/bin'
MODELS = '/opt/openland/models'
FONTS = '/opt/openland/fonts'
UA = {'User-Agent': 'OpenLand/5.3 (+https://openland-downloads.surge.sh)'}
for d in (MEDIA, STOCK, BIN, MODELS, FONTS): os.makedirs(d, exist_ok=True)
os.environ['PATH'] = BIN + ':' + os.environ.get('PATH', '')
ARCH = os.uname().machine
RELEASE_TOOLS = 'https://github.com/Jmcall87/openland-releases/releases/download/v5.3.0/'

def out(obj): print(json.dumps(obj)); sys.stdout.flush()
def log(*a): print(*a, file=sys.stderr); sys.stderr.flush()
def die(msg): out({'ok': False, 'error': msg}); sys.exit(1)
def stamp(prefix, ext): return f"{MEDIA}/{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{random.randint(100,999)}.{ext}"

def get(url, dest=None, data=None, headers=None, timeout=300):
    h = dict(UA); h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if dest is None: return r.read()
        tmp = dest + '.part'
        with open(tmp, 'wb') as f: shutil.copyfileobj(r, f, 1 << 20)
        os.replace(tmp, dest); return dest

def download_resume(url, dest, label=''):
    tmp = dest + '.part'
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    h = dict(UA)
    if have: h['Range'] = f'bytes={have}-'
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get('Content-Length') or 0) + (have if r.status == 206 else 0)
        mode = 'ab' if r.status == 206 else 'wb'
        if r.status != 206: have = 0
        last = 0
        with open(tmp, mode) as f:
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b); have += len(b)
                if time.time() - last > 1:
                    last = time.time(); log(f'PROGRESS {label} {have} {total}')
    os.replace(tmp, dest); return dest

def run(cmd, check=True, quiet=True):
    log('$ ' + ' '.join(cmd) if isinstance(cmd, list) else cmd)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and p.returncode != 0: die((p.stderr or p.stdout)[-1500:])
    return p

# ---------------- setup ----------------
def have_ffmpeg(): return shutil.which('ffmpeg') is not None
def setup(_=None):
    if not have_ffmpeg():
        if ARCH == 'aarch64':
            log('STEP Downloading ffmpeg (19 MB, once)')
            t = '/tmp/ffmpeg.tar.xz'
            try:
                download_resume('https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz', t, 'ffmpeg')
                run(['tar', '-xJf', t, '-C', '/tmp'])
                d = [x for x in os.listdir('/tmp') if x.startswith('ffmpeg-') and x.endswith('-static')][0]
                for b in ('ffmpeg', 'ffprobe'): shutil.move(f'/tmp/{d}/{b}', f'{BIN}/{b}')
                shutil.rmtree(f'/tmp/{d}', True); os.remove(t)
            except Exception as e:
                log('static ffmpeg failed, using apt:', e)
                run('DEBIAN_FRONTEND=noninteractive apt-get update -q && apt-get install -y -q --no-install-recommends ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*', check=True)
        else:
            run('apt-get install -y -q ffmpeg', check=True)
    font('Anton'); font('Montserrat')
    out({'ok': True, 'ffmpeg': shutil.which('ffmpeg')})

FONT_URLS = {
    'Anton': 'https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf',
    'Montserrat': 'https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-800-normal.ttf',
}
def font(name):
    p = f'{FONTS}/{name}.ttf'
    if not os.path.exists(p):
        try: get(FONT_URLS[name], p, timeout=60)
        except Exception as e: log('font', name, e); return '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    return p

def probe(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', path], stdout=subprocess.PIPE, text=True)
    try: j = json.loads(p.stdout)
    except Exception: return {'duration': 0, 'w': 0, 'h': 0, 'audio': False}
    v = next((s for s in j.get('streams', []) if s.get('codec_type') == 'video'), {})
    a = any(s.get('codec_type') == 'audio' for s in j.get('streams', []))
    return {'duration': float(j.get('format', {}).get('duration') or 0), 'w': v.get('width', 0), 'h': v.get('height', 0), 'audio': a}

# ---------------- generators ----------------
def image(a):
    # Pollinations keyless endpoint (open models served by pollinations.ai; no API key)
    q = {'width': a.w, 'height': a.h, 'nologo': 'true', 'seed': a.seed if a.seed is not None else random.randint(1, 10**6)}
    if a.model: q['model'] = a.model
    url = 'https://image.pollinations.ai/prompt/' + urllib.parse.quote(a.prompt) + '?' + urllib.parse.urlencode(q)
    dest = stamp('image', 'jpg')
    for i in range(3):
        try:
            get(url, dest, timeout=180)
            if os.path.getsize(dest) > 5000: break
        except Exception as e: log('retry', e); time.sleep(3)
    else: die('image generator did not answer')
    out({'ok': True, 'path': dest, 'source': 'Pollinations (keyless)', 'url': url, 'prompt': a.prompt})

LTX = 'https://lightricks-ltx-video-distilled.hf.space/gradio_api'
def upload_gradio(base, path):
    import uuid
    b = '----ol' + uuid.uuid4().hex
    data = open(path, 'rb').read()
    body = (f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="{os.path.basename(path)}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + data + f'\r\n--{b}--\r\n'.encode()
    r = json.loads(get(base + '/upload', data=body, headers={'Content-Type': 'multipart/form-data; boundary=' + b}))
    return {'path': r[0], 'meta': {'_type': 'gradio.FileData'}}

def video(a):
    secs = max(1, min(8, a.secs))
    img = upload_gradio(LTX, a.image) if a.image else None
    mode = 'image-to-video' if img else 'text-to-video'
    ep = 'image_to_video' if img else 'text_to_video'
    payload = {'data': [a.prompt, 'worst quality, inconsistent motion, blurry, jittery, distorted', img, None, a.h, a.w, mode, secs, 9, random.randint(1, 2**31), True, 1, False]}
    try:
        ev = json.loads(get(f'{LTX}/call/{ep}', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, timeout=60))['event_id']
        res = get(f'{LTX}/call/{ep}/{ev}', timeout=600).decode()
        m = re.search(r'event: complete\s*\ndata: (.*)', res)
        if not m: raise RuntimeError(res[-400:])
        url = json.loads(m.group(1))[0]['video']['url']
        dest = stamp('video', 'mp4'); get(url, dest)
        out({'ok': True, 'path': dest, 'source': 'LTX-Video (open source, Lightricks) via public Hugging Face Space', 'ai': True, 'prompt': a.prompt})
    except Exception as e:
        if a.no_fallback: die(f'LTX-Video endpoint failed: {e}')
        log('LTX failed, falling back to image + camera motion:', e)
        class A: pass
        i = A(); i.prompt = a.prompt; i.w = 768; i.h = 1344 if a.h > a.w else 768; i.seed = None; i.model = None
        old = sys.stdout; import io; sys.stdout = io.StringIO(); image(i); r = json.loads(sys.stdout.getvalue().strip().splitlines()[-1]); sys.stdout = old
        m = A(); m.image = r['path']; m.preset = 'push_in'; m.secs = secs; m.w = 720 if a.h > a.w else 1280; m.h = 1280 if a.h > a.w else 720
        p = motion(m, emit=False)
        out({'ok': True, 'path': p, 'source': 'FALLBACK: AI image + ffmpeg camera motion (not AI video). LTX-Video was unavailable: ' + str(e)[:160], 'ai': False})

PRESETS = {  # Higgsfield-style camera moves rendered with ffmpeg zoompan on a still
    'push_in':   ("min(1+0.25*on/{n},1.25)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    'pull_out':  ("max(1.25-0.25*on/{n},1)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    'pan_left':  ("1.2", "(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),
    'pan_right': ("1.2", "(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),
    'tilt_up':   ("1.2", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{n})"),
    'tilt_down': ("1.2", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*on/{n}"),
    'crash_zoom':("if(lt(on,{n}*0.3),1+1.0*on/({n}*0.3),2)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    'dolly_zoom':("1+0.35*sin(PI*on/{n})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    'orbit':     ("1.25", "iw/2-(iw/zoom/2)+(iw/12)*sin(2*PI*on/{n})", "ih/2-(ih/zoom/2)+(ih/24)*cos(2*PI*on/{n})"),
    'handheld':  ("1.12", "iw/2-(iw/zoom/2)+6*sin(on/3)+4*sin(on/7)", "ih/2-(ih/zoom/2)+5*cos(on/4)+3*sin(on/9)"),
    'static':    ("1", "0", "0"),
}
def motion(a, emit=True):
    fps = 30; n = int(a.secs * fps)
    z, x, y = [s.format(n=n) for s in PRESETS.get(a.preset, PRESETS['push_in'])]
    dest = stamp('motion-' + a.preset, 'mp4')
    vf = f"scale={a.w*2}:{a.h*2}:force_original_aspect_ratio=increase,crop={a.w*2}:{a.h*2},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={a.w}x{a.h}:fps={fps},format=yuv420p"
    run(['ffmpeg', '-y', '-loop', '1', '-i', a.image, '-vf', vf, '-t', str(a.secs), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', dest])
    if emit: out({'ok': True, 'path': dest, 'source': f'ffmpeg camera motion "{a.preset}" on a still image (not AI video)', 'ai': False})
    return dest

# ---------------- stock ----------------
def stock(a):
    res = []
    if a.kind == 'images':
        try:
            j = json.loads(get('https://api.openverse.org/v1/images/?' + urllib.parse.urlencode({'q': a.query, 'page_size': a.n, 'license_type': 'commercial,modification'}), timeout=30))
            for r in j.get('results', []):
                res.append({'title': r.get('title'), 'url': r.get('url'), 'thumb': r.get('thumbnail'), 'creator': r.get('creator'), 'license': (r.get('license') or '').upper() + ' ' + (r.get('license_version') or ''), 'license_url': r.get('license_url'), 'page': r.get('foreign_landing_url'), 'source': 'Openverse/' + (r.get('source') or ''), 'attribution': r.get('attribution')})
        except Exception as e: log('openverse', e)
        if len(res) < a.n:
            try:
                q = urllib.parse.urlencode({'action': 'query', 'format': 'json', 'generator': 'search', 'gsrsearch': 'filetype:bitmap ' + a.query, 'gsrnamespace': 6, 'gsrlimit': a.n, 'prop': 'imageinfo', 'iiprop': 'url|extmetadata', 'iiurlwidth': 1280})
                j = json.loads(get('https://commons.wikimedia.org/w/api.php?' + q, timeout=30))
                for p in (j.get('query', {}).get('pages', {}) or {}).values():
                    ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {})
                    res.append({'title': p.get('title'), 'url': ii.get('thumburl') or ii.get('url'), 'thumb': ii.get('thumburl'), 'creator': re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', '')), 'license': md.get('LicenseShortName', {}).get('value'), 'license_url': md.get('LicenseUrl', {}).get('value'), 'page': ii.get('descriptionurl'), 'source': 'Wikimedia Commons'})
            except Exception as e: log('commons', e)
    else:
        j = json.loads(get('https://api.openverse.org/v1/audio/?' + urllib.parse.urlencode({'q': a.query, 'page_size': a.n, 'license_type': 'commercial'}), timeout=30))
        for r in j.get('results', []):
            res.append({'title': r.get('title'), 'url': r.get('url'), 'duration_ms': r.get('duration'), 'creator': r.get('creator'), 'license': (r.get('license') or '').upper() + ' ' + (r.get('license_version') or ''), 'license_url': r.get('license_url'), 'page': r.get('foreign_landing_url'), 'source': 'Openverse/' + (r.get('source') or ''), 'attribution': r.get('attribution')})
    res = res[:a.n]
    if a.download:
        for i, r in enumerate(res):
            ext = 'mp3' if a.kind == 'audio' else 'jpg'
            m = re.search(r'\.(jpe?g|png|webp|mp3|ogg|wav|flac)(\?|$)', r['url'] or '', re.I)
            if m: ext = m.group(1).lower()
            p = f"{STOCK}/{a.kind}-{re.sub('[^a-z0-9]+','-',a.query.lower())[:30]}-{i}.{ext}"
            try: get(r['url'], p, timeout=120); r['path'] = p
            except Exception as e: r['error'] = str(e)[:100]
            json.dump(r, open(p + '.license.json', 'w'), indent=1)
    out({'ok': True, 'kind': a.kind, 'query': a.query, 'results': res})

# ---------------- captions (whisper.cpp) ----------------
WHISPER_MODELS = {'tiny.en': 'ggml-tiny.en.bin', 'base.en': 'ggml-base.en.bin', 'small.en': 'ggml-small.en.bin', 'base': 'ggml-base.bin'}
def whisper_bin():
    w = shutil.which('whisper-cli')
    if w: return w
    if ARCH == 'aarch64':
        p = f'{BIN}/whisper-cli'
        download_resume(RELEASE_TOOLS + 'whisper-cli-aarch64', p, 'whisper'); os.chmod(p, 0o755); return p
    die('whisper-cli not found')
def transcribe(path, model='base.en'):
    mf = f'{MODELS}/{WHISPER_MODELS.get(model, "ggml-base.en.bin")}'
    if not os.path.exists(mf):
        log('STEP Downloading Whisper', model)
        download_resume('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/' + os.path.basename(mf), mf, 'whisper-model')
    wav = '/tmp/ol-asr.wav'
    run(['ffmpeg', '-y', '-i', path, '-vn', '-ac', '1', '-ar', '16000', wav])
    base = '/tmp/ol-asr'
    run([whisper_bin(), '-m', mf, '-f', wav, '-ojf', '-of', base, '-ml', '1', '-sow', '-t', str(os.cpu_count() or 4)])
    j = json.load(open(base + '.json'))
    words = []
    for seg in j.get('transcription', []):
        raw = seg.get('text', ''); t = raw.strip()
        if not t or t.startswith('['): continue
        s0, e0 = seg['offsets']['from'] / 1000, seg['offsets']['to'] / 1000
        if words and not raw.startswith(' ') and not re.match(r'^[A-Za-z0-9]', t[:1] or ' ') is None and not raw[:1].isspace():
            words[-1]['w'] += t; words[-1]['e'] = max(words[-1]['e'], e0); continue  # sub-word token -> glue to previous word
        if words and not raw[:1].isspace() and re.match(r'^[^\w]', t):
            words[-1]['w'] += t; continue  # punctuation token
        words.append({'w': t, 's': s0, 'e': e0})
    for i in range(len(words) - 1):  # never overlap the next word
        words[i]['e'] = min(words[i]['e'], words[i+1]['s']); words[i+1]['s'] = max(words[i+1]['s'], words[i]['s'] + 0.01)
    return words
def captions(a):
    words = transcribe(a.input, a.model)
    srt = os.path.splitext(a.input)[0] + '.srt'
    with open(srt, 'w') as f:
        for i, c in enumerate(chunk(words, 3)):
            f.write(f"{i+1}\n{ts(c[0]['s'])} --> {ts(c[-1]['e'])}\n{' '.join(w['w'] for w in c)}\n\n")
    out({'ok': True, 'srt': srt, 'words': words})
def ts(t): h=int(t//3600); m=int(t%3600//60); s=t%60; return f'{h:02}:{m:02}:{s:06.3f}'.replace('.', ',')
def chunk(words, n):
    out_, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or re.search(r'[.!?,]$', w['w']): out_.append(cur); cur = []
    if cur: out_.append(cur)
    return out_

# ---------------- shorts ----------------
STYLES = {
  # name: caption look, words per line, cut pacing, punch-in zooms, color grade
  'hormozi':  {'font': 'Montserrat', 'size': 92, 'color': '&H00FFFFFF', 'hi': '&H0000E5FF', 'outline': 7, 'upper': True, 'words': 3, 'zoom_every': 2.5, 'zoom': 1.12, 'grade': 'eq=contrast=1.08:saturation=1.15', 'pos': 0.62},
  'mrbeast':  {'font': 'Anton', 'size': 120, 'color': '&H00FFFFFF', 'hi': '&H0000FF00', 'outline': 9, 'upper': True, 'words': 2, 'zoom_every': 1.8, 'zoom': 1.18, 'grade': 'eq=contrast=1.15:saturation=1.35:brightness=0.02', 'pos': 0.55},
  'podcast':  {'font': 'Montserrat', 'size': 70, 'color': '&H00FFFFFF', 'hi': '&H0057C1FF', 'outline': 5, 'upper': False, 'words': 4, 'zoom_every': 4.0, 'zoom': 1.08, 'grade': 'eq=contrast=1.04', 'pos': 0.72},
  'cinematic':{'font': 'Montserrat', 'size': 58, 'color': '&H00F0F0F0', 'hi': '&H00F0F0F0', 'outline': 2, 'upper': False, 'words': 5, 'zoom_every': 0, 'zoom': 1.0, 'grade': "curves=preset=increase_contrast,eq=saturation=0.9,vignette=PI/5", 'pos': 0.82, 'bars': True},
  'minimal':  {'font': 'Montserrat', 'size': 64, 'color': '&H00FFFFFF', 'hi': '&H00FFFFFF', 'outline': 3, 'upper': False, 'words': 4, 'zoom_every': 0, 'zoom': 1.0, 'grade': 'null', 'pos': 0.75},
  'fast':     {'font': 'Anton', 'size': 104, 'color': '&H00FFFFFF', 'hi': '&H003F61C6', 'outline': 8, 'upper': True, 'words': 1, 'zoom_every': 1.2, 'zoom': 1.15, 'grade': 'eq=contrast=1.12:saturation=1.25', 'pos': 0.58},
}
def ass_header(st, W=1080, H=1920):
    f = os.path.splitext(os.path.basename(font(st['font'])))[0]
    fname = 'Anton' if st['font'] == 'Anton' else 'Montserrat'
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{fname},{st['size']},{st['color']},{st['hi']},&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{st['outline']},2,5,60,60,0,1
Style: Hook,{fname},{int(st['size']*0.9)},&H00FFFFFF,&H00FFFFFF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,18,0,8,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
def at(t): h=int(t//3600); m=int(t%3600//60); s=t%60; return f'{h}:{m:02}:{s:05.2f}'
def build_ass(words, st, hook, path, W=1080, H=1920, dur=0):
    y = int(H * st['pos'])
    lines = [ass_header(st, W, H)]
    chunks = chunk(words, st['words'])
    for ci, c in enumerate(chunks):
        nxt = chunks[ci+1][0]['s'] if ci + 1 < len(chunks) else 1e9
        for k, w in enumerate(c):  # karaoke-style: active word highlighted + pop
            s = w['s']; e = c[k+1]['s'] if k + 1 < len(c) else w['e'] + 0.05
            txt = []
            for j, x in enumerate(c):
                t = x['w'].upper() if st['upper'] else x['w']
                t = t.replace('{', '').replace('}', '')
                txt.append('{\\c' + st['hi'] + '\\fscx112\\fscy112}' + t + '{\\r}' if j == k else t)
            lines.append(f"Dialogue: 0,{at(s)},{at(min(max(e, s+0.08), nxt))},Cap,,0,0,0,,{{\\pos({W//2},{y})\\t(0,80,\\fscx106\\fscy106)}}{' '.join(txt)}")
    if hook:
        lines.append(f"Dialogue: 1,{at(0)},{at(min(3.0, dur or 3.0))},Hook,,0,0,0,,{{\\fad(0,250)}}{hook.replace('{','').replace('}','')}")
    open(path, 'w').write('\n'.join(lines) + '\n')

def silence_cuts(path, dur, thresh='-34dB', minsil=0.45, pad=0.08):
    p = subprocess.run(['ffmpeg', '-i', path, '-af', f'silencedetect=noise={thresh}:d={minsil}', '-f', 'null', '-'], stderr=subprocess.PIPE, text=True)
    sil, s0 = [], None
    for line in p.stderr.splitlines():
        m = re.search(r'silence_start: ([\d.]+)', line)
        if m: s0 = float(m.group(1))
        m = re.search(r'silence_end: ([\d.]+)', line)
        if m and s0 is not None: sil.append((s0, float(m.group(1)))); s0 = None
    if s0 is not None: sil.append((s0, dur))
    keep, t = [], 0.0
    for a, b in sil:
        if a - t > 0.25: keep.append((max(0, t - pad if t else 0), min(dur, a + pad)))
        t = b
    if dur - t > 0.25: keep.append((max(0, t - pad), dur))
    return keep or [(0, dur)]

def shorts(a):
    if not have_ffmpeg(): setup()
    st = dict(STYLES.get(a.style, STYLES['hormozi']))
    if a.style_notes:  # free-text style tweaks from the user, e.g. "yellow captions, more zooms"
        n = a.style_notes.lower()
        for col, ass in (('yellow', '&H0000E5FF'), ('green', '&H0000FF00'), ('red', '&H000000FF'), ('blue', '&H00FF8000'), ('orange', '&H0000A5FF'), ('pink', '&H00B469FF')):
            if col in n: st['hi'] = ass
        if 'more zoom' in n or 'lots of zoom' in n: st['zoom_every'] = max(1.0, (st['zoom_every'] or 3) * 0.6); st['zoom'] = max(st['zoom'], 1.15)
        if 'no zoom' in n: st['zoom_every'] = 0
        if 'one word' in n: st['words'] = 1
        if 'lowercase' in n: st['upper'] = False
        if 'black and white' in n or 'b&w' in n: st['grade'] = 'hue=s=0,eq=contrast=1.2'
    work = f'/tmp/ol-shorts-{int(time.time())}'; os.makedirs(work, exist_ok=True)
    W, H, FPS = 1080, 1920, 30
    segs = []
    for idx, src in enumerate(a.inputs):
        info = probe(src)
        cuts = silence_cuts(src, info['duration']) if (info['audio'] and not a.keep_silence) else [(0, info['duration'])]
        for j, (s, e) in enumerate(cuts):
            o = f'{work}/seg{idx:02}_{j:03}.mp4'
            # 9:16: fill with blurred copy, center the original (or crop if it's already tall)
            if info['w'] and info['h'] and info['w'] / info['h'] < 0.8:
                vf = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'
            else:
                vf = f'split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:5,eq=brightness=-0.08[bg];[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2'
            vf += f',fps={FPS},{st["grade"]},format=yuv420p'
            cmd = ['ffmpeg', '-y', '-ss', f'{s:.3f}', '-to', f'{e:.3f}', '-i', src]
            if not info['audio']: cmd += ['-f', 'lavfi', '-t', f'{e-s:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
            cmd += ['-filter_complex', f'[0:v]{vf}[v]', '-map', '[v]', '-map', '0:a' if info['audio'] else '1:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-shortest', o]
            run(cmd); segs.append(o)
    lst = f'{work}/list.txt'; open(lst, 'w').write(''.join(f"file '{p}'\n" for p in segs))
    joined = f'{work}/joined.mp4'
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', joined])
    dur = probe(joined)['duration']
    if a.max and dur > a.max:
        run(['ffmpeg', '-y', '-i', joined, '-t', str(a.max), '-c', 'copy', f'{work}/cut.mp4']); joined = f'{work}/cut.mp4'; dur = a.max
    # punch-in zooms on a rhythm (or on detected beats when music is given)
    zf = 'null'
    if st['zoom_every']:
        per = st['zoom_every']; z = st['zoom']
        zf = f"scale=w='iw*if(lt(mod(t,{per*2}),{per}),1,{z})':h='ih*if(lt(mod(t,{per*2}),{per}),1,{z})':eval=frame,crop={W}:{H}"
    words = []
    if not a.no_captions:
        try: words = transcribe(joined, a.asr_model)
        except SystemExit: raise
        except Exception as e: log('captions failed:', e)
    ass = f'{work}/caps.ass'; build_ass(words, st, a.hook, ass, W, H, dur)
    fontsdir = FONTS
    vchain = f"[0:v]{zf}" + (",drawbox=y=0:w=iw:h=ih*0.1:color=black:t=fill,drawbox=y=ih*0.9:w=iw:h=ih*0.1:color=black:t=fill" if st.get('bars') else '') + f",ass={ass}:fontsdir={fontsdir}[v]"
    dest = a.out or stamp('short-' + a.style, 'mp4')
    cmd = ['ffmpeg', '-y', '-i', joined]
    if a.music:
        cmd += ['-stream_loop', '-1', '-i', a.music]
        achain = f"[1:a]volume={a.music_vol},afade=t=out:st={max(0,dur-1.5):.2f}:d=1.5[m];[0:a][m]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[ducked];[0:a][ducked]amix=inputs=2:duration=first:normalize=0[a]"
        # sidechain: duck the music under speech
        achain = f"[1:a]volume={a.music_vol},afade=t=out:st={max(0,dur-1.5):.2f}:d=1.5[m];[0:a]asplit[sp][key];[m][key]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[duck];[sp][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    else:
        achain = '[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]'
    cmd += ['-filter_complex', vchain + ';' + achain, '-map', '[v]', '-map', '[a]', '-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', dest]
    run(cmd)
    shutil.rmtree(work, True)
    out({'ok': True, 'path': dest, 'style': a.style, 'duration': round(dur, 2), 'segments': len(segs), 'captions': len(words), 'removed_silence': not a.keep_silence})

# ---------------- timeline renderer (movie editor) ----------------
XF = {'fade', 'wipeleft', 'wiperight', 'slideleft', 'slideright', 'slideup', 'circleopen', 'dissolve', 'zoomin', 'fadeblack', 'fadewhite', 'radial', 'smoothleft', 'pixelize'}
FILTERS = {'none': 'null', 'warm': 'colorbalance=rs=0.08:gs=0.02:bs=-0.08,eq=saturation=1.1', 'cool': 'colorbalance=rs=-0.06:bs=0.08', 'bw': 'hue=s=0,eq=contrast=1.15',
           'vintage': 'curves=preset=vintage,vignette=PI/4', 'teal_orange': 'colorbalance=rs=0.1:gs=-0.02:bs=-0.1:rh=-0.08:bh=0.1,eq=saturation=1.2', 'vivid': 'eq=saturation=1.4:contrast=1.08',
           'film': 'curves=preset=increase_contrast,noise=alls=6:allf=t,vignette=PI/5', 'fade': 'curves=all=0/0.08 1/0.92,eq=saturation=0.85', 'drama': 'eq=contrast=1.25:saturation=0.9,vignette=PI/4'}
def esc(t): return t.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\u2019").replace('%', '\\%')
def render(a):
    if not have_ffmpeg(): setup()
    P = json.load(open(a.project))
    W, H = P.get('width', 1080), P.get('height', 1920); FPS = P.get('fps', 30)
    if a.preview: W, H = W // 3 * 1 // 2 * 2 or 360, H // 3 // 2 * 2 or 640
    tracks = P.get('tracks', [])
    work = f'/tmp/ol-render-{int(time.time())}'; os.makedirs(work, exist_ok=True)
    main = next((t for t in tracks if t.get('kind') == 'video'), {'clips': []})
    clips = sorted(main.get('clips', []), key=lambda c: c.get('start', 0))
    if not clips: die('the video track is empty')
    norm = []
    for i, c in enumerate(clips):
        o = f'{work}/c{i:03}.mp4'
        src = c['src']; inn = float(c.get('in', 0)); dur = float(c.get('duration', 3)); spd = float(c.get('speed', 1)) or 1
        isimg = bool(re.search(r'\.(png|jpe?g|webp)$', src, re.I))
        vf = []
        if isimg:
            n = int(dur * FPS); z, x, y = [s.format(n=n) for s in PRESETS.get(c.get('motion', 'static'), PRESETS['static'])]
            vf.append(f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}")
            cmd = ['ffmpeg', '-y', '-loop', '1', '-t', f'{dur:.3f}', '-i', src, '-f', 'lavfi', '-t', f'{dur:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
        else:
            info = probe(src)
            fit = c.get('fit', 'cover')
            vf.append(f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}' if fit == 'cover' else f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2')
            if spd != 1: vf.append(f'setpts=PTS/{spd}')
            if c.get('motion') and c['motion'] != 'static':
                # keyframed zoom on video: linear from zoomFrom to zoomTo across the clip
                z0, z1 = float(c.get('zoomFrom', 1)), float(c.get('zoomTo', 1.2))
                vf.append(f"scale=w='iw*({z0}+({z1}-{z0})*t/{dur})':h='ih*({z0}+({z1}-{z0})*t/{dur})':eval=frame,crop={W}:{H}")
            cmd = ['ffmpeg', '-y', '-ss', f'{inn:.3f}', '-t', f'{dur*spd:.3f}', '-i', src]
            if not info['audio']: cmd += ['-f', 'lavfi', '-t', f'{dur:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
        vf.append(FILTERS.get(c.get('filter', 'none'), 'null'))
        adj = c.get('adjust') or {}
        if adj: vf.append(f"eq=brightness={adj.get('brightness',0)}:contrast={adj.get('contrast',1)}:saturation={adj.get('saturation',1)}")
        if c.get('lut') and os.path.exists(c['lut']): vf.append(f"lut3d='{c['lut']}'")
        if c.get('reverse'): vf.append('reverse')
        vf.append(f'fps={FPS},format=yuv420p,setsar=1')
        af = [f'atempo={min(2,max(0.5,spd))}' if spd != 1 else 'anull', f"volume={c.get('volume',1)}", 'aresample=48000']
        has_a = (not isimg) and probe(src)['audio']
        amap = '0:a' if has_a else '1:a'
        cmd += ['-filter_complex', f"[0:v]{','.join(vf)}[v];[{amap}]{','.join(af)}[a]", '-map', '[v]', '-map', '[a]', '-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac', '-ac', '2', o]
        run(cmd); norm.append((o, dur, c.get('transition'), float(c.get('transitionDuration', 0.5))))
    # join main track with xfade/acrossfade transitions
    cur, cur_d = norm[0][0], norm[0][1]
    for i in range(1, len(norm)):
        nxt, d, tr, td = norm[i][0], norm[i][1], norm[i-1][2], norm[i-1][3]
        o = f'{work}/j{i:03}.mp4'
        if tr and tr in XF:
            td = min(td, cur_d / 2, d / 2)
            run(['ffmpeg', '-y', '-i', cur, '-i', nxt, '-filter_complex', f'[0:v][1:v]xfade=transition={tr}:duration={td}:offset={cur_d-td:.3f}[v];[0:a][1:a]acrossfade=d={td}[a]', '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac', o])
            cur_d = cur_d + d - td
        else:
            lst = f'{work}/l{i}.txt'; open(lst, 'w').write(f"file '{cur}'\nfile '{nxt}'\n")
            run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', o]); cur_d += d
        cur = o
    total = cur_d
    # overlays (images/video picture-in-picture), text, audio tracks
    inputs = ['-i', cur]; fc = []; vlabel = '0:v'; k = 1
    for t in tracks:
        if t.get('kind') == 'overlay' and not t.get('muted'):
            for c in t.get('clips', []):
                s = float(c.get('start', 0)); d = float(c.get('duration', 3))
                if re.search(r'\.(png|jpe?g|webp)$', c['src'], re.I): inputs += ['-loop', '1', '-t', f'{s+d:.3f}', '-i', c['src']]
                else: inputs += ['-itsoffset', f'{s:.3f}', '-i', c['src']]
                sc = float(c.get('scale', 0.4)); x = c.get('x', 0.5); y = c.get('y', 0.3); op = c.get('opacity', 1)
                fc.append(f"[{k}:v]scale={int(W*sc)}:-2,format=rgba,colorchannelmixer=aa={op}[o{k}];[{vlabel}][o{k}]overlay=x=(W*{x})-w/2:y=(H*{y})-h/2:enable='between(t,{s},{s+d})'[v{k}]")
                vlabel = f'v{k}'; k += 1
    txt = []
    for t in tracks:
        if t.get('kind') == 'text' and not t.get('muted'):
            for c in t.get('clips', []):
                s = float(c.get('start', 0)); d = float(c.get('duration', 3))
                fz = int(c.get('size', 72) * W / 1080); col = c.get('color', 'white')
                ff = font(c.get('font', 'Montserrat'))
                y = c.get('y', 0.8); anim = c.get('animation', 'fade')
                alpha = f"alpha='if(lt(t,{s}+0.3),(t-{s})/0.3,if(gt(t,{s+d}-0.3),({s+d}-t)/0.3,1))'" if anim == 'fade' else "alpha=1"
                yexpr = f"(h*{y})-th/2+if(lt(t,{s}+0.35),40*(1-(t-{s})/0.35),0)" if anim == 'rise' else f"(h*{y})-th/2"
                box = ':box=1:boxcolor=black@0.45:boxborderw=24' if c.get('box') else ''
                txt.append(f"drawtext=fontfile='{ff}':text='{esc(c.get('text',''))}':fontsize={fz}:fontcolor={col}:borderw={c.get('outline',4)}:bordercolor=black@0.85:x=(w-tw)/2:y='{yexpr}':{alpha}{box}:enable='between(t,{s:.3f},{s+d:.3f})'")
    vchain = (';'.join(fc) + ';' if fc else '') + f"[{vlabel}]" + (','.join(txt) if txt else 'null') + '[vout]'
    amix = ['[0:a]volume=1[a0]']; alabels = ['[a0]']
    for t in tracks:
        if t.get('kind') == 'audio' and not t.get('muted'):
            for c in t.get('clips', []):
                s = float(c.get('start', 0)); d = float(c.get('duration', total))
                inputs += ['-i', c['src']]
                fade = f",afade=t=in:d={c.get('fadeIn',0.5)},afade=t=out:st={max(0,d-float(c.get('fadeOut',1))):.2f}:d={c.get('fadeOut',1)}"
                amix.append(f"[{k}:a]atrim=start={c.get('in',0)}:duration={d},asetpts=PTS-STARTPTS,volume={c.get('volume',0.6)}{fade},adelay={int(s*1000)}|{int(s*1000)}[a{k}]")
                alabels.append(f'[a{k}]'); k += 1
    achain = ';'.join(amix) + ';' + ''.join(alabels) + f'amix=inputs={len(alabels)}:duration=first:normalize=0,alimiter=limit=0.95[aout]'
    dest = a.out or stamp('movie' + ('-preview' if a.preview else ''), 'mp4')
    run(['ffmpeg', '-y', *inputs, '-filter_complex', vchain + ';' + achain, '-map', '[vout]', '-map', '[aout]', '-t', f'{total:.3f}',
         '-c:v', 'libx264', '-preset', 'ultrafast' if a.preview else 'medium', '-crf', '28' if a.preview else '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', dest])
    shutil.rmtree(work, True)
    out({'ok': True, 'path': dest, 'duration': round(total, 2), 'width': W, 'height': H})

# ---------------- local open-source image/video models (stable-diffusion.cpp) ----------------
LOCAL = json.loads(r'''[{"id": "sd-turbo", "name": "SD-Turbo (Stability, 1\u20134 steps)", "kind": "image", "phone": "good", "ram_gb": 3, "steps": 4, "cfg": 1, "sampler": "euler_a", "note": "Fastest real local option on a phone. 512\u00d7512 in about 20\u201360 s on a recent Snapdragon/Dimensity.", "files": [{"role": "model", "file": "sd_turbo-f16-q8_0.gguf", "url": "https://huggingface.co/Green-Sky/SD-Turbo-GGUF/resolve/main/sd_turbo-f16-q8_0.gguf", "bytes": 2023745376}], "size_gb": 2.02, "source": "Hugging Face (only public host with these GGUF conversions)"}, {"id": "sd15-q4", "name": "Stable Diffusion 1.5 (Q4_0)", "kind": "image", "phone": "ok", "ram_gb": 3, "steps": 20, "cfg": 7, "note": "Classic open model, huge community. 1\u20133 min per 512\u00d7512 on phone.", "files": [{"role": "model", "file": "stable-diffusion-v1-5-pruned-emaonly-Q4_0.gguf", "url": "https://huggingface.co/second-state/stable-diffusion-v1-5-GGUF/resolve/main/stable-diffusion-v1-5-pruned-emaonly-Q4_0.gguf", "bytes": 1566768416}], "size_gb": 1.57, "source": "Hugging Face (only public host with these GGUF conversions)"}, {"id": "sd21-turbo-q4", "name": "SD 2.1 Turbo (Q4_0)", "kind": "image", "phone": "ok", "ram_gb": 4, "steps": 4, "cfg": 1, "sampler": "euler_a", "note": "1\u20134 steps, a bit sharper than SD-Turbo.", "files": [{"role": "model", "file": "stable-diffusion-v2-1-turbo-Q4_0.gguf", "url": "https://huggingface.co/gpustack/stable-diffusion-v2-1-turbo-GGUF/resolve/main/stable-diffusion-v2-1-turbo-Q4_0.gguf", "bytes": 2185459424}], "size_gb": 2.19, "source": "Hugging Face (only public host with these GGUF conversions)"}, {"id": "z-image-turbo-q3", "name": "Z-Image Turbo (Alibaba Tongyi, Q3_K)", "kind": "image", "phone": "heavy", "ram_gb": 10, "steps": 8, "cfg": 1, "note": "Best quality open model here, 8 steps. Needs 12 GB+ RAM phone; several minutes per image.", "files": [{"role": "diffusion", "file": "z_image_turbo-Q3_K.gguf", "url": "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q3_K.gguf", "bytes": 3143559104}, {"role": "llm", "file": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "url": "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "bytes": 2497281120}, {"role": "vae", "file": "ae.safetensors", "url": "https://huggingface.co/second-state/FLUX.1-schnell-GGUF/resolve/main/ae.safetensors", "bytes": 335304388}], "extra": ["--diffusion-fa"], "size_gb": 5.98, "source": "Hugging Face (only public host with these GGUF conversions)"}, {"id": "flux-schnell-q4", "name": "FLUX.1-schnell (Black Forest Labs, Q4_0)", "kind": "image", "phone": "heavy", "ram_gb": 14, "steps": 4, "cfg": 1, "note": "Top open model (Apache-2.0). ~10 GB download, needs 16 GB RAM; 5\u201315 min per image on phone. Better on the PC.", "files": [{"role": "diffusion", "file": "flux1-schnell-Q4_0.gguf", "url": "https://huggingface.co/second-state/FLUX.1-schnell-GGUF/resolve/main/flux1-schnell-Q4_0.gguf", "bytes": 6688845536}, {"role": "vae", "file": "ae.safetensors", "url": "https://huggingface.co/second-state/FLUX.1-schnell-GGUF/resolve/main/ae.safetensors", "bytes": 335304388}, {"role": "clip_l", "file": "clip_l-Q8_0.gguf", "url": "https://huggingface.co/second-state/FLUX.1-schnell-GGUF/resolve/main/clip_l-Q8_0.gguf", "bytes": 130769600}, {"role": "t5xxl", "file": "t5xxl-Q2_K.gguf", "url": "https://huggingface.co/second-state/FLUX.1-schnell-GGUF/resolve/main/t5xxl-Q2_K.gguf", "bytes": 1605835296}], "extra": ["--diffusion-fa"], "size_gb": 8.76, "source": "Hugging Face (only public host with these GGUF conversions)"}, {"id": "wan21-1.3b-q4", "name": "Wan 2.1 T2V 1.3B (Alibaba, Q4_0) \u2014 video", "kind": "video", "phone": "very slow", "ram_gb": 8, "steps": 20, "cfg": 6, "frames": 17, "note": "Real open-source text-to-video. 17 frames at 480\u00d7320 takes 20\u201360+ min on a phone and needs 8 GB+ RAM. Experimental.", "files": [{"role": "diffusion", "file": "Wan2.1-T2V-1.3B-Q4_0.gguf", "url": "https://huggingface.co/samuelchristlie/Wan2.1-T2V-1.3B-GGUF/resolve/main/Wan2.1-T2V-1.3B-Q4_0.gguf", "bytes": 865581280}, {"role": "t5xxl", "file": "umt5-xxl-encoder-Q3_K_S.gguf", "url": "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q3_K_S.gguf", "bytes": 2858489696}, {"role": "vae", "file": "wan_2.1_vae.safetensors", "url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", "bytes": 253815318}], "extra": ["--diffusion-fa", "--flow-shift", "3.0"], "size_gb": 3.98, "source": "Hugging Face (only public host with these GGUF conversions)"}]''')
CUSTOM = f'{MODELS}/custom.json'
def catalog():
    c = list(LOCAL)
    if os.path.exists(CUSTOM): c += json.load(open(CUSTOM))
    return c
def sd_bin():
    p = shutil.which('sd') or shutil.which('sd-cli')
    if p: return p
    p = f'{BIN}/sd'
    if not os.path.exists(p):
        if ARCH != 'aarch64': die('stable-diffusion.cpp binary not found for ' + ARCH)
        log('STEP Downloading stable-diffusion.cpp (arm64)')
        download_resume(RELEASE_TOOLS + 'sd-aarch64', p, 'sd'); os.chmod(p, 0o755)
    return p
def local(a):
    cat = catalog()
    if a.action == 'list':
        res = []
        for m in cat:
            files = [f'{MODELS}/{f["file"]}' for f in m['files']]
            res.append({**m, 'installed': all(os.path.exists(f) for f in files), 'bytes_on_disk': sum(os.path.getsize(f) for f in files if os.path.exists(f))})
        out({'ok': True, 'models': res, 'free_bytes': shutil.disk_usage(MODELS).free}); return
    if a.action == 'add':
        cus = json.load(open(CUSTOM)) if os.path.exists(CUSTOM) else []
        fn = re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(urllib.parse.urlparse(a.id).path)) or 'custom.gguf'
        cus.append({'id': 'custom-' + hashlib.md5(a.id.encode()).hexdigest()[:8], 'name': a.name or fn, 'kind': 'image', 'family': 'sd', 'files': [{'file': fn, 'url': a.id, 'role': 'model'}], 'size_gb': 0, 'ram_gb': 0, 'phone': 'unknown', 'note': 'Added by URL. Must be a stable-diffusion.cpp compatible checkpoint (.gguf/.safetensors/.ckpt).', 'source': urllib.parse.urlparse(a.id).netloc, 'steps': 20, 'cfg': 7})
        json.dump(cus, open(CUSTOM, 'w'), indent=1); out({'ok': True, 'added': cus[-1]}); return
    m = next((x for x in cat if x['id'] == a.id), None)
    if a.action in ('install', 'remove') and not m: die('unknown model ' + str(a.id))
    if a.action == 'install':
        sd_bin()
        for f in m['files']:
            p = f'{MODELS}/{f["file"]}'
            if not os.path.exists(p): log('STEP Downloading', f['file']); download_resume(f['url'], p, f['file'])
        out({'ok': True, 'installed': m['id']}); return
    if a.action == 'remove':
        for f in m['files']:
            shared = any(f['file'] in [g['file'] for g in o['files']] for o in cat if o['id'] != m['id'] and all(os.path.exists(f'{MODELS}/{g["file"]}') for g in o['files']))
            for p in (f'{MODELS}/{f["file"]}', f'{MODELS}/{f["file"]}.part'):
                if os.path.exists(p) and not shared: os.remove(p)
        out({'ok': True, 'removed': m['id']}); return
    if a.action == 'gen':
        m = m or next((x for x in cat if all(os.path.exists(f'{MODELS}/{f["file"]}') for f in x['files'])), None)
        if not m: die('no local model installed; install one first')
        args = [sd_bin()]
        for f in m['files']:
            role = f.get('role', 'model'); p = f'{MODELS}/{f["file"]}'
            flag = {'model': '-m', 'diffusion': '--diffusion-model', 'vae': '--vae', 'clip_l': '--clip_l', 't5xxl': '--t5xxl', 'llm': '--llm', 'clip_vision': '--clip_vision', 'high_noise': '--high-noise-diffusion-model'}[role]
            args += [flag, p]
        is_video = m.get('kind') == 'video'
        dest = stamp('local-' + m['id'], 'mp4' if is_video else 'png')
        args += ['-p', a.prompt, '--steps', str(a.steps or m.get('steps', 20)), '--cfg-scale', str(m.get('cfg', 7)), '-W', str(a.w), '-H', str(a.h), '-t', str(os.cpu_count() or 4), '-o', dest]
        if m.get('sampler'): args += ['--sampling-method', m['sampler']]
        if m.get('extra'): args += m['extra']
        if is_video: args += ['-M', 'vid_gen', '--video-frames', str(m.get('frames', 17))]
        t0 = time.time(); run(args)
        if is_video and not os.path.exists(dest):
            # sd.cpp writes frames/avi depending on build; convert to mp4
            cand = [f for f in os.listdir(MEDIA) if f.startswith(os.path.basename(dest)[:-4])]
            log('outputs', cand)
        out({'ok': True, 'path': dest, 'model': m['id'], 'seconds': round(time.time() - t0, 1), 'source': 'local stable-diffusion.cpp'}); return

def serve(_):
    os.chdir(HOME)
    p = subprocess.run("pgrep -f 'http.server 8765' >/dev/null || (setsid python3 -m http.server 8765 --bind 127.0.0.1 >/tmp/ol-media-http.log 2>&1 &)", shell=True)
    out({'ok': True, 'url': 'http://127.0.0.1:8765/'})

def main():
    ap = argparse.ArgumentParser(prog='ol-media'); sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('setup')
    p = sp.add_parser('image'); p.add_argument('prompt'); p.add_argument('--w', type=int, default=768); p.add_argument('--h', type=int, default=1344); p.add_argument('--seed', type=int); p.add_argument('--model')
    p = sp.add_parser('video'); p.add_argument('prompt'); p.add_argument('--secs', type=float, default=3); p.add_argument('--w', type=int, default=512); p.add_argument('--h', type=int, default=704); p.add_argument('--image'); p.add_argument('--no-fallback', action='store_true')
    p = sp.add_parser('motion'); p.add_argument('image'); p.add_argument('--preset', default='push_in', choices=list(PRESETS)); p.add_argument('--secs', type=float, default=4); p.add_argument('--w', type=int, default=1080); p.add_argument('--h', type=int, default=1920)
    p = sp.add_parser('stock'); p.add_argument('kind', choices=['images', 'audio']); p.add_argument('query'); p.add_argument('--n', type=int, default=6); p.add_argument('--download', action='store_true')
    p = sp.add_parser('shorts'); p.add_argument('inputs', nargs='+'); p.add_argument('--style', default='hormozi', choices=list(STYLES)); p.add_argument('--style-notes', default=''); p.add_argument('--hook', default=''); p.add_argument('--music'); p.add_argument('--music-vol', type=float, default=0.18); p.add_argument('--max', type=float, default=60); p.add_argument('--no-captions', action='store_true'); p.add_argument('--keep-silence', action='store_true'); p.add_argument('--asr-model', default='base.en'); p.add_argument('--out')
    p = sp.add_parser('render'); p.add_argument('project'); p.add_argument('--out'); p.add_argument('--preview', action='store_true')
    p = sp.add_parser('captions'); p.add_argument('input'); p.add_argument('--model', default='base.en')
    p = sp.add_parser('local'); p.add_argument('action', choices=['list', 'install', 'remove', 'add', 'gen']); p.add_argument('id', nargs='?'); p.add_argument('name', nargs='?'); p.add_argument('--prompt', default=''); p.add_argument('--model'); p.add_argument('--steps', type=int); p.add_argument('--w', type=int, default=512); p.add_argument('--h', type=int, default=512)
    sp.add_parser('serve')
    a = ap.parse_args()
    if a.cmd == 'local' and a.action == 'gen':
        if not a.prompt and a.id: a.prompt = a.id; a.id = a.model
        else: a.id = a.model or a.id
    {'setup': setup, 'image': image, 'video': video, 'motion': motion, 'stock': stock, 'shorts': shorts, 'render': render, 'captions': captions, 'local': local, 'serve': serve}[a.cmd](a)

if __name__ == '__main__':
    try: main()
    except SystemExit: raise
    except Exception as e: die(f'{type(e).__name__}: {e}')
