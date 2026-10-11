// Explicitly approved for generated files in out/Vibeflow-win32-x64.
// No inheritable ACE: future project/session data does not inherit this grant.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=fs.realpathSync(path.resolve(__dirname,'..'));
const target=fs.realpathSync(path.join(root,'out','Vibeflow-win32-x64'));
if(path.relative(root,target)!==path.join('out','Vibeflow-win32-x64'))throw Error('Unexpected package path.');
if(!fs.existsSync(path.join(target,'icudtl.dat'))||!fs.existsSync(path.join(target,'Vibeflow.exe')))
 throw Error('Expected the generated Electron runtime.');
for(const name of ['VibeflowData','Projects','Exports'])
 if(fs.existsSync(path.join(target,name)))throw Error('Refusing to alter permissions in a package containing session/project data.');
const result=spawnSync(path.join(process.env.SystemRoot,'System32','icacls.exe'),
 [target,'/grant','*S-1-15-2-1:RX','/T','/Q'],{windowsHide:true,encoding:'utf8'});
if(result.status!==0)throw Error(result.stderr||result.stdout||'Could not prepare runtime file permissions.');
console.log('Granted read/execute access only to existing generated application files; no inheritable permissions.');
