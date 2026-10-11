import React,{useState} from 'react';
type Props={state:any;selected:string;act:(method:string,params?:any)=>Promise<any>};
export function Settings({state,act,onClose}:{state:any;act:Props['act'];onClose:()=>void}){
 const[key,setKey]=useState(''),[model,setModel]=useState(state.provider?.model||'gpt-4o-mini');
 return <div className="modal-shade"><section className="settings-dialog" role="dialog" aria-modal="true" aria-label="OpenAI settings">
 <div className="panel-heading"><h2>OpenAI settings</h2><button onClick={onClose}>Close</button></div>
 <p>Chat sends your prompt, clip timings and caption text to OpenAI. Videos stay local. Audio is uploaded only when you explicitly choose OpenAI transcription.</p>
 <label>API key · kept only until the app closes<input autoFocus type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={state.provider?.configured?'Key configured; enter to replace':'sk-…'}/></label>
 <label>Text model<input value={model} onChange={e=>setModel(e.target.value)}/></label>
 <p className="muted">API usage is billed to your OpenAI account. Local speech: {state.provider?.local_speech?'installed':'not installed — run setup-speech.cmd; requires Python 3.11+'}.</p>
 <button className="primary" disabled={!key.trim()} onClick={async()=>{if(await act('settings',{key,model})){setKey('');onClose()}}}>Use key for this session</button>
 <button onClick={async()=>{await act('settings',{key:'',model});setKey('')}}>Clear key</button>
 </section></div>
}
function Cue({cue,clip,act,revision}:{cue:any;clip:any;act:Props['act'];revision:number}){
 const[text,setText]=useState(cue.text),[start,setStart]=useState(String(cue.in/25)),[end,setEnd]=useState(String(cue.out/25)),[bold,setBold]=useState(cue.bold.join(', '));
 const update=(extra:any={})=>act('edit',{revision,operation:{type:'caption',id:cue.id,text,in:Math.round(Number(start)*25),out:Math.round(Number(end)*25),bold:bold.split(',').map((s:string)=>s.trim()).filter(Boolean),...extra}});
 return <div className="cue">
  <div className="cue-meta"><strong>{((clip.start+cue.in-clip.in)/25).toFixed(2)}–{((clip.start+cue.out-clip.in)/25).toFixed(2)}s</strong><span>{cue.needs_review?'Review timing/text':'Reviewed'}</span></div>
  <textarea aria-label="Caption text" value={text} onChange={e=>setText(e.target.value)}/>
  <div className="tool-row"><label>Source in <input aria-label="Caption source in" type="number" step=".04" value={start} onChange={e=>setStart(e.target.value)}/></label><label>Source out <input aria-label="Caption source out" type="number" step=".04" value={end} onChange={e=>setEnd(e.target.value)}/></label></div>
  <label>Bold words, comma separated<input aria-label="Bold caption words" value={bold} onChange={e=>setBold(e.target.value)}/></label>
  <div className="tool-row"><button onClick={()=>update()}>Save caption</button><button onClick={()=>update({delete:true})}>Delete caption</button><details><summary>Raw transcript</summary><p>{cue.raw_text||'Manual caption'}</p></details></div>
 </div>
}
export function Tools({state,selected,act}:Props){
 const p=state.project,clips=p.clips,clip=clips.find((c:any)=>c.id===selected),index=clips.findIndex((c:any)=>c.id===selected),right=clips[index+1];
 const[kind,setKind]=useState('dissolve'),[frames,setFrames]=useState(12);
 const[threshold,setThreshold]=useState(1),[padding,setPadding]=useState(.12),[db,setDb]=useState(-38);
 const[mode,setMode]=useState('local'),[size,setSize]=useState(p.caption_style?.size||54),[position,setPosition]=useState(p.caption_style?.position||'bottom');
 const busy=state.job?.status==='running';
 const edit=(operation:any)=>act('edit',{revision:p.revision,operation});
 return <section className="tools-panel" aria-label="Effects and captions">
 <details open><summary>Transitions <span className="muted">· video only, audio stays unchanged</span></summary>
 <p className="muted">{clip&&right?'Cut between clip '+(index+1)+' and '+(index+2)+' at '+right.start/25+'s.':'Select a clip with another clip immediately after it.'}</p>
 <div className="tool-row"><select aria-label="Transition type" value={kind} onChange={e=>setKind(e.target.value)}><option value="dissolve">Cross dissolve</option><option value="black">Fade through black</option></select>
 <label>Frames<input aria-label="Transition frames" type="number" min="2" max="125" value={frames} onChange={e=>setFrames(Number(e.target.value))}/></label>
 <button disabled={!clip||!right||busy} onClick={()=>act('propose',{operation:{type:'transition',left:selected,right:right.id,kind,frames}})}>Preview transition plan</button>
 <button disabled={!clip||busy} onClick={()=>edit({type:'remove_transition',left:selected})}>Remove transition</button></div>
 <p className="muted">{(p.transitions||[]).length} transitions. Trim both sides of a cut to leave spare source frames.</p>
 </details>
 <details><summary>Remove pauses & empty gaps</summary><p className="muted">Scans the current timeline for low-volume audio. Review every proposed range in chat; quiet speech can be mistaken for silence.</p>
 <div className="tool-row"><label>Longer than (s)<input type="number" min=".1" max="30" step=".1" value={threshold} onChange={e=>setThreshold(Number(e.target.value))}/></label>
 <label>Keep padding (s)<input type="number" min="0" max="1" step=".04" value={padding} onChange={e=>setPadding(Number(e.target.value))}/></label>
 <label>Below (dB)<input type="number" min="-70" max="-15" value={db} onChange={e=>setDb(Number(e.target.value))}/></label>
 <button disabled={busy||!clips.length} onClick={()=>act('analyze',{threshold,padding,db})}>Find pauses</button></div></details>
 <details open><summary>Roman-Hinglish captions</summary><p className="muted">Hindi words in Roman script; English words kept. Generated spelling and timing need review.</p>
 <div className="tool-row"><select aria-label="Transcription provider" value={mode} onChange={e=>setMode(e.target.value)}><option value="local">Local speech recognition</option><option value="openai">OpenAI · uploads timeline audio</option></select>
 <button disabled={busy||!clips.length||!state.provider?.configured||(mode==='local'&&!state.provider?.local_speech)} onClick={()=>act('captions',{mode})}>Generate captions</button>
 <button disabled={!clip||busy} onClick={()=>edit({type:'captions',clips:[],cues:[{id:crypto.randomUUID(),clip:selected,in:clip.in,out:Math.min(clip.out,clip.in+50),text:'Yeh mera video hai',raw_text:'',words:[],bold:[],needs_review:true}]})}>Add manual caption</button>
 <button disabled={!(p.captions||[]).length} onClick={()=>act('srt')}>Export SRT</button></div>
 {!state.provider?.configured&&<p className="muted">Add an API key in Settings to generate and Romanize captions. Manual captions work offline.</p>}
 <div className="tool-row"><label>Size (1080p)<input type="number" min="20" max="120" value={size} onChange={e=>setSize(Number(e.target.value))}/></label><label>Position<select value={position} onChange={e=>setPosition(e.target.value)}><option>bottom</option><option>middle</option><option>top</option></select></label>
 <button onClick={()=>edit({type:'caption_style',size,position})}>Apply caption style</button></div>
 {(p.captions||[]).map((c:any)=><Cue key={c.id+':'+p.revision} cue={c} clip={clips.find((v:any)=>v.id===c.clip)} act={act} revision={p.revision}/>)}
 </details></section>
}
