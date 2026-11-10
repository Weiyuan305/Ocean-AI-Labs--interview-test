import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def local_time(value, zone):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(ZoneInfo(zone))


def connect(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    return db


SCHEMA = '''
CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS actors(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id), email TEXT NOT NULL UNIQUE, token TEXT NOT NULL UNIQUE, UNIQUE(tenant_id,id));
CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id), title TEXT NOT NULL, UNIQUE(tenant_id,id));
CREATE TABLE IF NOT EXISTS learners(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id), name TEXT NOT NULL, search_name TEXT NOT NULL, UNIQUE(tenant_id,id));
CREATE TABLE IF NOT EXISTS enrollments(tenant_id INTEGER NOT NULL, course_id INTEGER NOT NULL, learner_id INTEGER NOT NULL, completed INTEGER NOT NULL CHECK(completed IN(0,1)), PRIMARY KEY(tenant_id,course_id,learner_id), FOREIGN KEY(tenant_id,course_id) REFERENCES courses(tenant_id,id), FOREIGN KEY(tenant_id,learner_id) REFERENCES learners(tenant_id,id));
CREATE TABLE IF NOT EXISTS certificates(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, course_id INTEGER NOT NULL, learner_id INTEGER NOT NULL, serial_number TEXT NOT NULL UNIQUE, issued_at TEXT NOT NULL, issue_date_local TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN('ACTIVE','REVOKED')), revoked_at TEXT, UNIQUE(tenant_id,id), UNIQUE(tenant_id,course_id,learner_id), FOREIGN KEY(tenant_id,course_id) REFERENCES courses(tenant_id,id), FOREIGN KEY(tenant_id,learner_id) REFERENCES learners(tenant_id,id), CHECK((status='ACTIVE' AND revoked_at IS NULL) OR (status='REVOKED' AND revoked_at IS NOT NULL)));
CREATE TABLE IF NOT EXISTS issuance_operations(id TEXT PRIMARY KEY, tenant_id INTEGER NOT NULL, actor_id INTEGER NOT NULL, idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(tenant_id,actor_id,idempotency_key), FOREIGN KEY(tenant_id,actor_id) REFERENCES actors(tenant_id,id));
CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, certificate_id INTEGER NOT NULL, actor_id INTEGER NOT NULL, event_type TEXT NOT NULL CHECK(event_type IN('ISSUED','REVOKED')), created_at TEXT NOT NULL, UNIQUE(tenant_id,certificate_id,event_type), FOREIGN KEY(tenant_id,certificate_id) REFERENCES certificates(tenant_id,id), FOREIGN KEY(tenant_id,actor_id) REFERENCES actors(tenant_id,id));
CREATE INDEX IF NOT EXISTS cert_date ON certificates(tenant_id,issue_date_local,id);
CREATE INDEX IF NOT EXISTS cert_serial ON certificates(tenant_id,serial_number,id);
CREATE INDEX IF NOT EXISTS cert_status ON certificates(tenant_id,status,id);
CREATE INDEX IF NOT EXISTS learner_name ON learners(tenant_id,name,id);
'''


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM tenants WHERE id=1').fetchone():
            db.commit()
            return
        db.executemany('INSERT INTO tenants VALUES(?,?,?)', [(1,'East','Australia/Sydney'),(2,'West','Australia/Perth')])
        db.executemany('INSERT INTO actors VALUES(?,?,?,?)', [(1,1,'alice@east.test','east-demo-token'),(2,2,'bob@west.test','west-demo-token')])
        db.executemany('INSERT INTO courses VALUES(?,?,?)', [(1,1,'Safety 101'),(2,2,'Safety 101'),(3,1,'First Aid'),(4,1,'Date Ordering')])
        people = [(1,1,'Alex Lee'),(2,1,'Casey Morgan'),(3,1,'Jordan Chen'),(4,2,'Alex Lee'),(5,2,'Casey Morgan'),(6,2,'Jordan Chen'),(7,1,'Date Later'),(8,1,'Date Earlier')]
        db.executemany('INSERT INTO learners VALUES(?,?,?,?)', [(i,t,n,n.casefold()) for i,t,n in people])
        db.executemany('INSERT INTO enrollments VALUES(?,?,?,?)',[(1,1,1,1),(1,1,2,0),(1,1,3,1),(2,2,4,1),(2,2,5,0),(2,2,6,1),(1,4,7,1),(1,4,8,1)])
        for cid,tenant,course,learner,stamp in [(1,1,1,3,'2026-01-10T13:30:00Z'),(2,2,2,6,'2026-01-10T13:30:00Z'),(3,1,4,7,'2026-01-08T08:00:00Z'),(4,1,4,8,'2026-01-08T01:00:00Z')]:
            zone = 'Australia/Sydney' if tenant == 1 else 'Australia/Perth'
            db.execute('INSERT INTO certificates VALUES(?,?,?,?,?,?,?,?,?)',(cid,tenant,course,learner,f'DEMO-{cid:04}',stamp,local_time(stamp,zone).date().isoformat(),'ACTIVE',None))
            db.execute('INSERT INTO audit_events(tenant_id,certificate_id,actor_id,event_type,created_at) VALUES(?,?,?,?,?)',(tenant,cid,tenant,'ISSUED',stamp))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
