// Runs the relocated frozen backend with no developer runtime on PATH.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),readline=require('node:readline');
const root=path.resolve(__dirname,'..');
const packageDir=process.argv[2]?path.resolve(process.argv[2]):path.join(root,'out','Vibeflow-win32-x64');
const resourceDir=fs.existsSync(path.join(packageDir,'resources'))?path.join(packageDir,'resources'):packageDir;
const moved=path.join(root,'verification','relocated-demo');
fs.mkdirSync(moved,{recursive:true});
fs.cpSync(path.join(resourceDir,'backend'),path.join(moved,'backend'),{recursive:true});
fs.cpSync(path.join(resourceDir,'media'),path.join(moved,'media'),{recursive:true});
const env={...process.env,PATH:path.join(process.env.SystemRoot,'System32')};
delete env.PYTHONPATH;delete env.PYTHONHOME;
const child=spawn(path.join(moved,'backend','vibeflow-backend.exe'),['--data',path.join(moved,'data'),'--resources',path.join(moved,'media')],{cwd:moved,env,windowsHide:true});
let id=0,state;
const pending=new Map();
function call(method,params={}){return new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});child.stdin.write(JSON.stringify({id:key,method,params})+'\n')})}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let readyResolve;const ready=new Promise(r=>readyResolve=r);
readline.createInterface({input:child.stdout}).on('line',line=>{
 const message=JSON.parse(line);
 if(message.event==='ready'){state=message.data;readyResolve()}
 if(message.id){const p=pending.get(message.id);pending.delete(message.id);if(p)message.error?p.reject(Error(message.error)):p.resolve(message.result)}
});
child.stderr.pipe(process.stderr);
child.on('error',error=>{console.error(error);process.exit(1)});
const timeout=setTimeout(()=>{child.kill();console.error('Packaged smoke test timed out');process.exit(1)},120000);
async function waitJob(){for(;;){state=await call('state');if(state.job.status!=='running'){if(state.job.status!=='done')throw Error(JSON.stringify(state.job));return}await sleep(300)}}
(async()=>{
 await ready;
 await call('new');
 await call('demo');await waitJob();
 state=await call('state');const media=state.project.media[0];
 state=await call('edit',{revision:state.project.revision,operation:{type:'append',source:media.id}});
 state=await call('edit',{revision:state.project.revision,operation:{type:'trim',clip:state.project.clips[0].id,in:25,out:75}});
 state=await call('edit',{revision:state.project.revision,operation:{type:'append',source:media.id}});
 const second=state.project.clips[1].id;
 state=await call('edit',{revision:state.project.revision,operation:{type:'trim',clip:second,in:150,out:200}});
 state=await call('edit',{revision:state.project.revision,operation:{type:'transition',left:state.project.clips[0].id,right:second,kind:'black',frames:13}});
 state=await call('edit',{revision:state.project.revision,operation:{type:'captions',clips:[second],cues:[{id:'pack-cue',clip:second,in:165,out:190,text:'Yeh packaged demo hai',raw_text:'',words:[],bold:['demo']}]}});
 await call('preview');await waitJob();
 await call('export',{filename:path.join(moved,'packaged-export.mp4')});await waitJob();
 await call('analyze',{threshold:.5,padding:.12,db:-38});await waitJob();
 state=await call('state');if(!state.pending.length)throw Error('No packaged pause proposal');
 await call('apply',{plan_id:state.pending[0]});
 await call('undo');
 await call('save',{filename:path.join(moved,'Packaged.vibeflow')});
 await call('open',{filename:path.join(moved,'Packaged.vibeflow')});
 child.stdin.end();
 await new Promise(resolve=>child.on('exit',resolve));
 if(child.exitCode!==0)throw Error('Backend shutdown failed');
 clearTimeout(timeout);
 const report={startup:'passed',developer_runtimes_on_PATH:false,relocated_backend:true,generated_demo:true,preview:true,export:true,save_reopen:true,transition:true,caption_burnin:true,pause_proposal_apply_undo:true,shutdown_exit_code:child.exitCode};
 fs.writeFileSync(path.join(root,'verification','packaged-report.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
})().catch(error=>{clearTimeout(timeout);child.kill();console.error(error);process.exit(1)});
