from .rules import build_entries
from app import store
def execute(ctx):
    entries=build_entries(ctx['payments'],ctx['tickets'])
    ctx['posting_entries']=entries
    run_id=ctx.get('manifest',{}).get('run_id')
    posted=store.ledger_rows(run_id) if run_id else []
    posted_keys={r['entry_key'] for r in posted}
    pending=[e for e in entries if e['entry_key'] not in posted_keys]
    ctx['stages'].append({'title':'入账台账','rows':posted or entries,'metrics':{
        '应入账分录':len(entries),'已入账':len(posted),'待入账':len(pending),
        '重试安全':'同键幂等'}});return ctx
