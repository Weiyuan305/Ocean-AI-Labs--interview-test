from concurrent.futures import ThreadPoolExecutor
import csv
import io
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient
from backend.app import create_app

ALICE = {"Authorization": "Bearer east-demo-token"}
BOB = {"Authorization": "Bearer west-demo-token"}


@pytest.fixture
def env(tmp_path):
    path = tmp_path / "test.sqlite3"
    app = create_app(str(path))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, path, app


def test_actor_isolation_and_detail_dates(env):
    client, _, _ = env
    assert client.get('/api/certificates').status_code == 401
    east = client.get('/api/certificates', headers=ALICE)
    assert east.status_code == 200
    assert east.json()['total'] == 3
    west = client.get('/api/certificates', headers=BOB).json()
    assert west['total'] == 1
    assert client.get('/api/certificates/1', headers=BOB).status_code == 404
    assert client.get('/api/certificates/1', headers=ALICE).json()['issued_at_local'] == '2026-01-11T00:30:00+11:00'
    assert client.get('/api/certificates/2', headers=BOB).json()['issued_at_local'] == '2026-01-10T21:30:00+08:00'
    assert client.get('/api/certificates?tenant_id=1', headers=BOB).status_code == 422


def test_query_validation_and_calendar_sort(env):
    client, _, _ = env
    for query in ['page=0', 'page_size=101', 'sort=bad', 'order=bad']:
        assert client.get('/api/certificates?' + query, headers=ALICE).status_code == 422
    assert client.get('/api/certificates?q=JORDAN', headers=ALICE).json()['total'] == 1
    assert client.get('/api/certificates?q=%25', headers=ALICE).json()['total'] == 0
    data = client.get('/api/certificates?sort=issue_date&order=asc&page_size=2', headers=ALICE).json()
    assert [x['id'] for x in data['items']] == [3, 4]
    assert data['total'] == 3


def issue(client, key='one', course=1, headers=ALICE):
    return client.post('/api/certificate-issuances',json={'course_id':course},headers={**headers,'Idempotency-Key':key})


def counts(path):
    with sqlite3.connect(path) as db:
        return tuple(db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['certificates','audit_events','issuance_operations'])


def test_bulk_retry_conflict_and_eligibility(env):
    client,path,_ = env
    original = issue(client)
    assert original.status_code == 200
    result = original.json()
    assert result['summary'] == {'issued':1,'skipped':2,'failed':0}
    assert [x['reason'] for x in result['outcomes']] == [None,'INCOMPLETE','ALREADY_CERTIFIED']
    assert issue(client).json() == result
    assert counts(path) == (5,5,1)
    assert issue(client,course=3).status_code == 409
    assert issue(client,course=2).status_code == 404
    assert counts(path) == (5,5,1)
    assert issue(client,headers=BOB).status_code == 404
    assert client.post('/api/certificate-issuances',json={'course_id':1,'extra':1},headers={**ALICE,'Idempotency-Key':'one'}).status_code == 422
    cert_id = result['outcomes'][0]['certificate_id']
    first = client.post(f'/api/certificates/{cert_id}/revoke',headers=ALICE)
    assert first.status_code == 200
    assert first.json()['status'] == 'REVOKED'
    assert client.post(f'/api/certificates/{cert_id}/revoke',headers=ALICE).json() == first.json()
    assert issue(client).json() == result
    assert issue(client,key='new').json()['summary']['issued'] == 0
    assert counts(path) == (5,6,2)
    assert client.post(f'/api/certificates/{cert_id}/revoke',headers=BOB).status_code == 404



def test_concurrent_same_and_different_keys(env):
    _,path,app = env
    gate = threading.Barrier(4)
    def send(i):
        with TestClient(app) as client:
            gate.wait()
            return issue(client,key='parallel')
    with ThreadPoolExecutor(4) as pool:
        responses = list(pool.map(send,range(4)))
    assert [r.status_code for r in responses] == [200]*4
    assert all(r.json() == responses[0].json() for r in responses)
    assert counts(path) == (5,5,1)
    def other(i):
        with TestClient(app) as client:
            gate.wait()
            return issue(client,key=f'other-{i}')
    with ThreadPoolExecutor(4) as pool:
        responses = list(pool.map(other,range(4)))
    assert all(r.status_code == 200 and r.json()['summary']['issued']==0 for r in responses)
    assert counts(path) == (5,5,5)


def test_concurrent_revocation(env):
    _,path,app=env
    gate=threading.Barrier(4)
    def send(i):
        with TestClient(app) as client:
            gate.wait()
            return client.post('/api/certificates/1/revoke',headers=ALICE)
    with ThreadPoolExecutor(4) as pool:
        responses=list(pool.map(send,range(4)))
    assert all(r.status_code==200 for r in responses)
    assert len({r.json()['revoked_at'] for r in responses})==1
    assert counts(path)==(4,5,0)


def test_audit_failure_rolls_back_operation(env):
    client,path,_=env
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT,'test failure'); END")
    assert issue(client).status_code==500
    assert counts(path)==(4,4,0)
    with sqlite3.connect(path) as db:
        db.execute('DROP TRIGGER fail_audit')
    assert issue(client).json()['summary']['issued']==1


def test_export_filter_order_dates_and_csv_escaping(env):
    client,path,_=env
    response=client.get('/api/certificates/export.csv?sort=issue_date&order=asc',headers=ALICE)
    assert response.status_code==200
    rows=list(csv.DictReader(io.StringIO(response.text)))
    assert [r['serial_number'] for r in rows]==['DEMO-0003','DEMO-0004','DEMO-0001']
    assert rows[-1]['issue_date_local']=='2026-01-11'
    west=list(csv.DictReader(io.StringIO(client.get('/api/certificates/export.csv',headers=BOB).text)))
    assert len(west)==1 and west[0]['issue_date_local']=='2026-01-10'
    assert client.get('/api/certificates/export.csv?page=1',headers=ALICE).status_code==422
    name='Zoë, "Example"\nLearner'
    with sqlite3.connect(path) as db:
        db.execute('UPDATE learners SET name=?,search_name=? WHERE id=3',(name,name.casefold()))
    data=client.get('/api/certificates/export.csv',params={'q':'zoË'},headers=ALICE)
    assert list(csv.DictReader(io.StringIO(data.text)))[0]['learner_name']==name
    assert len(list(csv.DictReader(io.StringIO(client.get('/api/certificates/export.csv?q=missing',headers=ALICE).text))))==0


def test_learner_rejection_and_restart_replay(env,monkeypatch):
    from backend import certificates
    client,path,_=env
    original=certificates.create_certificate
    def rejected(*args):
        original(*args)
        raise certificates.IssuanceRejected()
    monkeypatch.setattr(certificates,'create_certificate',rejected)
    result=issue(client).json()
    assert result['summary']=={'issued':0,'skipped':2,'failed':1}
    assert counts(path)==(4,4,1)
    monkeypatch.setattr(certificates,'create_certificate',original)
    with TestClient(create_app(str(path))) as restarted:
        assert issue(restarted).json()==result
        assert issue(restarted,key='retry-new').json()['summary']['issued']==1


def test_winter_timezone(env):
    client,path,_=env
    with sqlite3.connect(path) as db:
        db.execute("UPDATE certificates SET issued_at='2026-07-10T13:30:00Z',issue_date_local='2026-07-10' WHERE id=1")
    assert client.get('/api/certificates/1',headers=ALICE).json()['issued_at_local']=='2026-07-10T23:30:00+10:00'
