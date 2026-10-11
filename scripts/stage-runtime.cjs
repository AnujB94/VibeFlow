const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const destination=path.join(root,'runtime','media');
fs.mkdirSync(path.join(destination,'fonts'),{recursive:true});
for(const [src,name] of [
 ['node_modules/ffmpeg-static/ffmpeg.exe','ffmpeg.exe'],
 ['node_modules/ffmpeg-static/ffmpeg.exe.LICENSE','FFMPEG-LICENSE.txt'],
 ['node_modules/ffmpeg-static/ffmpeg.exe.README','FFMPEG-README.txt'],
 ['node_modules/@ffprobe-installer/win32-x64/ffprobe.exe','ffprobe.exe'],
 ['node_modules/@ffprobe-installer/win32-x64/README.md','FFPROBE-README.md']
]) fs.copyFileSync(path.join(root,src),path.join(destination,name));
for(const name of ['DejaVuSans.ttf','DejaVuSans-Bold.ttf','LICENSE_DEJAVU'])
 fs.copyFileSync(path.join(root,'assets','fonts',name),path.join(destination,'fonts',name));
console.log('Staged media runtime and fonts.');
