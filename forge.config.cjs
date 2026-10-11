const path=require('node:path');
const fs=require('node:fs');
const cache=path.join(__dirname,'.cache','electron');
const version=require('./package.json').devDependencies.electron;
const zip='electron-v'+version+'-win32-x64.zip';
const zipDir=fs.existsSync(cache)?fs.readdirSync(cache).map(n=>path.join(cache,n)).find(d=>fs.existsSync(path.join(d,zip))):undefined;
module.exports={
 outDir:process.env.VIBEFLOW_FIX_OUT||undefined,
 packagerConfig:{
  name:'Vibeflow',executableName:'Vibeflow',asar:true,electronZipDir:zipDir,
  download:{cacheRoot:path.join(__dirname,'.cache','electron')},
  extraResource:[path.join(__dirname,'runtime','backend'),path.join(__dirname,'runtime','media'),path.join(__dirname,'runtime','speech')],
  ignore:(file)=>file!==''&&!/^\/(electron|dist)(\/|$)/.test(file)&&file!=='/package.json'
 },
 rebuildConfig:{},
 makers:[]
};
