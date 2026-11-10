"""Generate an isolated, repeatable performance dataset; never target the demo DB."""
import argparse
from pathlib import Path
from .database import connect, initialize, local_time


def generate(path, count=100000):
    if Path(path).resolve()==Path('data/demo.sqlite3').resolve():
        raise ValueError('Use a separate performance database, not data/demo.sqlite3.')
    initialize(path)
    db=connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        existing=db.execute('SELECT count(*) FROM certificates WHERE tenant_id=1 AND course_id=1000').fetchone()[0]
        if existing==count:
            db.commit()
            return
        if existing:
            raise ValueError('Existing fixture has a different size; choose a fresh database path.')
        db.execute("INSERT INTO courses VALUES(1000,1,'Export Performance')")
        stamp='2026-01-10T13:30:00Z'
        day=local_time(stamp,'Australia/Sydney').date().isoformat()
        for start in range(0,count,1000):
            batch=range(start,min(count,start+1000))
            db.executemany('INSERT INTO learners VALUES(?,?,?,?)',[(10000+i,1,f'Export Fixture {i%100:03}',f'export fixture {i%100:03}') for i in batch])
            db.executemany('INSERT INTO enrollments VALUES(1,1000,?,1)',[(10000+i,) for i in batch])
            db.executemany("INSERT INTO certificates VALUES(?,1,1000,?,?,?,?,'ACTIVE',NULL)",[(10000+i,10000+i,f'PERF-{i:06}',stamp,day) for i in batch])
            db.executemany("INSERT INTO audit_events(tenant_id,certificate_id,actor_id,event_type,created_at) VALUES(1,?,1,'ISSUED',?)",[(10000+i,stamp) for i in batch])
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    args=parser.parse_args()
    generate(args.db)
    print('Performance database ready: 100,000 East fixture certificates.')
