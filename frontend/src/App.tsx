import {useEffect,useRef,useState} from 'react';
import {Alert,Button,Descriptions,Drawer,Empty,Input,Modal,Select,Space,Spin,Table,Tag,Typography} from 'antd';
import type {ColumnsType} from 'antd/es/table';
import {Actor,ApiError,Certificate,Course,Operation,Outcome,queryString,request} from './api';
const {Title,Text}=Typography;
const errorText=(error:unknown)=>error instanceof Error?error.message:'The request failed. Please try again.';
const statusTag=(status:string)=><Tag color={status==='ACTIVE'||status==='issued'?'green':status==='failed'?'red':'default'}>{status}</Tag>;

export default function App(){
  const [actors,setActors]=useState<Actor[]>([]),[actorId,setActorId]=useState<number>(),[error,setError]=useState(''),[reload,setReload]=useState(0);
  useEffect(()=>{const abort=new AbortController();request<{items:Actor[]}>('/demo-actors',undefined,{signal:abort.signal}).then(data=>{setActors(data.items);setActorId(data.items[0]?.id);setError('')}).catch(e=>{if(!abort.signal.aborted)setError(errorText(e))});return()=>abort.abort()},[reload]);
  const actor=actors.find(a=>a.id===actorId);
  return <div className="app"><header className="topbar"><div className="brand"><span className="brand-mark">O</span><span>Ocean AI Labs<span className="brand-sub">Learning operations</span></span></div><Space wrap><Text>Administrator</Text><Select aria-label="Administrator" style={{minWidth:230}} value={actorId} onChange={setActorId} options={actors.map(a=>({value:a.id,label:a.email}))}/></Space></header>
    <main>{error&&<Alert type="error" message={error} action={<Button onClick={()=>setReload(x=>x+1)}>Retry</Button>}/>}{actor?<Console key={actor.id} actor={actor}/>:!error&&<Spin/>}</main><footer>Certificate administration · Local demonstration</footer></div>
}

function Console({actor}:{actor:Actor}){
  const [data,setData]=useState<Certificate[]>([]),[total,setTotal]=useState(0),[courses,setCourses]=useState<Course[]>([]),[course,setCourse]=useState<number>();
  const [query,setQuery]=useState({q:'',sort:'issue_date',order:'desc',page:1,page_size:20});
  const [refresh,setRefresh]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState(''),[courseError,setCourseError]=useState('');
  const [busy,setBusy]=useState(false),[operation,setOperation]=useState<Operation>(),[operationError,setOperationError]=useState(''),[retry,setRetry]=useState(false);
  const [detailId,setDetailId]=useState<number>(),[detail,setDetail]=useState<Certificate>(),[detailError,setDetailError]=useState(''),[revoking,setRevoking]=useState(false),[exporting,setExporting]=useState(false);
  const pending=useRef<{key:string;course:number}|null>(null),locked=useRef(false),alive=useRef(true);
  const [modal,modalContext]=Modal.useModal();
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;Modal.destroyAll()}},[]);
  useEffect(()=>{const abort=new AbortController();request<{items:Course[]}>('/courses',actor,{signal:abort.signal}).then(r=>{setCourses(r.items);setCourseError('')}).catch(e=>{if(!abort.signal.aborted)setCourseError(errorText(e))});return()=>abort.abort()},[actor,refresh]);
  useEffect(()=>{const abort=new AbortController();setLoading(true);setError('');request<{items:Certificate[];total:number}>('/certificates?'+queryString(query),actor,{signal:abort.signal}).then(r=>{setData(r.items);setTotal(r.total)}).catch(e=>{if(!abort.signal.aborted){setData([]);setTotal(0);setError(errorText(e))}}).finally(()=>{if(!abort.signal.aborted)setLoading(false)});return()=>abort.abort()},[actor,query,refresh]);
  useEffect(()=>{setDetail(undefined);setDetailError('');if(detailId===undefined)return;const abort=new AbortController();request<Certificate>(`/certificates/${detailId}`,actor,{signal:abort.signal}).then(setDetail).catch(e=>{if(!abort.signal.aborted)setDetailError(errorText(e))});return()=>abort.abort()},[actor,detailId,refresh]);
  async function issue(){
    if(course===undefined||locked.current)return;locked.current=true;setBusy(true);setOperationError('');setOperation(undefined);
    const work=pending.current??{key:crypto.randomUUID(),course};pending.current=work;
    try{const result=await request<Operation>('/certificate-issuances',actor,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':work.key},body:JSON.stringify({course_id:work.course})});if(alive.current){setOperation(result);pending.current=null;setRetry(false);setRefresh(x=>x+1)}}
    catch(e){if(alive.current){setOperationError(errorText(e));const uncertain=!(e instanceof ApiError)||e.status>=500;setRetry(uncertain);if(!uncertain)pending.current=null}}
    finally{locked.current=false;if(alive.current)setBusy(false)}
  }
  async function revoke(){
    if(!detail||revoking)return;setRevoking(true);setDetailError('');try{const updated=await request<Certificate>(`/certificates/${detail.id}/revoke`,actor,{method:'POST'});if(alive.current){setDetail(updated);setRefresh(x=>x+1)}}catch(e){if(alive.current)setDetailError(errorText(e))}finally{if(alive.current)setRevoking(false)}
  }
  async function exportCsv(){
    setExporting(true);setError('');const {q,sort,order}=query;
    try{const response=await fetch('/api/certificates/export.csv?'+queryString({q,sort,order}),{headers:{Authorization:`Bearer ${actor.demo_token}`}});if(!response.ok){const body=await response.json();throw new Error(body.error?.message||'Export failed.')};const blob=await response.blob();if(!alive.current)return;const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`${actor.tenant_name.toLowerCase()}-certificates.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){if(alive.current)setError(errorText(e))}finally{if(alive.current)setExporting(false)}
  }
  const sorted=(field:string)=>query.sort===field?(query.order==='asc'?'ascend' as const:'descend' as const):null;
  const columns:ColumnsType<Certificate>=[
    {title:'Learner',dataIndex:'learner_name',key:'learner_name',sorter:true,sortOrder:sorted('learner_name'),render:value=><Text strong>{value}</Text>},
    {title:'Course',dataIndex:'course_title',key:'course_title',sorter:true,sortOrder:sorted('course_title')},
    {title:'Serial number',dataIndex:'serial_number',key:'serial_number',sorter:true,sortOrder:sorted('serial_number'),render:value=><span className="serial">{value}</span>},
    {title:'Issue date',dataIndex:'issue_date_local',key:'issue_date',sorter:true,sortOrder:sorted('issue_date')},
    {title:'Status',dataIndex:'status',key:'status',sorter:true,sortOrder:sorted('status'),render:statusTag},
    {title:'',key:'action',render:(_,row)=><Button type="link" onClick={()=>setDetailId(row.id)} aria-label={`View ${row.serial_number}`}>View details</Button>}
  ];
  const outcomeColumns:ColumnsType<Outcome>=[{title:'Learner',dataIndex:'learner_name'},{title:'Outcome',dataIndex:'outcome',render:statusTag},{title:'Reason',dataIndex:'reason',render:value=>value?value.replaceAll('_',' ').toLowerCase():'Certificate issued'}];
  return <>{modalContext}<section className="page-heading"><div><Title level={1}>Certificates</Title><p>Review completions, issue certificates, and keep a clear audit trail.</p></div><div className="tenant-label"><strong>{actor.tenant_name} tenant</strong><span>{actor.timezone}</span></div></section>
  <section className="issue-panel"><div><Title level={4}>Issue course certificates</Title><Text type="secondary">Completed learners receive one certificate. Incomplete or certified learners are skipped.</Text></div><div className="issue-controls"><Select aria-label="Course" placeholder="Choose a course" value={course} disabled={busy||retry} onChange={setCourse} options={courses.map(c=>({value:c.id,label:`${c.title} · ${c.completed_count} completed / ${c.incomplete_count} incomplete`}))}/><Button type="primary" disabled={course===undefined} loading={busy} onClick={issue}>{retry?'Retry same operation':'Issue certificates'}</Button></div>{courseError&&<Alert type="error" message={courseError} action={<Button onClick={()=>setRefresh(x=>x+1)}>Retry courses</Button>}/>}</section>
  {operationError&&<Alert className="feedback" type="error" showIcon message={operationError} description={retry?'The outcome is uncertain. Retry uses the same key to prevent duplicate issuance.':undefined}/>}
  {operation&&<section className="operation-result"><Alert type={operation.summary.failed?'warning':'success'} showIcon message={`Operation completed: ${operation.summary.issued} issued, ${operation.summary.skipped} skipped, ${operation.summary.failed} failed.`}/><Table size="small" rowKey="learner_id" dataSource={operation.outcomes} columns={outcomeColumns} pagination={operation.outcomes.length>10?{pageSize:10}:false}/><Text type="secondary" className="operation-id">Operation {operation.operation_id}</Text></section>}
  <section className="records"><div className="table-toolbar"><div><Title level={4}>Certificate records</Title><Text type="secondary">{total} matching records · Dates shown in tenant time zone</Text></div><Space wrap><Input.Search aria-label="Search certificates" placeholder="Search learner or serial number" allowClear onSearch={q=>setQuery(x=>({...x,q,page:1}))} style={{width:290}}/><Button onClick={exportCsv} loading={exporting}>Export CSV</Button></Space></div>
  {error&&<Alert type="error" message={error} action={<Button onClick={()=>setRefresh(x=>x+1)}>Retry</Button>}/>}
  <Table<Certificate> rowKey="id" loading={loading} columns={columns} dataSource={data} scroll={{x:950}} locale={{emptyText:<Empty description="No certificates match your search."/>}} pagination={{current:query.page,pageSize:query.page_size,total,showSizeChanger:true,pageSizeOptions:[10,20,50,100],showTotal:n=>`${n} certificates`}} onChange={(pagination,_,sorter)=>{const selected=Array.isArray(sorter)?sorter[0]:sorter;const sort=selected.order?String(selected.columnKey):'issue_date';const order=selected.order==='ascend'?'asc':'desc';setQuery(x=>({...x,page:sort!==x.sort||order!==x.order?1:pagination.current||1,page_size:pagination.pageSize||20,sort,order}))}}/>
  </section><Drawer title="Certificate details" open={detailId!==undefined} onClose={()=>setDetailId(undefined)} width={520}>
    {detailError&&<Alert type="error" message={detailError} action={<Button onClick={()=>setRefresh(x=>x+1)}>Retry detail</Button>}/>}{!detail&&!detailError&&<Spin/>}{detail&&<><Descriptions column={1} bordered items={[{key:'learner',label:'Learner',children:detail.learner_name},{key:'course',label:'Course',children:detail.course_title},{key:'serial',label:'Serial number',children:<span className="serial">{detail.serial_number}</span>},{key:'issued',label:'Issued locally',children:<>{detail.issued_at_local.slice(0,16).replace('T',' ')}<br/><Text type="secondary">{actor.timezone}</Text></>},{key:'status',label:'Status',children:statusTag(detail.status)}]}/><div className="detail-actions"><Button danger disabled={detail.status==='REVOKED'} loading={revoking} onClick={()=>modal.confirm({title:'Revoke this certificate?',content:'This action is permanent. The certificate and its audit history will be retained.',okText:'Revoke certificate',okButtonProps:{danger:true},cancelText:'Cancel',onOk:revoke})}>{detail.status==='REVOKED'?'Certificate revoked':'Revoke certificate'}</Button></div><Title level={4}>Audit history</Title>{detail.audit_events?.map(event=><div className="audit-event" key={event.id}><strong>{event.event_type}</strong><span>{event.actor_email}</span><Text type="secondary">{event.created_at}</Text></div>)}</>}
  </Drawer></>
}
