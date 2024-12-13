const canvas = document.getElementById('videoCanvas');
const ctx = canvas.getContext('2d');

let leftover = new Uint8Array(0);
const audioContext = new (window.AudioContext || window.webkitAudioContext)();

window.streamAPI.onData((newData) => {
  const combined = new Uint8Array(leftover.length + newData.length);
  combined.set(leftover, 0);
  combined.set(newData, leftover.length);

  let offset = 0;
  while (offset + 8 <= combined.length) {
    // Parse header
    let videoSize = (combined[offset]<<24) | (combined[offset+1]<<16) | (combined[offset+2]<<8) | combined[offset+3];
    let audioSize = (combined[offset+4]<<24) | (combined[offset+5]<<16) | (combined[offset+6]<<8) | combined[offset+7];
    let totalSize = 8 + videoSize + audioSize;

    if (offset + totalSize <= combined.length) {
      let videoData = combined.slice(offset+8, offset+8+videoSize);
      let audioData = combined.slice(offset+8+videoSize, offset+8+videoSize+audioSize);

      // Handle video
      let blob = new Blob([videoData], { type: 'image/jpeg' });
      let url = URL.createObjectURL(blob);
      let img = new Image();
      img.onload = function() {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
      };
      img.src = url;

      // Handle audio (PCM 16-bit mono 16kHz)
      let pcm16 = new Int16Array(audioData.buffer);
      let float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768;
      }
      let audioBuffer = audioContext.createBuffer(1, float32.length, 16000);
      audioBuffer.copyToChannel(float32, 0);
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.start();

      offset += totalSize;
    } else {
      // Not a complete packet yet
      break;
    }
  }

  leftover = combined.slice(offset);
});
