const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const env={...process.env,electron_config_cache:path.join(root,'.cache','electron'),
 LOCALAPPDATA:path.join(root,'.cache','installer')};
for(const script of ['node_modules/electron/install.js','node_modules/ffmpeg-static/install.js','scripts/stage-runtime.cjs']){
 const result=spawnSync(process.execPath,[path.join(root,script)],{cwd:root,env,windowsHide:true,stdio:'inherit'});
 if(result.error)throw result.error;
 if(result.status!==0)process.exit(result.status||1);
}
