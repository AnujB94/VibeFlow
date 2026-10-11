const {app,BrowserWindow,ipcMain,dialog,shell,screen}=require('electron');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const readline=require('node:readline');
const {pathToFileURL}=require('node:url');
const base=app.isPackaged?path.dirname(process.execPath):path.resolve(__dirname,'..');
const data=path.join(base,'VibeflowData');
fs.mkdirSync(path.join(data,'logs'),{recursive:true});
app.setPath('userData',path.join(data,'electron'));
app.setPath('sessionData',path.join(data,'session'));
app.setPath('crashDumps',path.join(data,'crashes'));
const appLog=(event,details={})=>fs.appendFileSync(path.join(data,'logs','app.log'),JSON.stringify({time:new Date().toISOString(),event,...details})+'\n');
let win,backend,latest,stopping=false,counter=0;
if(!app.requestSingleInstanceLock())app.quit();
app.on('second-instance',()=>{if(win){if(win.isMinimized())win.restore();win.focus()}});
const pending=new Map();
let resolveReady,rejectReady;
const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject});
ready.catch(()=>{});
function decorate(state){
 if(!state)return state;
 for(const m of state.project.media) m.url=m.missing?'':pathToFileURL(m.working).href;
 if(state.preview)state.preview.url=pathToFileURL(state.preview.path).href;
 latest=state;
 return state;
}
function call(method,params={}){
 return ready.then(()=>new Promise((resolve,reject)=>{
  if(!backend||backend.exitCode!==null)return reject(new Error('Backend stopped. Restart Vibeflow; your editing session is recovered automatically.'));
  const id=++counter;
  pending.set(id,{resolve,reject});
  backend.stdin.write(JSON.stringify({id,method,params})+'\n',error=>{
   if(error){pending.delete(id);reject(error)}
  });
 }));
}
function startBackend(){
 const resources=app.isPackaged?path.join(process.resourcesPath,'media'):path.join(base,'runtime','media');
 const executable=app.isPackaged?path.join(process.resourcesPath,'backend','vibeflow-backend.exe'):'python';
 const args=(app.isPackaged?[]:[path.join(base,'backend','entry.py')]).concat(['--data',data,'--resources',resources]);
 backend=spawn(executable,args,{cwd:base,windowsHide:true,stdio:['pipe','pipe','pipe']});
 const log=fs.createWriteStream(path.join(data,'logs','sidecar.log'),{flags:'a'});
 backend.stderr.pipe(log);
 const fail=error=>{
  rejectReady(error); for(const p of pending.values())p.reject(error);pending.clear();
  if(!stopping&&win&&!win.isDestroyed())win.webContents.send('backend-event',{event:'fatal',data:error.message});
 };
 backend.on('error',fail);
 backend.on('exit',code=>{appLog('backend-exit',{code});log.end();fail(new Error('Local backend exited ('+code+'). Restart the app to recover the session.'))});
 readline.createInterface({input:backend.stdout}).on('line',line=>{
  try{
   const message=JSON.parse(line);
   if(message.event==='ready'){decorate(message.data);appLog('backend-ready');resolveReady()}
   else if(message.event){
    if(message.event==='state')decorate(message.data);
    if(message.event==='job'&&latest)latest.job=message.data;
    if(win&&!win.isDestroyed())win.webContents.send('backend-event',message);
   } else {
    const p=pending.get(message.id);pending.delete(message.id);
    if(p){message.error?p.reject(new Error(message.error)):p.resolve(decorate(message.result))}
   }
  }catch(error){fs.appendFileSync(path.join(data,'logs','protocol.log'),String(error)+'\n')}
 });
}
async function discardOkay(){
 if(!latest?.dirty)return true;
 const result=await dialog.showMessageBox(win,{type:'question',buttons:['Keep editing','Discard and continue'],defaultId:0,cancelId:0,
  message:'This project has unsaved changes.',detail:'Save it first to keep this version. Continuing replaces the recovered session.'});
 return result.response===1;
}
const allowed=new Set(['state','edit','undo','redo','prompt','apply','discard','preview','cancel','demo','settings','analyze','captions','propose']);
ipcMain.handle('vibeflow',async(event,method,params={})=>{
 if(event.sender!==win.webContents)throw Error('Unknown window');
 if(allowed.has(method))return call(method,params);
 if(method==='new'){if(await discardOkay())return call('new');return latest}
 if(method==='open'){
  if(!await discardOkay())return latest;
  const result=await dialog.showOpenDialog(win,{filters:[{name:'Vibeflow project',extensions:['vibeflow']}],properties:['openFile']});
  return result.canceled?latest:call('open',{filename:result.filePaths[0]});
 }
 if(method==='import'||method==='relink'){
  const result=await dialog.showOpenDialog(win,{title:method==='relink'?'Relink with the same source video':'Import landscape SDR video',
   filters:[{name:'Video',extensions:['mp4','mov','mkv','webm','avi','m4v']}],properties:['openFile']});
  return result.canceled?latest:call('import',{filename:result.filePaths[0],relink:method==='relink'?params.source:undefined});
 }
 if(method==='save'){
  let filename=latest?.filepath;
  if(!filename){
   const result=await dialog.showSaveDialog(win,{defaultPath:path.join(base,'Projects','My edit.vibeflow'),filters:[{name:'Vibeflow project',extensions:['vibeflow']}]});
   if(result.canceled)return latest;
   filename=result.filePath;
  }
  return call('save',{filename});
 }
 if(method==='srt'){
  const result=await dialog.showSaveDialog(win,{defaultPath:path.join(base,'Exports','Captions.srt'),filters:[{name:'SubRip captions',extensions:['srt']}]});
  if(result.canceled)return latest;
  if(path.extname(result.filePath).toLowerCase()!=='.srt')throw Error('Choose an .srt filename for subtitles.');
  return call('srt',{filename:result.filePath});
 }
 if(method==='export'){
  const result=await dialog.showSaveDialog(win,{defaultPath:path.join(base,'Exports','My edit.mp4'),filters:[{name:'MP4 video',extensions:['mp4']}]});
  if(result.canceled)return latest;
  const output=path.resolve(result.filePath).toLowerCase();
  if(latest.project.media.some(m=>[m.working,m.original].filter(Boolean).some(p=>path.resolve(p).toLowerCase()===output)))
   throw Error('Choose a new export filename to preserve your source media.');
  return call('export',{filename:result.filePath});
 }
 if(method==='diagnostics'){await shell.openPath(path.join(data,'logs'));return latest}
 if(method==='show-export'){
  if(latest?.job?.status==='done'&&latest.job.kind==='export')shell.showItemInFolder(latest.job.output);
  return latest;
 }
 throw Error('Unsupported application action');
});
app.whenReady().then(()=>{
 startBackend();
 const workArea=screen.getPrimaryDisplay().workAreaSize;
 win=new BrowserWindow({width:Math.min(1460,workArea.width),height:Math.min(940,workArea.height),minWidth:Math.min(1100,workArea.width),minHeight:Math.min(760,workArea.height),backgroundColor:'#151515',title:'Vibeflow',
  webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
 win.setMenuBarVisibility(false);
 win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 win.webContents.on('will-navigate',event=>event.preventDefault());
 win.webContents.on('did-fail-load',(_event,code,description)=>appLog('renderer-load-failed',{code,description}));
 win.webContents.on('render-process-gone',(_event,details)=>appLog('renderer-crashed',details));
 win.webContents.on('did-finish-load',async()=>{
  appLog('renderer-loaded',{packaged:app.isPackaged});
  if(process.argv.includes('--smoke-test')){
   try{const state=await call('state');appLog('startup-smoke-passed',{project:state.project.id});setTimeout(()=>app.quit(),1000)}
   catch(error){appLog('startup-smoke-failed',{error:error.message});app.exit(1)}
  }
 });
 win.loadFile(path.join(__dirname,'..','dist','index.html'));
 if(process.argv.includes('--debug'))win.webContents.openDevTools({mode:'detach'});
});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{
 stopping=true;appLog('app-quit');
 if(backend){backend.stdin.end();setTimeout(()=>{if(backend.exitCode===null)backend.kill()},6000).unref()}
});
