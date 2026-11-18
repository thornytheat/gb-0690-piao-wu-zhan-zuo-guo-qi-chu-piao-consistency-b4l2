from decimal import Decimal as D
from collections import defaultdict
# 收款记在实际收款渠道（代收场景为票社），出票记在原售票渠道（官方）；
# 待核与已归属分列，待核款不参与出票核销，整批中已核实款照常结账。
def reconcile(payments,tickets):
    channels=defaultdict(lambda:{'paid':D(0),'pending':D(0),'owned':D(0),'ticketed':D(0),
                                 'payments':0,'pending_count':0,'tickets':0})
    for p in payments:
        cell=channels[p['channel']]
        cell['payments']+=1;cell['paid']+=p['amount']
        if p.get('state')=='待核':
            cell['pending']+=p['amount'];cell['pending_count']+=1
        else:
            cell['owned']+=p['amount']
    for t in tickets:
        cell=channels[t['channel']]
        cell['ticketed']+=t['amount'];cell['tickets']+=1
    result=[]
    for name,row in sorted(channels.items()):
        # 悬单=已归属但尚未出票的金额；待核款单列，不混入悬单
        delta=row['owned']-row['ticketed']
        if row['pending']>0:state='待核'
        elif row['paid']==row['ticketed'] and row['payments']==row['tickets']:state='通过'
        else:state='待出票'
        result.append({'channel':name,**row,'delta':delta,'state':state})
    return result
def settlements(payments,tickets):
    # 出票后核销同一笔款：按(订单,座席)把已出票与已归属款配对
    ticket_index={(t['order'],t['seat']):t for t in tickets}
    out=[]
    for p in payments:
        if p.get('state')!='已归属':continue
        t=ticket_index.get((p['order'],p['seat']))
        out.append({'order':p['order'],'seat':p['seat'],'sale_channel':p.get('sale_channel',p['channel']),
                    'pay_channel':p.get('pay_channel',p['channel']),'amount':p['amount'],
                    'voucher':p.get('voucher',''),
                    'state':'已核销' if t else '待核销','ticket':t['ticket'] if t else ''})
    return out
