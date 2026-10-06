"""
api.py - الـ API اللي الـ Agent (البرنامج اللي شغال على جهاز المستخدم) بيتواصل معاه.
شغّله بـ: uvicorn api:app --host 0.0.0.0 --port 8000
في الإنتاج لازم يكون خلف HTTPS (عن طريق Nginx / Caddy / Cloudflare Tunnel).
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import db

app = FastAPI(title="Remote Admin API")
db.init_db()


# ---------- Models ----------

class PairRequest(BaseModel):
    code: str
    device_id: str
    device_name: str = "جهاز غير مسمى"


class ResultRequest(BaseModel):
    command_id: int
    status: str  # done | error
    result: str


# ---------- Auth helper ----------

def auth_device(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    token = authorization.split(" ", 1)[1]
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(401, "invalid token")
    return user


# ---------- Endpoints يستخدمها الـ Agent ----------

@app.post("/pair")
def pair(req: PairRequest):
    """الـ Agent يبعت الكود اللي كتبه المستخدم + معرف الجهاز، فيرجع توكن دائم."""
    data, error = db.consume_pairing_code(req.code, req.device_id, req.device_name)
    if error:
        raise HTTPException(400, error)
    return data


@app.get("/poll")
def poll(authorization: str = Header(None)):
    """الـ Agent يسأل كل كذا ثانية: فيه أوامر جديدة؟"""
    user = auth_device(authorization)
    rows = db.pop_pending_commands(user["device_id"])
    commands = [
        {"id": r["id"], "command": r["command"], "args": r["args"]}
        for r in rows
    ]
    return {"commands": commands}


@app.post("/result")
def result(req: ResultRequest, authorization: str = Header(None)):
    """الـ Agent يرجّع نتيجة تنفيذ الأمر."""
    auth_device(authorization)
    db.set_command_result(req.command_id, req.status, req.result)
    return {"ok": True}


# ---------- Endpoints داخلية يستخدمها البوت (bot.py) مباشرة عن طريق استيراد db، مش HTTP ----------
# البوت وملف الـ API بيشتغلوا في نفس المشروع ويستخدموا نفس db.py، فمفيش داعي لطبقة HTTP بينهم.
