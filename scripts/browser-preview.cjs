// Local UI test adapter. Production uses native dialogs and IPC, never this server.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),readline=require('node:readline');
const root=path.resolve(__dirname,'..'),folder=path.join(root,'verification','browser-session');
fs.mkdirSync(folder,{recursive:true});
const child=spawn('python',[path.join(root,'backend','entry.py'),'--data',folder,'--resources',path.join(root,'runtime','media')],{cwd:root,windowsHide:true});
child.stderr.pipe(process.stderr);
let id=0,last;const pending=new Map();
function decorate(state){
 last=state;
 for(const m of state.project.media)m.url='/media/'+m.id;
 if(state.preview)state.preview.url='/media/preview-'+state.preview.revision;
 return state;
}
readline.createInterface({input:child.stdout}).on('line',line=>{
 const message=JSON.parse(line);
 if(message.event==='ready'||message.event==='state')decorate(message.data);
 if(message.id){const entry=pending.get(message.id);pending.delete(message.id);if(entry)message.error?entry.reject(Error(message.error)):entry.resolve(decorate(message.result))}
});
function call(method,params){return new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});child.stdin.write(JSON.stringify({id:key,method,params})+'\n')})}
const shim="window.vibeflow={call:async(method,params={})=>{const r=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,params})});const x=await r.json();if(x.error)throw Error(x.error);return x;},listen:cb=>{let previous='';const t=setInterval(async()=>{try{const x=await window.vibeflow.call('state');const s=JSON.stringify(x);if(s!==previous){previous=s;cb({event:'state',data:x});}}catch{}},700);return()=>clearInterval(t)}};";
const server=http.createServer(async(req,res)=>{
 try{
  if(req.url==='/preview-shim.js'){res.setHeader('Content-Type','text/javascript');return res.end(shim)}
  if(req.url==='/api'&&req.method==='POST'){
   let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>16000)throw Error('Request too large')}
   let {method,params}=JSON.parse(raw);params=params||{};
   if(method==='import'){method='demo';params={}}
   if(method==='save'||method==='open')params={filename:path.join(folder,'Browser demo.vibeflow')};
   if(method==='export')params={filename:path.join(folder,'Browser export.mp4')};
   if(method==='diagnostics'||method==='show-export')method='state';
   const allowed=new Set(['state','new','open','save','demo','edit','undo','redo','prompt','apply','discard','preview','export','cancel']);
   if(!allowed.has(method))throw Error('Unsupported preview action');
   const result=await call(method,params);res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(result));
  }
  if(req.url.startsWith('/media/')){
   const key=decodeURIComponent(req.url.slice(7));
   const filename=key.startsWith('preview-')?last?.preview?.path:last?.project.media.find(m=>m.id===key)?.working;
   if(!filename||!fs.existsSync(filename)){res.writeHead(404);return res.end()}
   const size=fs.statSync(filename).size,range=req.headers.range;
   const match=range&&/^bytes=(\d+)-(\d*)$/.exec(range);
   const start=match?Number(match[1]):0,end=match&&match[2]?Math.min(Number(match[2]),size-1):size-1;
   if(start>end||start>=size){res.writeHead(416);return res.end()}
   res.writeHead(match?206:200,{'Content-Type':'video/mp4','Accept-Ranges':'bytes','Content-Length':end-start+1,...(match?{'Content-Range':'bytes '+start+'-'+end+'/'+size}:{})});
   return fs.createReadStream(filename,{start,end}).pipe(res);
  }
  const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const relative=pathname==='/'?'index.html':pathname.slice(1);
  const filename=path.resolve(root,'dist',relative);
  if(!filename.startsWith(path.join(root,'dist')+path.sep))throw Error('Invalid path');
  let body=fs.readFileSync(filename);
  if(relative==='index.html')body=body.toString().replace("connect-src 'none'","connect-src 'self'").replace('<head>','<head><script src="/preview-shim.js"></script>');
  res.setHeader('Content-Type',({'.js':'text/javascript','.html':'text/html','.css':'text/css'})[path.extname(filename)]||'application/octet-stream');res.end(body);
 }catch(error){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({error:error.message}))}
});
server.listen(4173,'127.0.0.1',()=>console.log('UI test adapter: http://127.0.0.1:4173'));
function close(){child.stdin.end();server.close();setTimeout(()=>process.exit(),1000).unref()}
process.on('SIGINT',close);process.on('SIGTERM',close);
