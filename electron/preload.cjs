const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('vibeflow',{
 call:(method,params)=>ipcRenderer.invoke('vibeflow',method,params),
 listen:callback=>{const listener=(_event,message)=>callback(message);ipcRenderer.on('backend-event',listener);
 return ()=>ipcRenderer.removeListener('backend-event',listener)}
});
