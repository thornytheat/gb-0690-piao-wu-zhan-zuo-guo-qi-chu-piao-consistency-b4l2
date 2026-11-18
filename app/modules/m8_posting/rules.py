# 入账分录构造：把对账结果投影为借贷分录，全部为可重放的派生数据。
# 收款记在实际收款渠道（代收为票社）；出票核销原售票渠道的同一笔款。
def build_entries(payments, tickets):
    entries=[]; ordinal=0
    ticket_index={(t['order'],t['seat']):t for t in tickets}
    def add(direction,channel,kind,amount,ref_id,state):
        nonlocal ordinal; ordinal+=1
        entries.append({'entry_key':f"{kind}:{ref_id}",'ordinal':ordinal,'direction':direction,
                        'channel':channel,'kind':kind,'amount':amount,'ref_id':ref_id,'state':state})
    for p in sorted(payments,key=lambda x:(x['time'],x['id'])):
        pay_channel=p.get('pay_channel',p['channel'])
        if p.get('state')=='待核':
            add('借',pay_channel,'待核收款',p['amount'],p['id'],'待核')
        else:
            add('借',pay_channel,'已归属收款',p['amount'],p['id'],'已归属')
            t=ticket_index.get((p['order'],p['seat']))
            if t is not None:
                # 出票后核销同一笔款：原售票渠道应收与代收渠道实收付讫对冲
                add('贷',p.get('sale_channel',p['channel']),'出票核销',p['amount'],t['ticket'],'已核销')
    return entries
