export interface Actor { id: number; email: string; demo_token: string; tenant_name: string; timezone: string }
export interface Certificate { id: number; serial_number: string; learner_name: string; course_title: string; issue_date_local: string; issued_at_local: string; status: 'ACTIVE'|'REVOKED'; revoked_at: string|null; audit_events?: {id:number;event_type:string;actor_email:string;created_at:string}[] }
export interface Course { id:number; title:string; completed_count:number; incomplete_count:number }
export interface Outcome { learner_id:number; learner_name:string; outcome:string; reason:string|null; certificate_id:number|null }
export interface Operation { operation_id:string; summary:{issued:number;skipped:number;failed:number}; outcomes:Outcome[] }
export class ApiError extends Error { constructor(message:string, public status:number) { super(message) } }
export async function request<T>(path:string, actor?:Actor, init:RequestInit={}):Promise<T> {
  const response=await fetch('/api'+path,{...init,headers:{...(actor?{Authorization:`Bearer ${actor.demo_token}`} : {}),...init.headers}});
  if(!response.ok) { const body=await response.json().catch(()=>null); throw new ApiError(body?.error?.message || `Request failed (${response.status})`,response.status) }
  return response.json();
}
export function queryString(query:Record<string,string|number>) { return new URLSearchParams(Object.entries(query).map(([key,value])=>[key,String(value)])).toString() }
