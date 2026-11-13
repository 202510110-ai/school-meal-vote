from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import sqlite3
import os
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace-this-secret-key")
DB = os.environ.get("DB_PATH", "meal_benpick.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def setup():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS menus(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS votes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_id INTEGER NOT NULL,
            voter_id TEXT UNIQUE NOT NULL,
            FOREIGN KEY(menu_id) REFERENCES menus(id))""")
        if con.execute("SELECT COUNT(*) FROM menus").fetchone()[0] == 0:
            con.executemany("INSERT INTO menus(name) VALUES(?)",
                            [("생선 요리",), ("가지 요리",), ("나물 반찬",), ("콩 요리",)])

STYLE = """
*{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#243047;font-family:Arial,sans-serif}
main{max-width:760px;margin:35px auto;padding:18px}.card{background:white;border-radius:20px;padding:28px;box-shadow:0 8px 28px #20305012}
h1{color:#2859a5;margin-top:0}.sub{color:#68758a;line-height:1.6}
.menu{display:block;padding:15px;margin:11px 0;border:1px solid #dce4f0;border-radius:12px;cursor:pointer}
.menu:hover{background:#f4f8ff;border-color:#82a9e5}
button{border:0;background:#2864c5;color:white;padding:13px 20px;border-radius:11px;font-size:16px;cursor:pointer}
button:hover{background:#194e9e}.mainbtn{width:100%;margin-top:12px}
a{color:#2859a5;text-decoration:none;margin-right:15px}.links{margin-top:22px}
.notice{background:#fff4d6;padding:12px;border-radius:10px;margin:15px 0}
.bar{height:13px;background:#e9eef6;border-radius:20px;overflow:hidden;margin-top:8px}
.fill{height:100%;background:#4382df}.result{margin:22px 0}
input[type=text],input[type=password]{padding:12px;border:1px solid #ccd5e3;border-radius:9px;width:100%;margin:8px 0 14px}
"""

HOME = """
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>학교 급식 밴픽</title><style>""" + STYLE + """</style></head><body><main><section class="card">
<h1>🍚 학교 급식 밴픽</h1>
<p class="sub">먹기 부담스럽거나 개선이 필요한 급식 메뉴에 투표해 주세요.<br>
결과는 앞으로의 급식 개선 방향을 논의하기 위한 참고 자료로 활용됩니다.</p>
{% with msgs=get_flashed_messages() %}{% if msgs %}<div class="notice">{{msgs[0]}}</div>{% endif %}{% endwith %}
<h2>이번 투표: 개선이 필요한 급식 메뉴는?</h2>
{% if voted %}<div class="notice">이 브라우저에서는 이미 투표했어요. 결과를 확인해 주세요.</div>
{% else %}<form method="post" action="/vote">
{% for m in menus %}<label class="menu"><input type="radio" name="menu_id" value="{{m.id}}" required> {{m.name}}</label>{% endfor %}
<button class="mainbtn">투표하기</button></form>{% endif %}
<div class="links"><a href="/results">📊 투표 결과 보기</a><a href="/admin">관리자 메뉴</a></div>
</section></main></body></html>
"""

RESULTS = """
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>투표 결과</title><style>""" + STYLE + """</style></head><body><main><section class="card">
<h1>📊 투표 결과</h1><p class="sub">총 투표수: <b>{{total}}표</b></p>
{% for r in rows %}<div class="result"><b>{{r.name}}</b> — {{r.count}}표 ({{r.pct}}%)
<div class="bar"><div class="fill" style="width:{{r.pct}}%"></div></div></div>{% endfor %}
{% if total == 0 %}<p>아직 투표가 없습니다.</p>{% endif %}
<p class="sub">투표 결과는 학생 의견을 파악하기 위한 참고 자료입니다. 실제 급식 변경은 학교와 영양(교)사의 검토가 필요합니다.</p>
<a href="/">← 투표 화면</a></section></main></body></html>
"""

ADMIN = """
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>관리자 메뉴</title><style>""" + STYLE + """</style></head><body><main><section class="card">
<h1>관리자 메뉴</h1>
{% with msgs=get_flashed_messages() %}{% if msgs %}<div class="notice">{{msgs[0]}}</div>{% endif %}{% endwith %}
{% if not ok %}<p>관리자 비밀번호를 입력하세요.</p>
<form method="post"><input type="password" name="password" placeholder="관리자 비밀번호" required><button>로그인</button></form>
{% else %}<h2>급식 메뉴 추가</h2><form method="post" action="/admin/add">
<input type="text" name="name" maxlength="40" placeholder="추가할 메뉴 이름" required><button>메뉴 추가</button></form>
<h2>현재 메뉴</h2><ul>{% for m in menus %}<li>{{m.name}}</li>{% endfor %}</ul>
<form method="post" action="/admin/reset" onsubmit="return confirm('투표 기록을 초기화할까요?')"><button>투표 기록 초기화</button></form>
{% endif %}<p><a href="/">← 투표 화면</a></p></section></main></body></html>
"""

@app.route("/")
def home():
    with db() as con:
        menus = con.execute("SELECT id,name FROM menus ORDER BY id").fetchall()
    return render_template_string(HOME, menus=menus, voted=session.get("voted", False))

@app.route("/vote", methods=["POST"])
def vote():
    if session.get("voted"):
        flash("이미 투표했습니다.")
        return redirect("/")
    menu_id = request.form.get("menu_id", type=int)
    if menu_id is None:
        flash("메뉴를 선택해 주세요.")
        return redirect("/")
    voter_id = session.get("voter_id")
    if not voter_id:
        voter_id = secrets.token_urlsafe(24)
        session["voter_id"] = voter_id
    try:
        with db() as con:
            valid = con.execute("SELECT id FROM menus WHERE id=?", (menu_id,)).fetchone()
            if not valid:
                flash("올바른 메뉴를 선택해 주세요.")
                return redirect("/")
            con.execute("INSERT INTO votes(menu_id,voter_id) VALUES(?,?)", (menu_id,voter_id))
        session["voted"] = True
        flash("투표가 저장되었습니다!")
    except sqlite3.IntegrityError:
        session["voted"] = True
        flash("이미 투표한 기록이 있습니다.")
    return redirect("/")

@app.route("/results")
def results():
    with db() as con:
        rows = con.execute("""SELECT menus.name,COUNT(votes.id) AS n
        FROM menus LEFT JOIN votes ON menus.id=votes.menu_id
        GROUP BY menus.id ORDER BY n DESC,menus.id""").fetchall()
    total = sum(r["n"] for r in rows)
    data = [{"name":r["name"],"count":r["n"],
             "pct":round(r["n"]*100/total,1) if total else 0} for r in rows]
    return render_template_string(RESULTS, rows=data, total=total)

@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            flash("관리자 로그인 성공")
        else:
            flash("비밀번호가 틀렸습니다.")
        return redirect("/admin")
    with db() as con:
        menus = con.execute("SELECT name FROM menus ORDER BY id").fetchall()
    return render_template_string(ADMIN, ok=session.get("admin",False), menus=menus)

@app.route("/admin/add", methods=["POST"])
def add_menu():
    if not session.get("admin"):
        return redirect("/admin")
    name = request.form.get("name","").strip()
    if name:
        try:
            with db() as con:
                con.execute("INSERT INTO menus(name) VALUES(?)",(name,))
            flash("메뉴를 추가했습니다.")
        except sqlite3.IntegrityError:
            flash("이미 있는 메뉴입니다.")
    return redirect("/admin")

@app.route("/admin/reset", methods=["POST"])
def reset():
    if not session.get("admin"):
        return redirect("/admin")
    with db() as con:
        con.execute("DELETE FROM votes")
    flash("투표 기록을 초기화했습니다.")
    return redirect("/admin")

setup()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
