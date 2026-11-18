from .rules import match_payments
def execute(ctx):
    vouchers=[r for r in ctx['records'] if r['type']=='voucher']
    rows,bad,payments=match_payments(ctx['records'],ctx['leases'],vouchers)
    ctx['records']=rows;ctx['quarantine'].extend(bad);ctx['payments']=payments
    pending=[p for p in payments if p['state']=='待核'];owned=[p for p in payments if p['state']=='已归属']
    ctx['stages'].append({'title':'支付归属','rows':payments,'metrics':{
        '已归属':len(owned),'待核':len(pending),'无效支付':len(bad),
        '已归属金额 CNY':str(sum((r['amount'] for r in owned),0)),
        '待核金额 CNY':str(sum((r['amount'] for r in pending),0))}});return ctx
