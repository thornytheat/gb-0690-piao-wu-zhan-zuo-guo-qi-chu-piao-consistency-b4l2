import os,sqlite3,json
from pathlib import Path
from app.errors import DomainError
def connection():
    path=Path(os.environ.get("DATA_DIR","data"));path.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path/"runs.sqlite",timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,review TEXT NOT NULL DEFAULT '待复核')")
    db.execute("""CREATE TABLE IF NOT EXISTS postings(
        run_id TEXT NOT NULL, entry_key TEXT NOT NULL, ordinal INTEGER NOT NULL,
        direction TEXT NOT NULL, channel TEXT NOT NULL, kind TEXT NOT NULL,
        amount TEXT NOT NULL, ref_id TEXT NOT NULL, state TEXT NOT NULL,
        PRIMARY KEY(run_id,entry_key))""")
    db.execute("""CREATE TABLE IF NOT EXISTS posting_journal(
        run_id TEXT NOT NULL, entry_key TEXT NOT NULL, attempt INTEGER NOT NULL,
        status TEXT NOT NULL, detail TEXT NOT NULL,
        PRIMARY KEY(run_id,entry_key,attempt))""")
    return db
def save(result):
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES(?,?)",(result["manifest"]["run_id"],json.dumps(result,ensure_ascii=False)))
    return fetch(result["manifest"]["run_id"])
def fetch(run_id):
    with connection() as db: row=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
    result=json.loads(row["payload"]);result["version"]=row["version"];result["review"]=row["review"]
    return result
def history():
    with connection() as db: rows=db.execute("SELECT id,version,review FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
    return [dict(row) for row in rows]
def review(run_id,version,decision):
    if decision not in ("通过","退回"): raise DomainError("REVIEW","请选择通过或退回")
    if not isinstance(version,int): raise DomainError("STALE","版本必须为整数")
    with connection() as db:
        cur=db.execute("UPDATE runs SET review=?,version=version+1 WHERE id=? AND version=?",(decision,run_id,version))
        if cur.rowcount!=1: raise DomainError("STALE","复核版本已更新",409)
    return fetch(run_id)
def ledger_rows(run_id):
    with connection() as db:
        rows=db.execute("SELECT entry_key,ordinal,direction,channel,kind,amount,ref_id,state FROM postings WHERE run_id=? ORDER BY ordinal",(run_id,)).fetchall()
        return [dict(r) for r in rows]
def ledger_journal(run_id):
    with connection() as db:
        rows=db.execute("SELECT entry_key,attempt,status,detail FROM posting_journal WHERE run_id=? ORDER BY attempt,entry_key",(run_id,)).fetchall()
        return [dict(r) for r in rows]
def next_attempt(db,run_id,entry_key):
    row=db.execute("SELECT COALESCE(MAX(attempt),0)+1 AS n FROM posting_journal WHERE run_id=? AND entry_key=?",(run_id,entry_key)).fetchone()
    return row["n"]
def apply_ledger(run_id,entries,fail_keys=()):
    """幂等入账：同(run,entry_key)重试不重复记账；任一分录失败则本次分录整体回滚，
    失败痕迹单独落库保留，重跑从断点继续（fail_keys 模拟入账中断）。返回本批次新入账数。"""
    fail_keys=set(fail_keys or ())
    failures=[];applied=0
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            for entry in entries:
                key=entry["entry_key"];attempt=next_attempt(db,run_id,key)
                existing=db.execute("SELECT 1 FROM postings WHERE run_id=? AND entry_key=?",(run_id,key)).fetchone()
                if existing is not None:
                    # 已入账：重试仅登记一次幂等跳过，不产生第二条分录
                    db.execute("INSERT OR IGNORE INTO posting_journal VALUES(?,?,?,?,?)",
                               (run_id,key,attempt,"SKIP","重试补证不重复记账"))
                    continue
                if key in fail_keys:
                    failures.append((run_id,key,attempt,"FAILED","入账中断，等待恢复"))
                    raise DomainError("POSTING_INTERRUPTED","入账中断，可重试恢复",409)
                db.execute("INSERT INTO postings VALUES(?,?,?,?,?,?,?,?,?)",
                           (run_id,key,entry["ordinal"],entry["direction"],entry["channel"],
                            entry["kind"],str(entry["amount"]),entry["ref_id"],entry["state"]))
                db.execute("INSERT INTO posting_journal VALUES(?,?,?,?,?)",
                           (run_id,key,attempt,"POSTED","入账成功"))
                applied+=1
        except Exception:
            db.rollback();raise
        finally:
            # 失败痕迹在独立事务中保留，不受分录回滚影响，作为恢复依据
            if failures:
                with connection() as log_db:
                    log_db.executemany("INSERT OR REPLACE INTO posting_journal VALUES(?,?,?,?,?)",failures)
    return applied
