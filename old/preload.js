const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('streamAPI', {
  onData: (callback) => ipcRenderer.on('stream-data', (event, data) => callback(data))
});
