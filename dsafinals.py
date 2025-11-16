
import sqlite3
import pathlib
import urllib.parse as up
import http.server as hs
import webbrowser
import os
import datetime as dt
import signal
import sys
import mimetypes
import shutil

DB         = 'todo_app.db'
PORT       = 8080
UPLOAD_DIR = pathlib.Path(__file__).parent / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
os.chdir(pathlib.Path(__file__).parent)
class DBC:
    def __enter__(self):
        self.db = sqlite3.connect(DB)
        self.db.row_factory = sqlite3.Row
        return self.db
    def __exit__(self, exc_type, exc, tb):
        self.db.close()

# ----------  tiny helpers  ----------
get_uid   = lambda self: int(self.headers.get('Cookie', '')[4:]) if self.headers.get('Cookie', '').startswith('uid=') else None
redirect  = lambda self, loc, msg: (
    self.send_response(302), self.send_header('Location', loc), self.end_headers(),
    self.wfile.write(f'<html><body>{msg}<br><a href="/">continue</a></body></html>'.encode())
)

class H(hs.BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): pass   # quiet console


    def do_GET(self):
        if self.path.startswith('/files/'):
            parts = pathlib.Path(self.path[len('/files/'):])
            if len(parts.parts) != 2:   # task-id / filename
                self.send_error(404); return
            task_id, fname = parts.parts
            fpath = UPLOAD_DIR / task_id / fname
            if not fpath.exists():
                self.send_error(404); return
            self.send_response(200)
            mt, _ = mimetypes.guess_type(str(fpath))
            self.send_header('Content-Type', mt or 'application/octet-stream')
            self.end_headers()
            self.wfile.write(fpath.read_bytes())
            return

        uid = get_uid(self)
        # ---------------  LOGIN PAGE  ---------------
        if self.path == '/':
            if not uid:
                page = '''<!doctype html>
<html><head><meta charset="utf-8"><title>To-Do List</title>
<style>
body{background:#b3d9ff;font-family:"Eras Bold ITC",Arial,Helvetica,sans-serif;color:#003366;text-align:center;height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:#d6ebff;border:2px solid #66a3ff;display:inline-block;padding:30px 50px;border-radius:10px}
h2{font-family:"Eras Bold ITC";color:#003366;margin-top:0}
input{margin:8px 0;padding:8px;width:240px;border:1px solid #66a3ff;border-radius:4px;font-family:"Bahnschrift Light SemiCondensed",Arial;font-size:14px}
button{margin-top:12px;padding:10px 24px;font-family:"Segoe UI Black",Arial;font-size:14px;background:#d6ebff;color:#003366;border:1px solid #66a3ff;border-radius:5px;cursor:pointer}
button:hover{background:#c2dfff}
form{margin:0}
</style></head>
<body>
<div class="box">
<h2>Login or Register</h2>
<form action="/auth" method="post">
  Username:<br><input name="u" required><br>
  Password:<br><input type="password" name="p" required><br>
  <button name="action" value="login">Login</button>
  <button name="action" value="register">Register</button>
</form>
</div></body></html>'''
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(page.encode()); return

            # ---------------  MAIN TODO PAGE  ---------------
            with DBC() as db:
                user = db.execute('SELECT username FROM users WHERE id=?',(uid,)).fetchone()[0]
                rows = db.execute('SELECT id,task,status,due_date FROM tasks WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall()

            tr = ''
            for tid,txt,st,due in rows:
                task_dir = UPLOAD_DIR / str(tid)
                files    = sorted(task_dir.iterdir()) if task_dir.exists() else []
                file_links = ''.join(
                    f'<li><a href="/files/{tid}/{f.name}" target="_blank">{f.name}</a> '
                    f'<button class="del-file" onclick="fetch(\'/del-file\',{{method:\'post\',body:\'task={tid}&file={f.name}\'}}).then(()=>location=\'/\')">Del</button></li>'
                    for f in files
                )

                chk = 'checked' if st else ''
                tr += f'''<tr>
                  <td style="text-align:center"><input {chk} type=checkbox onchange="fetch('/toggle',{chr(123)}method:'post',body:'id={tid}'{chr(125)}).then(()=>location='/')">
                  <td style="font-family:'Courier New',monospace;padding:6px">{txt}
                  <td style="font-family:'Courier New',monospace;padding:6px">{due or 'N/A'}
                  <td style="text-align:center"><button class="del-task" onclick="fetch('/delete',{chr(123)}method:'post',body:'id={tid}'{chr(125)}).then(()=>location='/')">Delete</button>
                  <td style="font-size:12px;padding:4px"><ul style="margin:0;padding-left:16px">{file_links or ''}</ul>
                      <form action="/upload" method="post" enctype="multipart/form-data" style="margin-top:4px">
                          <input type="file" name="file" multiple required>
                          <input type="hidden" name="task" value="{tid}">
                          <button class="upBtn">Upload</button>
                      </form>
                </tr>'''

            page = '''<!doctype html>
<html><head><meta charset="utf-8"><title>To-Do List</title>
<style>
body{margin:0;background:#b3d9ff;font-family:"Eras Bold ITC",Arial,Helvetica,sans-serif;color:#003366}
.box{max-width:900px;margin:30px auto;background:#d6ebff;border:2px solid #66a3ff;border-radius:10px;padding:25px}
h2{color:#003366;font-family:"Eras Bold ITC";margin-top:0}
input{border:1px solid #66a3ff;border-radius:4px;padding:6px;margin:2px;font-family:"Bahnschrift Light SemiCondensed",Arial;font-size:14px}
button{border:1px solid #66a3ff;border-radius:5px;padding:6px 12px;margin:2px;cursor:pointer;font-family:"Lucida Bright",Georgia,serif;font-size:14px}
.addBtn{background:lightgreen;color:darkgreen}
.upBtn {background:orange;color:white}
.del-task{background:#888;color:#fff;border:none;padding:3px 8px;font-size:12px;border-radius:3px;cursor:pointer}
.del-file{background:#888;color:#fff;border:none;padding:2px 6px;font-size:11px;border-radius:3px;cursor:pointer}
a{color:#003366;font-weight:bold;text-decoration:none}a:hover{text-decoration:underline}
table{width:100%;border-collapse:collapse;margin-top:15px;font-family:"Courier New",monospace;font-size:14px}
th{background:#66a3ff;color:white;padding:6px}
td{background:#f0f8ff;padding:4px;vertical-align:top}
.row-line{display:flex;gap:8px;align-items:center}
.logout-bar{text-align:right;margin-top:20px}
</style></head>
<body>
<div class="box">
  <h2>Hello, ''' + user + '''</h2>

  <!--  quick-add row  -->
  <form action="/add" method="post">
    <div class="row-line">
      Task: <input name="task" required placeholder="What needs to be done?">
      Due: <input name="due" placeholder="YYYY-MM-DD">
      <button class="addBtn">Add Task</button>
    </div>
  </form>

  <table><tr><th>Done<th>Task<th>Due Date<th>Delete<th>Attachments</tr>''' + tr + '''</table>

  <div class="logout-bar">
    <a href="/logout" style="background:tomato;color:white;padding:6px 14px;border-radius:4px;text-decoration:none;font-family:'Lucida Bright',Georgia,serif">Logout</a>
  </div>
</div></body></html>'''
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(page.encode()); return

        if self.path == '/logout':
            self.send_response(302); self.send_header('Set-Cookie','uid=; Path=/; Max-Age=0'); self.send_header('Location','/'); self.end_headers(); return
        self.send_error(404)

    # ----------  POST  ----------
    def do_POST(self):
        l   = int(self.headers['Content-Length'])
        uid = get_uid(self)

        #  LOGIN / REGISTER  --------------------
        if self.path == '/auth':
            body = self.rfile.read(l).decode()
            u,p  = up.parse_qs(body)['u'][0], up.parse_qs(body)['p'][0]
            action = up.parse_qs(body).get('action',[''])[0]
            if action == 'login':
                with DBC() as db:
                    row = db.execute('SELECT id FROM users WHERE username=? AND password=?',(u,p)).fetchone()
                if row:
                    self.send_response(302); self.send_header('Set-Cookie',f'uid={row[0]}; Path=/'); self.send_header('Location','/'); self.end_headers(); return
                else: redirect(self,'/','Bad login'); return
            elif action == 'register':
                try:
                    with DBC() as db:
                        db.execute('INSERT INTO users(username,password) VALUES(?,?)',(u,p))
                        db.commit()
                    redirect(self,'/','Registered – please log in'); return
                except sqlite3.IntegrityError: redirect(self,'/','Username taken'); return
            redirect(self,'/','Unknown action'); return

        #  TASK OPERATIONS  ---------------------
        if self.path == '/add' and uid:
            body = self.rfile.read(l).decode()
            task,due = up.parse_qs(body)['task'][0].strip(), up.parse_qs(body).get('due',[''])[0].strip()
            if due:
                try: dt.datetime.strptime(due,'%Y-%m-%d')
                except: redirect(self,'/','Bad date'); return
            with DBC() as db:
                db.execute('INSERT INTO tasks(user_id,task,status,due_date) VALUES(?,?,0,?)',(uid,task,due or None))
                db.commit()
            redirect(self,'/','Added'); return

        if self.path == '/toggle' and uid:
            tid = int(up.parse_qs(self.rfile.read(l).decode())['id'][0])
            with DBC() as db:
                db.execute('UPDATE tasks SET status=1-status WHERE id=? AND user_id=?',(tid,uid))
                db.commit()
            redirect(self,'/','Updated'); return

        if self.path == '/delete' and uid:
            tid = int(up.parse_qs(self.rfile.read(l).decode())['id'][0])
            task_dir = UPLOAD_DIR / str(tid)
            if task_dir.exists(): shutil.rmtree(task_dir)
            with DBC() as db:
                db.execute('DELETE FROM tasks WHERE id=? AND user_id=?',(tid,uid))
                db.commit()
            redirect(self,'/','Deleted'); return

        #  MULTIPLE FILE UPLOAD  (binary-safe) -----------------
        if self.path == '/upload' and uid:
            boundary   = self.headers['Content-Type'].split('boundary=')[1].encode()
            body_bytes = self.rfile.read(l)
            parts      = body_bytes.split(boundary)

            task_id = None
            for part in parts:
                if b'name="task"' in part:
                    task_id = int(part.decode(errors='ignore').split('name="task"')[1].split('\r\n')[2].strip())
                    break

            for part in parts:
                if b'filename=' in part and task_id:
                    lines = part.splitlines()
                    for raw in lines:
                        if b'Content-Disposition:' in raw and b'name="file"' in raw:
                            filename = raw.decode(errors='ignore').split('filename="')[1].split('"')[0]
                            file_data = b'\r\n'.join(lines[4:-1])   # skip headers & tail
                            if filename and file_data:
                                task_dir = UPLOAD_DIR / str(task_id)
                                task_dir.mkdir(exist_ok=True)
                                (task_dir / filename).write_bytes(file_data)
                            break

            redirect(self,'/','Uploaded'); return

        #  SINGLE FILE DELETE  -------------------
        if self.path == '/del-file' and uid:
            body = self.rfile.read(l).decode()
            task_id = int(up.parse_qs(body)['task'][0])
            fname   = up.parse_qs(body)['file'][0]
            fpath   = UPLOAD_DIR / str(task_id) / fname
            if fpath.exists(): fpath.unlink()
            redirect(self,'/','File deleted'); return

        self.send_error(404)

# ----------  start  ----------
def shutdown(*_): print('\nShutting down...'); sys.exit(0)
signal.signal(signal.SIGINT, shutdown)

with sqlite3.connect(DB) as db:   # create schema once
    db.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, user_id INTEGER, task TEXT, status INTEGER DEFAULT 0, due_date TEXT)')
    db.commit()

srv = hs.HTTPServer(('localhost', PORT), H)
print(f'Running on http://localhost:{PORT}/  (Ctrl-C to stop)')
webbrowser.open(f'http://localhost:{PORT}/')
try:
    srv.serve_forever()
except KeyboardInterrupt:
    print('\nDone.')