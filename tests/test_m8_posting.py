import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.normalize import instant
from app.config import SAMPLES
from app.modules.m5_tickets.rules import verify_tickets
from app.modules.m6_reconcile.rules import reconcile, settlements
from app.errors import DomainError
from app import store
from app.modules.m8_posting.rules import build_entries

def agency_pay(state='已归属', voucher='V1'):
    return dict(id='P1', channel='票社', seat='A-01', order='O',
                time=instant('2026-11-17T10:10:00Z'), type='pay', amount=D(100), lease='L',
                state=state, sale_channel='官方', pay_channel='票社', voucher=voucher if state=='已归属' else '')
def issue(**kw):
    x = dict(id='I', channel='官方', seat='A-01', order='O',
             time=instant('2026-11-17T10:20:00Z'), type='issue', amount=D(100),
             ticket='000001', _line=9)
    x.update(kw); return x

def test_original_channel_issues_against_agency_money():
    good, bad, tickets = verify_tickets([issue()], [agency_pay()])
    assert len(tickets) == 1 and not bad
    t = tickets[0]
    assert t['channel'] == '官方' == t['sale_channel']      # 原售票渠道出票
    assert t['pay_channel'] == '票社'                        # 收款仍记代收渠道

def test_pending_payment_blocks_issue():
    good, bad, tickets = verify_tickets([issue()], [agency_pay(state='待核', voucher='')])
    assert tickets == [] and bad[0]['code'] == 'REVIEW'

def test_collector_cannot_issue_original_order():
    good, bad, tickets = verify_tickets([issue(channel='票社')], [agency_pay()])
    assert tickets == [] and bad[0]['code'] == 'CONFLICT'

def test_reconcile_splits_pending_and_owned():
    bal = reconcile([agency_pay('已归属'), agency_pay('待核', '')], [])
    by = {b['channel']: b for b in bal}
    assert by['票社']['owned'] == D(100) and by['票社']['pending'] == D(100)
    assert by['票社']['state'] == '待核'
    assert by['票社']['delta'] == D(100)  # 悬单只算已归属

def test_settlement_pairs_same_money():
    payments = [agency_pay()]
    tickets = [dict(channel='官方', seat='A-01', order='O', amount=D(100), ticket='000001')]
    s = settlements(payments, tickets)
    assert s[0]['state'] == '已核销' and s[0]['pay_channel'] == '票社' and s[0]['ticket'] == '000001'

def test_real_agency_writeoff(raw_agency):
    r = run(raw_agency, persist=False)
    done = [s for s in r['settlements'] if s['state'] == '已核销']
    assert any(s['pay_channel'] == '票社' and s['sale_channel'] == '官方' for s in done)
    bal = {b['channel']: b for b in r['channel_balances']}
    assert D(bal['票社']['pending']) == D(100) and D(bal['票社']['owned']) == D(100)

def test_ledger_idempotent_retry(raw_agency, isolate):
    r = run(raw_agency)
    rid = r['manifest']['run_id']
    entries = build_entries(r['payments'], r['tickets'])
    first = store.apply_ledger(rid, entries)
    second = store.apply_ledger(rid, entries)   # 重试补证
    assert first == len(entries) and second == 0
    assert len(store.ledger_rows(rid)) == len(entries)
    assert all(j['status'] == 'SKIP' for j in store.ledger_journal(rid) if j['attempt'] == 2)

def test_ledger_resumes_after_interruption(raw_agency, isolate):
    r = run(raw_agency)
    rid = r['manifest']['run_id']
    entries = build_entries(r['payments'], r['tickets'])
    with pytest.raises(DomainError):
        store.apply_ledger(rid, entries, fail_keys={entries[1]['entry_key']})
    assert store.ledger_rows(rid) == []          # 中断整体回滚
    resumed = store.apply_ledger(rid, entries)   # 恢复后全量入账
    assert resumed == len(entries)
    assert {j['status'] for j in store.ledger_journal(rid)} >= {'FAILED', 'POSTED'}

def test_posting_sync_api(client, raw_agency):
    r = client.post('/api/runs', json={'text': raw_agency.decode('utf-8')}).json
    rid = r['manifest']['run_id']
    a = client.post(f'/api/posting/{rid}/sync', json={}).json
    b = client.post(f'/api/posting/{rid}/sync', json={}).json
    assert a['applied'] > 0 and b['applied'] == 0
    assert len(a['ledger']) == len(b['ledger'])
    got = client.get(f'/api/posting/{rid}').json
    assert len(got['ledger']) == len(a['ledger'])

@pytest.fixture
def raw_agency():
    return (SAMPLES / 'agency.csv').read_bytes()
