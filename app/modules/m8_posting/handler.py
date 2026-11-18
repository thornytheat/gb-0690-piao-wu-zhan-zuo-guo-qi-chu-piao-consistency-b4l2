from flask import Blueprint,request,jsonify
from app.pipeline import run
from app import store
from app.modules.m8_posting.rules import build_entries
from app.errors import DomainError
bp=Blueprint("m8",__name__)
@bp.route("/api/m8",methods=["GET","POST"])
def endpoint():
    payload=request.get_json(silent=True) if request.method=="POST" else {}
    if not isinstance(payload,dict): raise DomainError("BODY","请求必须是对象")
    raw=payload.get("text")
    if raw is not None and not isinstance(raw,str): raise DomainError("TEXT","数据必须为文本")
    # 走完整 8 阶段（含入账台账），但不落库；实际持久化由 /api/posting/<run>/sync 负责
    return jsonify(run(raw,payload.get("params"),stop=8,persist=False))
@bp.post("/api/posting/<run_id>/sync")
def sync(run_id):
    # 幂等入账：重试补证不重复记账；中断后再次调用从断点恢复
    result=store.fetch(run_id)
    fail=request.get_json(silent=True) or {}
    fail_keys=fail.get("fail_keys") if isinstance(fail,dict) else None
    entries=build_entries(result['payments'],result['tickets'])
    applied=store.apply_ledger(run_id,entries,fail_keys)
    return jsonify({'run_id':run_id,'applied':applied,'ledger':store.ledger_rows(run_id),
                    'journal':store.ledger_journal(run_id)})
@bp.get("/api/posting/<run_id>")
def ledger(run_id):
    return jsonify({'run_id':run_id,'ledger':store.ledger_rows(run_id),
                    'journal':store.ledger_journal(run_id)})
