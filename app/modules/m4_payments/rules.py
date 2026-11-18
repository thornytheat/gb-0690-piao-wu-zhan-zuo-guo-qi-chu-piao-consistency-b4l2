from app.reasons import rejected
# 官方售票可由票社代收：渠道与租约不一致的同号订单付款不直接认款，
# 先挂“待核”，待代收凭据补齐后归属；凭据未到前同号订单不得确认。
COLLECTORS = {'票社'}  # 具备代收资格的渠道
def voucher_index(vouchers):
    # 凭据按(订单,座席)索引；同键多渠道相互矛盾或重复时不采信（None 标记）
    evidence = {}
    for v in sorted(vouchers, key=lambda x: (x['time'], x['id'])):
        key = (v['order'], v['seat'])
        if key not in evidence:
            evidence[key] = v
        elif evidence[key] is None or evidence[key]['channel'] != v['channel']:
            evidence[key] = None
    return evidence
def match_payments(rows, leases, vouchers=None):
    evidence = voucher_index(vouchers or [])
    good = []; bad = []; payments = []; attributed_leases = set(); pending_orders = set()
    for row in sorted(rows, key=lambda x: (x['time'], x['id'])):
        if row['type'] != 'pay':
            good.append(row); continue
        candidates = [l for l in leases if l['seat'] == row['seat'] and l['order'] == row['order'] and l['start'] <= row['time'] < l['end']]
        if len(candidates) != 1:
            bad.append(rejected(row, 'EXPIRED', '付款未落入有效占座区间')); continue
        lease = candidates[0]
        if row['channel'] == lease['channel']:
            if lease['lease'] in attributed_leases:
                bad.append(rejected(row, 'DUPLICATE', '租约已支付')); continue
            attributed_leases.add(lease['lease'])
            payments.append({**row, 'lease': lease['lease'], 'state': '已归属', 'attribution': '本渠道收款',
                             'sale_channel': lease['channel'], 'pay_channel': row['channel'], 'voucher': ''})
            good.append(row); continue
        # 跨渠道：仅票社代收官方售票可进入待核，其余跨渠道冲突逐行隔离
        if row['channel'] not in COLLECTORS or lease['channel'] != '官方':
            bad.append(rejected(row, 'CONFLICT', '支付渠道与占座渠道不符且非代收')); continue
        if (row['order'], row['seat']) in pending_orders:
            bad.append(rejected(row, 'DUPLICATE', '代收款待核中，重复收款')); continue
        voucher = evidence.get((row['order'], row['seat']))
        if voucher is None:
            # 凭据未到：同号订单不直接认款，挂待核，不占用归属位，整批中已核实款照常结账
            pending_orders.add((row['order'], row['seat']))
            payments.append({**row, 'lease': lease['lease'], 'state': '待核', 'attribution': '待代收凭据',
                             'sale_channel': lease['channel'], 'pay_channel': row['channel'], 'voucher': ''})
            good.append(row); continue
        if lease['lease'] in attributed_leases:
            bad.append(rejected(row, 'DUPLICATE', '租约已支付')); continue
        attributed_leases.add(lease['lease'])
        payments.append({**row, 'lease': lease['lease'], 'state': '已归属', 'attribution': '代收凭据归属',
                         'sale_channel': lease['channel'], 'pay_channel': row['channel'], 'voucher': voucher['id']})
        good.append(row)
    return good, bad, payments
