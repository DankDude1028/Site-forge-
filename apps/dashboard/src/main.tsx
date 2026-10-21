import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { dollars, readable, rows } from './format.mjs';
import './style.css';

type Row = Record<string, unknown>;
type Resource = 'overview'|'tasks'|'workers'|'approvals'|'models'|'audit';
const nav: [Resource,string,string][] = [['overview','◈','Portfolio'],['tasks','≋','Agents & jobs'],['workers','⌁','Windows workers'],['models','▥','Model laboratory'],['approvals','◇','Approvals'],['audit','☷','Audit trail']];
const endpoints = ['sites','tasks','workers','approvals','budgets','metrics','audit','models','benchmark-runs'] as const;
function App() {
  const [token,setToken] = useState(''); const [draft,setDraft] = useState('');
  const [view,setView] = useState<Resource>('overview'); const [data,setData] = useState<Record<string,Row[]>>({});
  const [error,setError] = useState(''); const [busy,setBusy] = useState(false); const [updated,setUpdated] = useState('');
  const [selected,setSelected] = useState<Row|null>(null); const [message,setMessage] = useState('');
  const [paused,setPaused] = useState(false); const sessionVersion=useRef(0);
  const request = useCallback(async (path:string, body?:unknown) => {
    const result = await fetch(`/v1/${path}`, {method:body === undefined ? 'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
    if(!result.ok) throw new Error(`${path}: ${result.status} ${await result.text()}`);
    return result.status===204 ? null:result.json();
  },[token]);
  const refresh = useCallback(async () => {
    if(!token) return; setBusy(true);
    const version=sessionVersion.current;
    const responses = await Promise.allSettled(endpoints.map(p=>request(p)));
    const next:Record<string,Row[]> = {}; const errors:string[]=[];
    responses.forEach((r,i)=>{if(r.status==='fulfilled')next[endpoints[i]]=rows(r.value);else errors.push(String(r.reason));});
    const economics = await Promise.allSettled((next.sites??[]).map(site=>request(`sites/${site.id}/economics`)));
    next.economics=economics.filter((x):x is PromiseFulfilledResult<Row>=>x.status==='fulfilled').map(x=>x.value);
    if(economics.some(x=>x.status==='rejected')) errors.push('Some site economics could not load');
    const kill=await request('kill-switch').catch(()=>null);
    if(version!==sessionVersion.current) return;
    if(kill&&typeof kill.enabled==='boolean') setPaused(kill.enabled);
    setData(next);setError(errors.join(' · '));setUpdated(new Date().toLocaleTimeString());setBusy(false);
  },[token,request]);
  useEffect(()=>{void refresh();const id=setInterval(()=>void refresh(),15000);return()=>clearInterval(id);},[refresh]);
  useEffect(()=>{
    if(!selected)return;
    const previous=document.activeElement as HTMLElement|null;
    const dialog=document.querySelector('.modal') as HTMLElement|null;
    const buttons=dialog?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
    buttons?.[0]?.focus();
    const keydown=(event:KeyboardEvent)=>{
      if(event.key==='Escape')setSelected(null);
      if(event.key==='Tab'&&buttons?.length){
        const first=buttons[0],last=buttons[buttons.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
        if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
      }
    };
    document.addEventListener('keydown',keydown);
    return()=>{document.removeEventListener('keydown',keydown);previous?.focus();};
  },[selected]);
  async function togglePause(){try{await request('kill-switch',{enabled:!paused});setPaused(!paused);setMessage(paused?'Dispatch resumed.':'Dispatch paused. Read-only inspection remains available.');}catch(e){setMessage(String(e));}}
  async function decide(approve:boolean) {
    if(!selected) return;
    try { await request(`approvals/${selected.id}/${approve?'approve':'reject'}`,{reason:approve?'Owner reviewed the immutable action in the dashboard':'Owner rejected the action'});setSelected(null);setMessage(approve?'Approval recorded for this exact action.':'Action rejected.');await refresh(); }
    catch(e){setMessage(String(e));}
  }
  const tasks=data.tasks??[];const sites=data.sites??[];const workers=data.workers??[];const approvals=data.approvals??[];
  const revenueRows=(data.economics??[]).filter(x=>x.verified_revenue!==null&&x.verified_revenue!==undefined);
  const costRows=(data.economics??[]).filter(x=>x.verified_expenses!==null&&x.verified_expenses!==undefined);
  const actualRevenue=revenueRows.length?dollars(revenueRows.reduce((s,x)=>s+Number(x.verified_revenue),0)):'—';
  const spent=costRows.length?dollars(costRows.reduce((s,x)=>s+Number(x.verified_expenses),0)):'—';
  if(!token) return <main className="login"><div className="brand">◈ <b>SITEFORGE</b></div><p className="eyebrow">OWNER CONTROL ROOM</p><h1>A small portfolio.<br/>A clear view.</h1><p>Connect to your supervisor to review work, evidence, and decisions.</p><form onSubmit={e=>{e.preventDefault();sessionVersion.current++;setToken(draft);setDraft('');}}><label htmlFor="token">Supervisor access token</label><input id="token" type="password" value={draft} onChange={e=>setDraft(e.target.value)} required autoComplete="off"/><button>Open control room <span>↗</span></button></form><small>Your token stays in memory for this session.</small></main>;
  return <div className="shell"><aside><a href="#main" className="skip">Skip to content</a><div className="brand"><span>◈</span> <b>SITEFORGE</b></div><p className="workspace">90-DAY PILOT / WORKSPACE 01</p><nav aria-label="Main navigation">{nav.map(([key,icon,label])=><button key={key} className={view===key?'active':''} onClick={()=>setView(key)} aria-current={view===key?'page':undefined}><span>{icon}</span>{label}{key==='approvals'&&approvals.filter(x=>x.status==='pending').length>0&&<i>{approvals.filter(x=>x.status==='pending').length}</i>}</button>)}</nav><div className="guard"><span className="dot"/> OWNER GATED<p>External spend starts at $0. Production release requires approval.</p></div><button className="logout" onClick={()=>{sessionVersion.current++;setToken('');setData({});setSelected(null);setMessage('');setError('');}}>End session ↗</button></aside><main id="main"><header><span>PORTFOLIO OPERATIONS</span><div className="connection"><button onClick={()=>void togglePause()}>{paused?'Resume dispatch':'Pause dispatch'}</button> <span className="dot"/> {updated?`Synced ${updated}`:'Connecting'} <button onClick={()=>void refresh()} disabled={busy} aria-label="Refresh data">↻</button></div></header><section className="heading"><div><p className="eyebrow">BUILD WITH PURPOSE. MEASURE WHAT MATTERS.</p><h1>{nav.find(x=>x[0]===view)?.[2]}</h1><p>{view==='overview'?'One useful site first. Expand when the evidence supports it.':'Recorded state from your authenticated supervisor.'}</p></div><span className="badge">PILOT · STAGING</span></section>{error&&<div role="alert" className="notice">Some resources could not load: {error}</div>}{message&&<div role="status" className="notice">{message}</div>}
  {view==='overview'?<><section className="stats"><Stat title="Portfolio sites" value={String(sites.length)} detail="Registered sites"/><Stat title="Verified revenue" value={actualRevenue} detail={revenueRows.length?"Verified imports / partial coverage":"Awaiting provider imports"}/><Stat title="Recorded costs" value={spent} detail={costRows.length?"Verified expenses / USD":"Awaiting expense imports"}/><Stat title="Awaiting decision" value={String(approvals.filter(x=>x.status==='pending').length)} detail="Owner approvals"/></section><div className="split"><section className="panel"><div className="panelhead"><h2>Your portfolio</h2><span>{sites.length} SITES</span></div>{sites.length?<Table items={sites} columns={['slug','status','created_at']}/>:<Empty icon="◈" title="The first site starts with evidence." text="Evaluate a candidate, review its original value, and build a protected preview."/>}</section><section className="panel"><div className="panelhead"><h2>Local capacity</h2><span>{workers.length} WORKERS</span></div>{workers.length?workers.map(w=><article className="worker" key={String(w.id)}><span className="workericon">⌁</span><div><b>{String(w.name)}</b><p>{readable(w.status)} · Last heartbeat {String(w.last_heartbeat_at??'pending')}</p></div></article>):<Empty icon="⌁" title="Waiting for the Windows worker" text="Queued tasks stay durable when the local PC is offline."/>}<div className="footnote">LM Studio stays on localhost. GPU jobs run one at a time.</div></section></div><section className="panel"><div className="panelhead"><h2>Work in motion</h2><button onClick={()=>setView('tasks')}>View all jobs ↗</button></div><Table items={tasks.slice(0,6)} columns={['agent_type','status','attempt','capability']}/></section></>:null}
  {view==='tasks'&&<section className="panel"><div className="panelhead"><h2>Durable task queue</h2><span>{tasks.length} TASKS</span></div><Table items={tasks} columns={['id','agent_type','status','attempt','capability','error_code']}/></section>}
  {view==='workers'&&<section className="panel"><Table items={workers} columns={['name','status','last_heartbeat_at','version']}/></section>}
  {view==='models'&&<section className="panel"><div className="panelhead"><h2>Measured model evidence</h2><span>LOCAL HARDWARE</span></div><p className="footnote">Routing remains pending until a role has sufficient measured task coverage. The complete benchmark report is in benchmarks/results/model_comparison.html.</p><Table items={(data['benchmark-runs']??[]).map(x=>({...x,source_model:(x.config as Row)?.source_model,quantization:(x.config as Row)?.quantization,context:(x.config as Row)?.context,passed:((x.config as Row)?.summary as Row)?.passed,tasks:((x.config as Row)?.summary as Row)?.tasks}))} columns={['source_model','quantization','context','status','passed','tasks']}/></section>}
  {view==='approvals'&&<section className="panel"><div className="panelhead"><h2>Owner decisions</h2><span>EXACT ACTION BINDING</span></div>{approvals.length?approvals.map(a=><article className="approval" key={String(a.id)}><div><h3>{readable(a.action??a.action_type)}</h3><p>{String(a.site_id)} · {String(a.currency??'USD')} {String(a.amount??0)}</p><span className="status">{readable(a.status)}</span></div><button onClick={()=>setSelected(a)}>Review details ↗</button></article>):<Empty icon="◇" title="No approvals to review" text="Spending, production publication, and sensitive actions require an exact owner decision."/>}</section>}
  {view==='audit'&&<section className="panel"><div className="panelhead"><h2>Immutable event history</h2></div><Table items={data.audit??[]} columns={['created_at','action','actor_id','outcome','target_id']}/></section>}
  <footer>SiteForge / Hybrid portfolio supervisor <span>Measured facts. Bounded autonomy.</span></footer></main>{selected&&<div className="modalshade"><section role="dialog" aria-modal="true" aria-labelledby="review-title" className="modal"><h2 id="review-title">Review exact action</h2><pre>{JSON.stringify(selected,null,2)}</pre><div className="actions"><button onClick={()=>setSelected(null)}>Close</button><button onClick={()=>void decide(false)}>Reject</button><button disabled={selected.status!=='pending'} onClick={()=>void decide(true)}>Approve exact action</button></div></section></div>}</div>;
}
function Stat({title,value,detail}:{title:string,value:string,detail:string}){return <article className="stat"><span>{title}</span><strong>{value}</strong><small>{detail}</small></article>;}
function Empty({icon,title,text}:{icon:string,title:string,text:string}){return <div className="empty"><span>{icon}</span><h3>{title}</h3><p>{text}</p></div>;}
function Table({items,columns}:{items:Row[],columns:string[]}){return items.length?<div className="tablewrap"><table><thead><tr>{columns.map(c=><th key={c}>{readable(c)}</th>)}</tr></thead><tbody>{items.map((item,i)=><tr key={String(item.id??i)}>{columns.map(c=><td key={c}>{c==='status'?<span className={`status ${item[c]}`}>{readable(item[c])}</span>:<span title={String(item[c]??'')}>{readable(item[c])}</span>}</td>)}</tr>)}</tbody></table></div>:<Empty icon="≋" title="Nothing recorded yet" text="As tasks run, their durable state and evidence appear here."/>;}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
