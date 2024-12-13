const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const net = require('net');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true // recommended for security
    }
  });

  mainWindow.loadURL('file://' + __dirname + '/index.html');
}

app.whenReady().then(createWindow);

// Connect to the Pi's TCP server
const tcpHost = '192.168.10.59'; // Pi's IP
const tcpPort = 65434;           // TCP server port
const client = net.createConnection({ host: tcpHost, port: tcpPort }, () => {
  console.log('Connected to TCP server');
});

// Forward data from the TCP server to renderer
client.on('data', (data) => {
  if (mainWindow) {
    mainWindow.webContents.send('stream-data', data);
  }
});

client.on('error', (err) => {
  console.error('TCP error:', err);
});
