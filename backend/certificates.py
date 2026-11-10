from dataclasses import dataclass
from .database import connect, local_time


class DomainError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class Actor:
    id: int
    tenant_id: int
    email: str
    timezone: str


def actor_for(path, authorization):
    db = connect(path)
    try:
        token = authorization[7:] if authorization and authorization.startswith('Bearer ') else ''
        row = db.execute('SELECT a.*, t.timezone FROM actors a JOIN tenants t ON t.id=a.tenant_id WHERE a.token=?',(token,)).fetchone()
        if not row:
            raise DomainError(401,'UNAUTHORIZED','A valid demo actor token is required.')
        return Actor(row['id'],row['tenant_id'],row['email'],row['timezone'])
    finally:
        db.close()


SELECT = '''SELECT c.*, l.name AS learner_name, co.title AS course_title FROM certificates c
JOIN learners l ON l.id=c.learner_id AND l.tenant_id=c.tenant_id
JOIN courses co ON co.id=c.course_id AND co.tenant_id=c.tenant_id'''
SORTS = {'learner_name':'l.name COLLATE BINARY','course_title':'co.title COLLATE BINARY','serial_number':'c.serial_number COLLATE BINARY','issue_date':'c.issue_date_local','status':'c.status'}


def query_sql(actor, query):
    q = query.q.strip().casefold().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    where = " WHERE c.tenant_id=? AND (l.search_name LIKE ? ESCAPE '\\' OR lower(c.serial_number) LIKE ? ESCAPE '\\')"
    params = (actor.tenant_id, '%' + q + '%', '%' + q + '%')
    order = f' ORDER BY {SORTS[query.sort]} {query.order.upper()}, c.id ASC'
    return where, params, order


def certificate_dict(row, actor):
    data = dict(row)
    data.pop('tenant_id', None)
    data['issued_at_local'] = local_time(data['issued_at'],actor.timezone).isoformat()
    return data


def list_certificates(path, actor, query):
    db = connect(path)
    try:
        db.execute('BEGIN')
        where, params, order = query_sql(actor,query)
        total = db.execute('SELECT count(*) FROM (' + SELECT + where + ')', params).fetchone()[0]
        rows = db.execute(SELECT + where + order + ' LIMIT ? OFFSET ?',(*params,query.page_size,(query.page-1)*query.page_size)).fetchall()
        return {'items':[certificate_dict(r,actor) for r in rows], 'total':total,'page':query.page,'page_size':query.page_size}
    finally:
        db.close()


def detail(path, actor, certificate_id):
    db = connect(path)
    try:
        db.execute('BEGIN')
        row = db.execute(SELECT + ' WHERE c.tenant_id=? AND c.id=?',(actor.tenant_id,certificate_id)).fetchone()
        if not row:
            raise DomainError(404,'NOT_FOUND','Certificate not found.')
        result = certificate_dict(row,actor)
        result['audit_events'] = [dict(r) for r in db.execute('SELECT e.id,e.event_type,a.email AS actor_email,e.created_at FROM audit_events e JOIN actors a ON a.id=e.actor_id AND a.tenant_id=e.tenant_id WHERE e.tenant_id=? AND e.certificate_id=? ORDER BY e.id',(actor.tenant_id,certificate_id))]
        return result
    finally:
        db.close()


class IssuanceRejected(Exception):
    """An explicitly classified learner-local rejection."""


def create_certificate(db, actor, course_id, learner_id, stamp):
    import uuid
    serial = 'CERT-' + uuid.uuid4().hex.upper()
    row = db.execute('INSERT INTO certificates(tenant_id,course_id,learner_id,serial_number,issued_at,issue_date_local,status) VALUES(?,?,?,?,?,?,?)', (actor.tenant_id,course_id,learner_id,serial,stamp,local_time(stamp,actor.timezone).date().isoformat(),'ACTIVE'))
    return row.lastrowid


def issue_course(path, actor, course_id, key, clock=None):
    import hashlib
    import json
    import uuid
    from .database import utc_now
    fingerprint = hashlib.sha256(json.dumps({'version':1,'course_id':course_id},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    db = connect(path)
    try:
        if not db.execute('SELECT 1 FROM courses WHERE tenant_id=? AND id=?',(actor.tenant_id,course_id)).fetchone():
            raise DomainError(404,'NOT_FOUND','Course not found.')
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM courses WHERE tenant_id=? AND id=?',(actor.tenant_id,course_id)).fetchone():
            raise DomainError(404,'NOT_FOUND','Course not found.')
        old = db.execute('SELECT fingerprint,result_json FROM issuance_operations WHERE tenant_id=? AND actor_id=? AND idempotency_key=?',(actor.tenant_id,actor.id,key)).fetchone()
        if old:
            if old['fingerprint'] != fingerprint:
                raise DomainError(409,'IDEMPOTENCY_CONFLICT','This key was already used for a different request.')
            db.commit()
            return json.loads(old['result_json'])
        stamp = (clock or utc_now)()
        rows = db.execute('SELECT e.learner_id,e.completed,l.name,c.id AS certificate_id FROM enrollments e JOIN learners l ON l.tenant_id=e.tenant_id AND l.id=e.learner_id LEFT JOIN certificates c ON c.tenant_id=e.tenant_id AND c.course_id=e.course_id AND c.learner_id=e.learner_id WHERE e.tenant_id=? AND e.course_id=? ORDER BY e.learner_id',(actor.tenant_id,course_id)).fetchall()
        result = {'operation_id':str(uuid.uuid4()),'course_id':course_id,'status':'COMPLETED','summary':{'issued':0,'skipped':0,'failed':0},'outcomes':[]}
        for row in rows:
            item = {'learner_id':row['learner_id'],'learner_name':row['name'],'outcome':'skipped','reason':None,'certificate_id':None}
            if not row['completed']:
                item['reason'] = 'INCOMPLETE'
            elif row['certificate_id']:
                item['reason'] = 'ALREADY_CERTIFIED'
                item['certificate_id'] = row['certificate_id']
            else:
                db.execute('SAVEPOINT learner')
                try:
                    cid = create_certificate(db,actor,course_id,row['learner_id'],stamp)
                except IssuanceRejected:
                    db.execute('ROLLBACK TO learner')
                    db.execute('RELEASE learner')
                    item.update(outcome='failed',reason='ISSUANCE_REJECTED')
                else:
                    # Audit errors deliberately escape: the entire operation must roll back.
                    db.execute('INSERT INTO audit_events(tenant_id,certificate_id,actor_id,event_type,created_at) VALUES(?,?,?,?,?)',(actor.tenant_id,cid,actor.id,'ISSUED',stamp))
                    db.execute('RELEASE learner')
                    item.update(outcome='issued',certificate_id=cid)
            result['outcomes'].append(item)
            result['summary'][item['outcome']] += 1
        db.execute('INSERT INTO issuance_operations VALUES(?,?,?,?,?,?,?)',(result['operation_id'],actor.tenant_id,actor.id,key,fingerprint,json.dumps(result),stamp))
        db.commit()
        return result
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def revoke(path, actor, certificate_id, clock=None):
    from .database import utc_now
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT status FROM certificates WHERE tenant_id=? AND id=?',(actor.tenant_id,certificate_id)).fetchone()
        if not row:
            raise DomainError(404,'NOT_FOUND','Certificate not found.')
        if row['status'] == 'ACTIVE':
            stamp = (clock or utc_now)()
            db.execute("UPDATE certificates SET status='REVOKED',revoked_at=? WHERE tenant_id=? AND id=?",(stamp,actor.tenant_id,certificate_id))
            db.execute('INSERT INTO audit_events(tenant_id,certificate_id,actor_id,event_type,created_at) VALUES(?,?,?,?,?)',(actor.tenant_id,certificate_id,actor.id,'REVOKED',stamp))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
    return detail(path,actor,certificate_id)


def spreadsheet_cell(value):
    """Keep untrusted text from being interpreted as a spreadsheet formula."""
    if isinstance(value, str) and (value.startswith(('\t','\r','\n')) or value.lstrip().startswith(('=','+','-','@'))):
        return "'" + value
    return value


class CsvExport:
    """Owns one sequentially consumed snapshot across handler and stream threads."""
    def __init__(self,path,actor,query):
        self.db = connect(path)
        self.closed = False
        try:
            self.db.execute('BEGIN')
            where,params,order = query_sql(actor,query)
            self.cursor = self.db.execute(SELECT + where + order, params)
            self.first = self.cursor.fetchmany(1000)
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.closed=True
            self.db.close()

    def chunks(self):
        import csv
        import io
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        fields = ['learner_name','course_title','serial_number','issue_date_local']
        try:
            writer.writerow(fields)
            yield output.getvalue().encode('utf-8')
            batch = self.first
            while batch:
                output.seek(0)
                output.truncate(0)
                writer.writerows([[spreadsheet_cell(row[field]) for field in fields] for row in batch])
                yield output.getvalue().encode('utf-8')
                batch=self.cursor.fetchmany(1000)
        finally:
            self.close()
