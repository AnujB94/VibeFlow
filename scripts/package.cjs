const {spawnSync}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
const root=path.resolve(__dirname,'..');
process.chdir(root);
const previous=path.join(root,'out','Vibeflow-win32-x64');
for(const name of ['VibeflowData','Projects','Exports'])
 if(fs.existsSync(path.join(previous,name)))throw Error('Preserve the existing portable app folder before rebuilding: it contains '+name+'. Move that folder aside, then package again.');
const env={...process.env,electron_config_cache:path.join(root,'.cache','electron'),
 PYINSTALLER_CONFIG_DIR:path.join(root,'.cache','pyinstaller')};
function step(command,args){
 const result=spawnSync(command,args,{cwd:root,env,stdio:'inherit',windowsHide:true});
 if(result.error)throw result.error;
 if(result.status!==0)process.exit(result.status||1);
}
step(process.execPath,[path.join(root,'node_modules','typescript','bin','tsc'),'--noEmit']);
step(process.execPath,[path.join(root,'node_modules','vite','bin','vite.js'),'build']);
step(process.execPath,[path.join(__dirname,'stage-runtime.cjs')]);
step('python',['-m','PyInstaller','--noconfirm','--clean','--onedir','--name','vibeflow-backend',
 '--distpath','runtime/build','--workpath','.cache/pyinstaller-work','--specpath','.cache',
 '--paths',root,'backend/entry.py']);
// Forge copies this directory verbatim as resources/backend.
fs.mkdirSync(path.join(root,'runtime','backend'),{recursive:true});
fs.cpSync(path.join(root,'runtime','build','vibeflow-backend'),path.join(root,'runtime','backend'),{recursive:true,force:true});
step(process.execPath,[path.join(root,'node_modules','@electron-forge','cli','dist','electron-forge.js'),'package','--platform=win32','--arch=x64']);
const output=path.join(root,'out','Vibeflow-win32-x64');
for(const file of ['README.md','THIRD_PARTY.md','VERIFICATION.md','VERIFICATION_PHASE1.md','MVP_PLAN.md'])if(fs.existsSync(path.join(root,file)))fs.copyFileSync(path.join(root,file),path.join(output,file));
fs.copyFileSync(path.join(root,'scripts','setup-speech.py'),path.join(output,'setup-speech.py'));
fs.copyFileSync(path.join(root,'setup-speech.cmd'),path.join(output,'setup-speech.cmd'));
console.log('Portable app: '+path.join(output,'Vibeflow.exe'));
