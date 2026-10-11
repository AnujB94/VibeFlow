import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {Tools,Settings} from './Tools';

type Clip={id:string;source:string;in:number;out:number;start:number};
type Media={id:string;name:string;frames:number;url:string;missing:boolean;had_audio:boolean};
type Job={id:string;kind:string;status:string;progress:number;message:string;seconds?:number};
type Chat={id:string;role:string;status:string;text:string;time:number};
type State={provider?:{configured:boolean;model:string;local_speech:boolean};project:{id:string;revision:number;name:string;media:Media[];clips:Clip[];chat:Chat[]};
 duration:number;can_undo:boolean;can_redo:boolean;dirty:boolean;filepath:string|null;pending:string[];
 preview:{url:string;revision:number;project_id:string}|null;job:Job|null};
declare global{interface Window{vibeflow:{call:(method:string,params?:unknown)=>Promise<State>;listen:(callback:(event:{event:string;data:any})=>void)=>()=>void}}}
const seconds=(frames:number)=>(frames/25).toFixed(2);
function App(){
 const [toolTab,setToolTab]=useState(false),[settings,setSettings]=useState(false);
 const [state,setState]=useState<State|null>(null);
 const [error,setError]=useState(''),[waiting,setWaiting]=useState(false);
 const [selected,setSelected]=useState(''),[sourceId,setSourceId]=useState('');
 const [playhead,setPlayhead]=useState(0),[mode,setMode]=useState<'source'|'sequence'>('source');
 const [trimIn,setTrimIn]=useState('0'),[trimOut,setTrimOut]=useState('0'),[ripple,setRipple]=useState(true);
 const [prompt,setPrompt]=useState(''),[playing,setPlaying]=useState(false);
 const video=useRef<HTMLVideoElement>(null),history=useRef<HTMLDivElement>(null);
 const project=state?.project;
 const clip=project?.clips.find(c=>c.id===selected);
 const source=project?.media.find(m=>m.id===sourceId);
 const busy=state?.job?.status==='running';
 const stale=Boolean(state?.preview && (state.preview.revision!==project?.revision||state.preview.project_id!==project?.id));
 const url=mode==='sequence'?state?.preview?.url:source?.url;
 async function act(method:string,params?:unknown){
  setError('');setWaiting(true);
  try{const next=await window.vibeflow.call(method,params);setState(next);return next}
  catch(e){setError(String(e).replace(/^Error: Error invoking remote method 'vibeflow': Error: /,''))}
  finally{setWaiting(false)}
 }
 useEffect(()=>{
  act('state');
  return window.vibeflow.listen(event=>{
   if(event.event==='state')setState(event.data);
   else if(event.event==='job')setState(previous=>previous?{...previous,job:event.data}:previous);
   else if(event.event==='fatal')setError(event.data);
  });
 },[]);
 useEffect(()=>{
  setSelected('');setSourceId('');setPlayhead(0);setMode('source');
 },[project?.id]);
 useEffect(()=>{
  if(clip){setTrimIn(seconds(clip.in));setTrimOut(seconds(clip.out))}
 },[clip?.id,clip?.in,clip?.out]);
 useEffect(()=>{
  if(mode==='source'&&clip&&video.current&&clip.source===sourceId)video.current.currentTime=clip.in/25;
 },[clip?.id,sourceId,mode]);
 useEffect(()=>{history.current?.scrollTo({top:history.current.scrollHeight})},[project?.chat.length,state?.pending.length]);
 useEffect(()=>{
  if(state?.preview&&!stale)setMode('sequence');
 },[state?.preview?.url]);
 useEffect(()=>{
  const handler=(event:KeyboardEvent)=>{
   const tag=(event.target as HTMLElement)?.tagName;
   if(event.ctrlKey&&event.key.toLowerCase()==='s'){event.preventDefault();act('save')}
   else if(event.ctrlKey&&event.key.toLowerCase()==='z'&&!['INPUT','TEXTAREA'].includes(tag)){
    event.preventDefault();act(event.shiftKey?'redo':'undo');
   }
  };window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
 });
 const edit=(operation:Record<string,unknown>)=>act('edit',{operation,revision:project?.revision});
 function select(c:Clip){setSelected(c.id);setSourceId(c.source);setPlayhead(c.start);setMode('source');setPlaying(false)}
 function seek(frame:number){
  const value=Math.max(0,Math.min(state?.duration||0,Math.round(frame)));
  setPlayhead(value);
  if(video.current){
   if(mode==='sequence')video.current.currentTime=value/25;
   else if(clip&&value>=clip.start&&value<clip.start+clip.out-clip.in)
    video.current.currentTime=(clip.in+value-clip.start)/25;
  }
 }
 function syncTime(){
  if(!video.current)return;
  const n=Math.round(video.current.currentTime*25);
  if(mode==='sequence')setPlayhead(Math.min(n,state?.duration||0));
  else if(clip&&clip.source===sourceId&&n>=clip.in&&n<=clip.out)setPlayhead(clip.start+n-clip.in);
 }
 function send(){if(!busy&&!waiting&&prompt.trim()){act('prompt',{text:prompt,selected,playhead});setPrompt('')}}
 if(!state)return <main className="startup"><h1>Vibeflow</h1><p>{error||'Starting the local editor…'}</p><button onClick={()=>act('state')}>Retry connection</button></main>;
 return <div className="app">
  <header className="topbar"><div className="brand">Vibeflow <span>LOCAL EDITOR</span></div>
   <div className="project-name" title={state.filepath||'Not saved to a project file'}>{project!.name}{state.dirty?' ·':''}</div>
   <nav aria-label="Project"><button disabled={busy||waiting} onClick={()=>act('new')}>New</button><button disabled={busy||waiting} onClick={()=>act('open')}>Open</button>
    <button disabled={waiting} onClick={()=>act('save')}>Save</button>
    <button disabled={!state.can_undo||waiting} onClick={()=>act('undo')} title="Ctrl+Z">Undo</button>
    <button disabled={!state.can_redo||waiting} onClick={()=>act('redo')} title="Ctrl+Shift+Z">Redo</button>
    <button onClick={()=>setSettings(true)}>Settings</button><button className="primary" disabled={busy||waiting||!state.duration} onClick={()=>act('export')}>Export 1080p</button></nav>
  </header>
  <div className="workspace">
   <aside className="media-panel"><div className="panel-heading"><h2>Media</h2><span>{project!.media.length} files</span></div>
    <button className="wide" disabled={busy||waiting} onClick={()=>act('import')}>＋ Import video</button>
    <div className="media-list">
     {!project!.media.length&&<div className="empty-media"><p>Start with a video.</p><p className="muted">Landscape SDR, up to 1080p.<br/>Three minutes per source.</p><button disabled={busy} onClick={()=>act('demo')}>Load test clip</button><p className="muted">12 seconds, frame numbers and an audio pulse each second.</p></div>}
     {project!.media.map(m=><div key={m.id} className={'media-item '+(sourceId===m.id?'selected':'')}>
      <button className="media-select" onClick={()=>{setSourceId(m.id);setMode('source');setSelected('')}}><span className="media-mark">▻</span><strong>{m.name}</strong><small>{seconds(m.frames)}s · {m.missing?'Missing media':'25 fps'}</small></button>
      <div className="media-actions"><button disabled={waiting||m.missing} onClick={()=>edit({type:'append',source:m.id})}>Add to timeline</button>
       {m.missing&&<button disabled={busy||waiting} onClick={()=>act('relink',{source:m.id})}>Relink</button>}</div>
     </div>)}
    </div>
    <div className="media-footer">Original files stay untouched.<br/>Edits use local working copies.</div>
   </aside>
   <main className="editor">
    <section className="monitor" aria-label="Video monitor">
     <div className="monitor-head"><div className="tabs"><button className={mode==='source'?'active':''} onClick={()=>setMode('source')}>Source</button><button className={mode==='sequence'?'active':''} onClick={()=>setMode('sequence')}>Sequence</button></div>
      <span className="muted">{mode==='source'?(source?.name||'No source selected'):(stale?'Preview needs refresh':state.preview?'Preview up to date':'Render a preview')}</span></div>
     <div className="screen">{url?<video ref={video} key={url} src={url} controls onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onTimeUpdate={syncTime}
       onLoadedMetadata={()=>{if(video.current)video.current.currentTime=mode==='source'&&clip?clip.in/25:0}}
       onError={()=>setError('The video could not be played. Relink missing media or refresh the sequence preview.')}/>:
      <div className="monitor-empty"><span className="frame-symbol">[ ▷ ]</span><p>{mode==='source'?'Your footage starts here':'See your edit as one video'}</p><span className="muted">{mode==='source'?'Import a video or load the test clip.':'Refresh the preview after making edits.'}</span></div>}</div>
     <div className="monitor-footer"><span>{mode==='source'?'Source playback':'Sequence playback'}{playing?' · Playing':''}</span>
      <button disabled={busy||waiting||!state.duration} onClick={()=>act('preview')}>Refresh preview · 540p</button></div>
    </section>
    <div className="editor-tabs tabs"><button className={!toolTab?"active":""} onClick={()=>setToolTab(false)}>Timeline</button><button className={toolTab?"active":""} onClick={()=>setToolTab(true)}>Effects & captions</button></div>
    {toolTab?<Tools state={state} selected={selected} act={act}/>:<section className="timeline" aria-label="Timeline">
     <div className="panel-heading"><h2>Timeline <span>VIDEO + LINKED AUDIO</span></h2><span>{seconds(state.duration)}s · 25 fps</span></div>
     <div className="timeline-toolbar"><label>Playhead <input aria-label="Playhead seconds" type="number" min="0" max={state.duration/25} step=".04" value={seconds(playhead)} onChange={e=>seek(Number(e.target.value)*25)}/><span>s</span></label>
      <button disabled={!state.duration} onClick={()=>seek(playhead-1)} title="Previous frame">−1f</button><button disabled={!state.duration} onClick={()=>seek(playhead+1)} title="Next frame">+1f</button>
      <button disabled={!clip||waiting} onClick={()=>edit({type:'split',clip:selected,at:playhead})}>Split</button>
      <button disabled={!clip||waiting} onClick={()=>edit({type:'delete',clip:selected,ripple})}>Delete</button>
      <button disabled={!clip||waiting} onClick={()=>edit({type:'move',clip:selected,direction:'left'})}>← Move</button>
      <button disabled={!clip||waiting} onClick={()=>edit({type:'move',clip:selected,direction:'right'})}>Move →</button>
     </div>
     <input className="scrubber" aria-label="Timeline playhead" type="range" min="0" max={state.duration||1} step="1" value={Math.min(playhead,state.duration)} onChange={e=>seek(Number(e.target.value))}/>
     <div className="tracks">
      {!state.duration?<p className="timeline-empty">Add imported media to start your sequence.</p>:
       <><div className="ruler"><span>0:00</span><span>{seconds(state.duration/2)}s</span><span>{seconds(state.duration)}s</span></div>
       <div className="track"><span className="track-label">V1</span><div className="track-content">
        {project!.clips.map((c,i)=><button key={c.id} title={'Source '+seconds(c.in)+'–'+seconds(c.out)+'s'} className={'clip '+(c.id===selected?'active':'')} style={{left:(c.start/state.duration*100)+'%',width:((c.out-c.in)/state.duration*100)+'%'}} onClick={()=>select(c)}><strong>{i+1}</strong><span>{seconds(c.in)}–{seconds(c.out)}s</span></button>)}
        <i className="playhead" style={{left:(playhead/state.duration*100)+'%'}}/></div></div>
       <div className="track audio-track"><span className="track-label">A1</span><div className="track-content">{project!.clips.map(c=><button aria-label="Select linked audio" key={c.id} className={'clip audio '+(c.id===selected?'active':'')} style={{left:(c.start/state.duration*100)+'%',width:((c.out-c.in)/state.duration*100)+'%'}} onClick={()=>select(c)}>Linked audio</button>)}</div></div></>}
     </div>
     <div className="trim-controls"><label>Source in (s)<input disabled={!clip} type="number" min="0" step=".04" value={trimIn} onChange={e=>setTrimIn(e.target.value)}/></label>
      <label>Source out (s)<input disabled={!clip} type="number" min="0" step=".04" value={trimOut} onChange={e=>setTrimOut(e.target.value)}/></label>
      <button disabled={!clip||waiting} onClick={()=>edit({type:'trim',clip:selected,in:Math.round(Number(trimIn)*25),out:Math.round(Number(trimOut)*25),ripple})}>Apply trim</button>
      <label className="checkbox"><input type="checkbox" checked={ripple} onChange={e=>setRipple(e.target.checked)}/>Ripple later clips</label></div>
    </section>}
   </main>
   <aside className="chat-panel"><div className="panel-heading"><h2>Edit assistant</h2><span>{state.provider?.configured?"OPENAI":"OFFLINE"}</span></div>
    <p className="chat-intro">Your prompts and editing history.<br/><span className="muted">Review proposed edits before applying.</span></p>
    <div className="history" ref={history} aria-live="polite">
     {!project!.chat.length&&<div className="chat-empty"><h3>Make your first cut.</h3><p>Select a timeline clip, move the playhead, then try:</p><button onClick={()=>setPrompt('Split the selected clip at the playhead')}>Split the selected clip at the playhead</button><p className="muted">You review every proposed change before applying it.</p></div>}
     {project!.chat.map(entry=><article className={'entry '+entry.role} key={entry.id}><div className="entry-meta"><strong>{entry.role==='user'?'You':'Vibeflow'}</strong><span>{entry.status==='prompt'?'Prompt':entry.status}</span></div><p>{entry.text}</p>
      {entry.status==='preview'&&state.pending.includes(entry.id)&&<div className="proposal-actions"><button disabled={waiting} onClick={()=>act('apply',{plan_id:entry.id})}>Apply edit</button><button disabled={waiting} onClick={()=>act('discard')}>Discard</button></div>}</article>)}
    </div>
    <div className="composer"><label htmlFor="prompt">Ask for an edit</label><textarea id="prompt" maxLength={500} value={prompt} placeholder="Split the selected clip at the playhead…" onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}/>
     <div><span className="muted">Enter to send · Shift+Enter for a line</span><button disabled={busy||waiting||!prompt.trim()} onClick={send}>Send</button></div>
     <details><summary>Example prompts</summary><p>Split the selected clip at the playhead<br/>Trim selected clip from 1 to 5 seconds<br/>Delete selected clip<br/>Move selected clip left / right</p><p>With an OpenAI key: “Add a 12-frame dissolve between clips 1 and 2” or “Remove pauses longer than 1 second”. Trim times refer to source video.</p></details></div>
   </aside>
  </div>
  {settings&&<Settings state={state} act={act} onClose={()=>setSettings(false)}/>}
  {error&&<div className="error-banner" role="alert"><span>{error}</span><button onClick={()=>setError('')}>Dismiss</button></div>}
  <footer className="statusbar"><div className="status-text">{state.job?<><strong>{state.job.kind} · {state.job.status}</strong><span>{state.job.message}</span>{busy&&<progress value={state.job.progress} max="1"/>}{busy&&<button onClick={()=>act('cancel')}>Cancel</button>}{state.job.kind==='export'&&state.job.status==='done'&&<button onClick={()=>act('show-export')}>Show file</button>}</>:<span>Ready · Local rendering</span>}</div><button onClick={()=>act('diagnostics')}>Diagnostics</button></footer>
 </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
