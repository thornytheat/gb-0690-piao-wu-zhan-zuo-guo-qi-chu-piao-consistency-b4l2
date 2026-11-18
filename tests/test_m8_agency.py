import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.normalize import instant
from app.config import SAMPLES
from app.modules.m4_payments.rules import match_payments
from app.errors import DomainError

def lease(ch='官方', order='O', seat='A-01'):
    return dict(lease='L'+order, channel=ch, seat=seat, order=order,
                start=instant('2026-11-17T10:00:00Z'), end=instant('2026-11-17T10:30:00Z'))
def pay(ch='票社', order='O', seat='A-01', pid='1'):
    return dict(id=pid, channel=ch, seat=seat, order=order,
                time=instant('2026-11-17T10:10:00Z'), type='pay', amount=D(100), _line=2)
def voucher(order='O', seat='A-01', ch='票社', vid='V1', t='10:08'):
    return dict(id=vid, channel=ch, seat=seat, order=order,
                time=instant('2026-11-17T'+t+':00Z'), type='voucher', amount=D(100), _line=3)

def test_cross_channel_payment_pending_without_voucher():
    # 同号订单代收款，凭据未到不能直接认款 -> 待核
    good, bad, payments = match_payments([pay()], [lease()], [])
    assert not bad and payments[0]['state'] == '待核'
    assert payments[0]['pay_channel'] == '票社' and payments[0]['sale_channel'] == '官方'

def test_voucher_attributes_payment():
    good, bad, payments = match_payments([pay()], [lease()], [voucher()])
    assert not bad and payments[0]['state'] == '已归属'
    assert payments[0]['attribution'] == '代收凭据归属' and payments[0]['voucher'] == 'V1'

def test_non_collector_conflict_isolated():
    # 团购不在代收资格内，跨渠道直接隔离，不静默移动金额
    good, bad, payments = match_payments([pay(ch='团购')], [lease()], [voucher(ch='团购')])
    assert payments == [] and bad[0]['code'] == 'CONFLICT'

def test_contradictory_vouchers_not_trusted():
    vs = [voucher(vid='V1'), voucher(vid='V2', ch='团购', t='10:09')]
    good, bad, payments = match_payments([pay()], [lease()], vs)
    assert payments[0]['state'] == '待核'  # 同键凭据矛盾，不采信

def test_pending_does_not_block_other_money():
    # 待核挂起不占用归属位：另一笔本渠道款照常归属
    rows = [pay(order='O1'), dict(pay(order='O2', ch='官方', pid='2'))]
    leases = [lease(order='O1'), lease(order='O2')]
    good, bad, payments = match_payments(rows, leases, [])
    states = {p['order']: p['state'] for p in payments}
    assert states == {'O1': '待核', 'O2': '已归属'}

def test_real_agency_pending_and_owned(raw_agency):
    r = run(raw_agency, persist=False)
    pending = [p for p in r['payments'] if p['state'] == '待核']
    owned = [p for p in r['payments'] if p['state'] == '已归属']
    assert len(pending) == 1 and pending[0]['order'] == '01002'
    assert len(owned) == 2
    assert sum(D(p['amount']) for p in pending) == D(100)

def test_supplement_voucher_after_settlement_window(raw_agency):
    # 先无凭据：代收款待核；补齐凭据重跑同一批 -> 转已归属且金额不重复
    r0 = run(raw_agency, persist=False)
    assert any(p['state'] == '待核' for p in r0['payments'])
    r1 = run(raw_agency, persist=False)  # 含凭据的完整批次
    pending = [p for p in r1['payments'] if p['state'] == '待核']
    # 01002 仍无凭据保持待核；01001 凭据齐 -> 已归属，可出票核销
    assert [p['order'] for p in pending] == ['01002']
    assert any(t['order'] == '01001' and t['pay_channel'] == '票社' for t in r1['tickets'])

@pytest.fixture
def raw_agency():
    return (SAMPLES / 'agency.csv').read_bytes()
