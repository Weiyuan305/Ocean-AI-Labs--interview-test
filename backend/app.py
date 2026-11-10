import os
import sqlite3
from pathlib import Path
from typing import Annotated, Literal
from fastapi import FastAPI, Request, Depends, Query, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, ConfigDict, Field
from .database import connect, initialize
from . import certificates as service


class ExportQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    q: str = Field(default='', max_length=200)
    sort: Literal['learner_name','course_title','serial_number','issue_date','status'] = 'issue_date'
    order: Literal['asc','desc'] = 'desc'


class ListQuery(ExportQuery):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class IssueRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    course_id: int = Field(strict=True, gt=0)


def create_app(db_path=None):
    path = str(db_path or os.environ.get('DB_PATH','data/demo.sqlite3'))
    initialize(path)
    app = FastAPI(title='Certificate Admin Console')
    app.state.db_path = path

    @app.middleware('http')
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(service.DomainError)
    async def domain_error(request, exc):
        return JSONResponse({'error':{'code':exc.code,'message':exc.message}},status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({'error':{'code':'INVALID_REQUEST','message':'Invalid request parameters or body.'}},status_code=422)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        locked = 'locked' in str(exc).lower() or 'busy' in str(exc).lower()
        return JSONResponse({'error':{'code':'DATABASE_BUSY' if locked else 'INTERNAL_ERROR','message':'Please retry with the same operation key.' if locked else 'The operation could not be completed.'}},status_code=503 if locked else 500,headers={'Retry-After':'1'} if locked else {})

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return JSONResponse({'error':{'code':'INTERNAL_ERROR','message':'The operation could not be completed.'}},status_code=500,headers={'Cache-Control':'no-store'})

    def actor(request: Request):
        return service.actor_for(path,request.headers.get('Authorization'))

    def no_query(request: Request):
        if request.query_params:
            raise service.DomainError(422,'INVALID_REQUEST','This endpoint does not accept query parameters.')

    @app.get('/api/demo-actors', dependencies=[Depends(no_query)])
    def demo_actors():
        db = connect(path)
        try:
            return {'items':[dict(r) for r in db.execute('SELECT a.id,a.email,a.token AS demo_token,t.name AS tenant_name,t.timezone FROM actors a JOIN tenants t ON t.id=a.tenant_id ORDER BY a.id')]}
        finally:
            db.close()

    @app.get('/api/courses', dependencies=[Depends(no_query)])
    def courses(current=Depends(actor)):
        db = connect(path)
        try:
            return {'items':[dict(r) for r in db.execute('SELECT c.id,c.title,COALESCE(SUM(e.completed=1),0) AS completed_count,COALESCE(SUM(e.completed=0),0) AS incomplete_count FROM courses c LEFT JOIN enrollments e ON e.tenant_id=c.tenant_id AND e.course_id=c.id WHERE c.tenant_id=? GROUP BY c.id ORDER BY c.id',(current.tenant_id,))]}
        finally:
            db.close()

    @app.get('/api/certificates')
    def certificates(query: Annotated[ListQuery,Query()], current=Depends(actor)):
        return service.list_certificates(path,current,query)

    @app.get('/api/certificates/export.csv')
    def export(query: Annotated[ExportQuery,Query()], current=Depends(actor)):
        stream = service.CsvExport(path,current,query)
        return StreamingResponse(stream.chunks(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="certificates.csv"'},background=BackgroundTask(stream.close))

    @app.get('/api/certificates/{certificate_id}',  dependencies=[Depends(no_query)])
    def certificate_detail(certificate_id: int, current=Depends(actor)):
        return service.detail(path,current,certificate_id)

    @app.post('/api/certificate-issuances', dependencies=[Depends(no_query)])
    def issue(body: IssueRequest, idempotency_key: Annotated[str, Header(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_.-]+$')], current=Depends(actor)):
        return service.issue_course(path,current,body.course_id,idempotency_key)

    @app.post('/api/certificates/{certificate_id}/revoke', dependencies=[Depends(no_query)])
    async def revoke(certificate_id: int, request: Request, current=Depends(actor)):
        if await request.body():
            raise service.DomainError(422,'INVALID_REQUEST','Revocation does not accept a body.')
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(service.revoke,path,current,certificate_id)

    dist=Path(__file__).resolve().parent.parent/'frontend'/'dist'
    if dist.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount('/',StaticFiles(directory=dist,html=True),name='console')
    return app
