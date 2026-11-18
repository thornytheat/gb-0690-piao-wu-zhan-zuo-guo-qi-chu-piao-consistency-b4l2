from .rules import reconcile,settlements
def execute(ctx):
    ctx['channel_balances']=reconcile(ctx['payments'],ctx['tickets'])
    ctx['settlements']=settlements(ctx['payments'],ctx['tickets'])
    pending=sum(1 for p in ctx['payments'] if p['state']=='待核')
    ctx['stages'].append({'title':'渠道对账','rows':ctx['channel_balances'],'metrics':{
        '渠道':len(ctx['channel_balances']),'已归属':len(ctx['payments'])-pending,'待核':pending,
        '已出票':len(ctx['tickets']),'待核销':len(ctx['settlements'])-len(ctx['tickets'])}});return ctx
