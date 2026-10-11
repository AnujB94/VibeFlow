// Relocate the already-prepared application files, launch, then restore the folder name.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const root=fs.realpathSync(path.resolve(__dirname,'..'));
const source=path.join(root,'out','Vibeflow-win32-x64'),moved=path.join(root,'out','Vibeflow-startup-check');
for(const target of [source,moved]){
 const relative=path.relative(root,path.resolve(target));
 if(!relative||relative.startsWith('..')||path.isAbsolute(relative))throw Error('Invalid test relocation path');
}
if(fs.existsSync(moved))throw Error('The startup-check folder already exists; inspect it before retrying.');
fs.renameSync(source,moved);
const env={...process.env,PATH:path.join(process.env.SystemRoot,'System32')};
delete env.PYTHONPATH;delete env.PYTHONHOME;delete env.ELECTRON_RUN_AS_NODE;
const logpath=path.join(moved,'VibeflowData','logs','app.log');
const child=spawn(path.join(moved,'Vibeflow.exe'),['--smoke-test'],{cwd:moved,env,windowsHide:true,stdio:'inherit'});
let ended=false;
const timer=setTimeout(()=>{child.kill();console.error('App startup test timed out');process.exitCode=1},30000);
function finish(code){
 if(ended)return;ended=true;clearTimeout(timer);
 const events=fs.existsSync(logpath)?fs.readFileSync(logpath,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse):[];
 const report={exit_code:code,relocated_full_app:true,developer_runtimes_on_PATH:false,
  renderer_loaded:events.some(x=>x.event==='renderer-loaded'&&x.packaged),
  backend_connected:events.some(x=>x.event==='backend-ready'),
  startup_smoke_passed:events.some(x=>x.event==='startup-smoke-passed'),
  visual_interaction_verified:false};
 fs.writeFileSync(path.join(root,'verification','app-startup-report.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
 // Wait for owned sidecar shutdown before restoring the portable folder name.
 let attempts=0;
 const restore=()=>{
  try{fs.renameSync(moved,source)}
  catch(error){if(++attempts<20){setTimeout(restore,300);return}console.error('Restore failed:',error);process.exitCode=1}
 };
 restore();
 if(code!==0||!report.startup_smoke_passed||!report.renderer_loaded)process.exitCode=1;
}
child.on('error',error=>{console.error(error);finish(-1)});
child.on('exit',finish);
