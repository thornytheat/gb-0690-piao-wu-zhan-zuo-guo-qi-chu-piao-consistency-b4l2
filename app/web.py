from flask import render_template,request
from app import store
from app.pipeline import run
from app.config import TITLE,MODULES,STAGES,COLUMNS,SAMPLES,DEFAULTS
def view(stage):
    if not 1<=stage<=8: return "页面不存在",404
    run_id=request.args.get("run")
    result=store.fetch(run_id) if run_id else run()
    sample=(SAMPLES/"dirty.csv").read_text(encoding="utf-8-sig")
    data=result["stages"][stage-1]
    sold={t['seat'] for t in result['tickets']};paid={t['seat'] for t in result['payments'] if t.get('state')=='已归属'};held={t['seat'] for t in result['leases']}
    pending={t['seat'] for t in result['payments'] if t.get('state')=='待核'}
    seats=[{'seat':f'A-{i:02d}','state':'已出票' if f'A-{i:02d}' in sold else '待核' if f'A-{i:02d}' in pending else '待出票' if f'A-{i:02d}' in paid else '已过期' if f'A-{i:02d}' in held else '空闲'} for i in range(1,17)]
    ledger=store.ledger_rows(result["manifest"]["run_id"]) if stage==8 else []
    journal=store.ledger_journal(result["manifest"]["run_id"]) if stage==8 else []
    return render_template(f"m{stage}.html",title=TITLE,modules=MODULES,stage=stage,result=result,data=data,
                           sample=sample,defaults=DEFAULTS,columns=COLUMNS,history=store.history(),seats=seats,
                           ledger=ledger,journal=journal)
