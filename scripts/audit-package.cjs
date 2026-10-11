const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
(async()=>{
 const root=path.resolve(__dirname,'..'),folder=path.join(root,'out','Vibeflow-win32-x64');
 const {listPackage}=await import('@electron/asar');
 const files=listPackage(path.join(folder,'resources','app.asar'));
 if(files.some(x=>/node_modules|verification|MVP_PLAN|recovery/.test(x)))throw Error('Unexpected development/session files in app archive');
 const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
 const binaries={};
 for(const name of ['ffmpeg.exe','ffprobe.exe']){
  const packaged=hash(path.join(folder,'resources','media',name));
  if(packaged!==hash(path.join(root,'runtime','media',name)))throw Error('Media runtime differs: '+name);
  binaries[name]=packaged;
 }
 const backend=path.join(folder,'resources','backend','vibeflow-backend.exe');
 if(hash(backend)!==hash(path.join(root,'runtime','backend','vibeflow-backend.exe')))throw Error('Backend differs from final build');
 function total(p){return fs.readdirSync(p,{withFileTypes:true}).reduce((n,d)=>n+(d.isDirectory()?total(path.join(p,d.name)):fs.statSync(path.join(p,d.name)).size),0)}
 const report={archive_files:files,includes_development_dependencies:false,media_sha256:binaries,
  backend_matches_final_build:true,package_mib:Math.round(total(folder)/1024/1024)};
 fs.writeFileSync(path.join(root,'verification','package-audit.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
})().catch(error=>{console.error(error);process.exitCode=1});
