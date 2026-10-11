// DOM integration test with the real Python backend (no desktop automation).
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const data=path.join(root,'verification','dom-session-'+Date.now());fs.mkdirSync(data,{recursive:true});
const child=spawn('python',[path.join(root,'backend','entry.py'),'--data',data,'--resources',path.join(root,'runtime','media')],{cwd:root,windowsHide:true});
let count=0,last,listeners=new Set(),readyResolve;
const pending=new Map(),ready=new Promise(resolve=>readyResolve=resolve);
function publish(state){last=state;for(const m of state.project.media)m.url='';if(state.preview)state.preview.url='';return state}
readline.createInterface({input:child.stdout}).on('line',line=>{
 const message=JSON.parse(line);
 if(message.event==='ready'){publish(message.data);readyResolve()}
 if(message.event==='state'){publish(message.data);for(const listener of listeners)listener(message)}
 if(message.event==='job'){for(const listener of listeners)listener(message)}
 if(message.id){const p=pending.get(message.id);pending.delete(message.id);if(p)message.error?p.reject(Error(message.error)):p.resolve(publish(message.result))}
});
child.stderr.pipe(process.stderr);
function request(method,params={}){return new Promise((resolve,reject)=>{
 if(method==='save'||method==='open')params={filename:path.join(data,'UI.vibeflow')};
 const id=++count;pending.set(id,{resolve,reject});child.stdin.write(JSON.stringify({id,method,params})+'\n');
})}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,label){for(let i=0;i<300;i++){if(check())return;await delay(100)}throw Error('Timed out: '+label)}
(async()=>{
 await ready;
 const fixture=JSON.parse(fs.readFileSync(path.join(root,'verification','Acceptance.vibeflow'),'utf8'));
 const media=fixture.project.media[0];
 const src=path.resolve(root,'verification',media.working);
 // Use the acceptance project to skip re-normalizing already-tested video.
 await request('open',{filename:path.join(root,'verification','Acceptance.vibeflow')}).catch(()=>{});
 // The UI adapter's open action always targets UI.vibeflow, so seed that file explicitly.
 const seed=structuredClone(fixture);seed.project.clips=[{id:'ui-clip',source:media.id,in:0,out:300,start:0}];
 seed.project.media[0].working=src;seed.project.chat=[];seed.project.revision=1;
 fs.writeFileSync(path.join(data,'UI.vibeflow'),JSON.stringify(seed));
 await request('open');
 const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
 const window=dom.window;
 window.HTMLElement.prototype.scrollTo=function(){};
 window.vibeflow={call:request,listen:callback=>{listeners.add(callback);return()=>listeners.delete(callback)}};
 const html=fs.readFileSync(path.join(root,'dist','index.html'),'utf8');
 const script=html.match(/src="([^"]+[.]js)"/)[1];
 window.eval(fs.readFileSync(path.join(root,'dist',script),'utf8'));
 const document=window.document;
 await until(()=>document.querySelector('.app'),'app connected');
 function button(label){const found=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===label);assert(found,'Missing button '+label);return found}
 async function click(label){await until(()=>!button(label).disabled,label+' enabled');button(label).click();await delay(50)}
 function input(element,value){const descriptor=Object.getOwnPropertyDescriptor(element instanceof window.HTMLTextAreaElement?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype,'value');descriptor.set.call(element,value);element.dispatchEvent(new window.Event('input',{bubbles:true}));}
 await delay(100);
 document.querySelector('.track .clip').click();
 await until(()=>!button('Split').disabled,'clip selected');
 input(document.querySelector('[aria-label="Playhead seconds"]'),'2');
 await delay(100);
 await click('Split');
 await until(()=>document.querySelectorAll('.track:not(.audio-track) .clip').length===2,'split applied');
 assert.equal(last.project.clips[0].out,50);
 await click('Undo');
 await until(()=>document.querySelectorAll('.track:not(.audio-track) .clip').length===1,'undo visible');
 await click('Redo');
 await until(()=>document.querySelectorAll('.track:not(.audio-track) .clip').length===2,'redo visible');
 input(document.querySelector('#prompt'),'Trim selected clip from 0 to 1 seconds');
 await delay(100);
 await click('Send');
 await until(()=>document.body.textContent.includes('No change yet.'),'proposal visible');
 assert.equal(last.project.clips[0].out,50,'proposal must not mutate timeline');
 await click('Apply edit');
 await until(()=>last.project.clips[0].out===25,'proposal committed');
 assert.equal(last.pending.length,0);
 await until(()=>!document.body.textContent.includes('No change yet.'),'applied outcome visible');
 await click('Save');
 await until(()=>fs.existsSync(path.join(data,'UI.media')),'saved assets');
 await click('Open');
 await until(()=>document.body.textContent.includes('Trimmed source range to 0.00–1.00s.'),'history restored');
 input(document.querySelector('#prompt'),'Add Hinglish captions');
 await delay(100);
 await click('Send');
 await until(()=>document.body.textContent.includes('Add your OpenAI API key'),'unsupported prompt explained');
 await click('Effects & captions');
 await until(()=>document.querySelector('.tools-panel'),'tools visible');
 await click('Add manual caption');
 await until(()=>document.querySelector('[aria-label="Caption text"]'),'caption created');
 input(document.querySelector('[aria-label="Caption text"]'),'Yeh mera test hai');
 await delay(100);
 await click('Save caption');
 await until(()=>last.project.captions[0].text==='Yeh mera test hai','caption saved');
 await click('Settings');
 await until(()=>document.querySelector('[role="dialog"]'),'settings open');
 assert(document.querySelector('input[type=password]'));
 await click('Close');
 const report={manual_caption:true,caption_edit:true,settings_dialog:true,connection:true,selection:true,split:true,undo:true,redo:true,
  proposal_does_not_mutate:true,apply_once:true,save_reopen_history:true,unsupported_prompt_error:true,
  real_video_playback_tested:false,native_dialogs_tested:false};
 fs.writeFileSync(path.join(root,'verification','ui-dom-report.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
 dom.window.close();child.stdin.end();
})().catch(error=>{console.error(error);child.kill();process.exitCode=1});
