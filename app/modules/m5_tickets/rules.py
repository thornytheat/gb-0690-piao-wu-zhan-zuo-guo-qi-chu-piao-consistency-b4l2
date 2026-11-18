from app.reasons import rejected
def verify_tickets(rows,payments):
    good=[];bad=[];tickets=[];used_tickets=set();sold_seats=set()
    # 仅已归属款可供出票；待核款（凭据未齐）不得出票，避免给错单出票
    spendable=[p for p in payments if p.get('state','已归属')=='已归属']
    for row in sorted(rows,key=lambda r:(r['time'],r['id'])):
        if row['type']!='issue':good.append(row);continue
        matches=[p for p in spendable if p['seat']==row['seat'] and p['order']==row['order'] and p['time']<=row['time']]
        if len(matches)!=1:
            pending=[p for p in payments if p['seat']==row['seat'] and p['order']==row['order'] and p.get('state')=='待核']
            bad.append(rejected(row,'REVIEW' if pending else 'ORPHAN','代收凭据未齐，暂不能出票' if pending else '出票缺少有效支付'));continue
        pay=matches[0]
        sale_channel=pay.get('sale_channel',pay['channel']);pay_channel=pay.get('pay_channel',pay['channel'])
        # 出票渠道认原售票渠道（sale_channel），收款仍记代收渠道（pay_channel）
        if row['channel']!=sale_channel:bad.append(rejected(row,'CONFLICT','出票渠道与售票渠道不符'));continue
        if not row['ticket']:bad.append(rejected(row,'MISSING','票号缺失'));continue
        if row['ticket'] in used_tickets or row['seat'] in sold_seats:bad.append(rejected(row,'CONFLICT','票号或座席重复出票'));continue
        if row['amount']!=pay['amount']:bad.append(rejected(row,'CONFLICT','票面金额与支付不符'));continue
        used_tickets.add(row['ticket']);sold_seats.add(row['seat'])
        tickets.append({**row,'lease':pay['lease'],'state':'已出票','sale_channel':sale_channel,
                        'pay_channel':pay_channel,'voucher':pay.get('voucher','')});good.append(row)
    return good,bad,tickets
