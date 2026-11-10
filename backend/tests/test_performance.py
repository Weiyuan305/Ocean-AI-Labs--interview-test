"""Real HTTP A6 proof, including overlapping requests and full body timing."""
import csv
import io
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from backend.seed_large import generate


def test_a6_real_http(tmp_path):
    path=tmp_path/'performance.sqlite3'
    generate(str(path))
    generate(str(path))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:create_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','error'],env={**os.environ,'DB_PATH':str(path)},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    base=f'http://127.0.0.1:{port}'
    headers={'Authorization':'Bearer east-demo-token'}
    try:
        for _ in range(100):
            try:
                if httpx.get(base+'/api/demo-actors',timeout=1).status_code==200:
                    break
            except httpx.TransportError:
                time.sleep(.05)
        else:
            raise AssertionError('Server failed to start: '+process.stderr.read().decode() if process.poll() is not None else 'Server startup timed out')
        started=threading.Event()
        proceed=threading.Event()
        def download(overlap=False,query='Export Fixture'):
            begin=time.perf_counter()
            chunks=[]
            with httpx.stream('GET',base+'/api/certificates/export.csv',params={'q':query,'sort':'learner_name','order':'asc'},headers=headers,timeout=60) as response:
                assert response.status_code==200
                for chunk in response.iter_bytes():
                    chunks.append(chunk)
                    if overlap and not started.is_set():
                        started.set()
                        assert proceed.wait(10)
            elapsed=time.perf_counter()-begin
            assert elapsed<=60
            return b''.join(chunks).decode(),elapsed
        with ThreadPoolExecutor(1) as pool:
            pending=pool.submit(download,True)
            assert started.wait(10)
            assert not pending.done()
            list_start=time.perf_counter()
            listed=httpx.get(base+'/api/certificates',headers=headers,timeout=10)
            list_elapsed=time.perf_counter()-list_start
            assert listed.status_code==200 and listed.json()['total']==100003
            proceed.set()
            first,t1=pending.result(timeout=60)
        second,t2=download()
        assert first==second
        rows=list(csv.DictReader(io.StringIO(first)))
        assert len(rows)==100000
        expected=[f'PERF-{i:06}' for group in range(100) for i in range(group,100000,100)]
        assert [r['serial_number'] for r in rows]==expected
        assert {r['issue_date_local'] for r in rows}=={'2026-01-11'}
        selected,_=download(query='Export Fixture 003')
        assert [r['serial_number'] for r in csv.DictReader(io.StringIO(selected))]==[f'PERF-{i:06}' for i in range(3,100000,100)]
        all_rows,_=download(query='')
        assert len(list(csv.DictReader(io.StringIO(all_rows))))==100003
        west=httpx.get(base+'/api/certificates/export.csv',headers={'Authorization':'Bearer west-demo-token'})
        assert len(list(csv.DictReader(io.StringIO(west.text))))==1
        # Disconnect an export early; a subsequent request must still work.
        with httpx.stream('GET',base+'/api/certificates/export.csv',headers=headers) as response:
            next(response.iter_bytes())
        assert httpx.get(base+'/api/certificates',headers=headers).status_code==200
        print('\nA6_MEASUREMENTS '+json.dumps({'rows':len(rows),'first_seconds':round(t1,3),'second_seconds':round(t2,3),'concurrent_list_seconds':round(list_elapsed,3),'python':platform.python_version(),'platform':platform.platform()}))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
