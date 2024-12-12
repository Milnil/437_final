class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(0);
    this.muted = false;

    this.port.onmessage = (event) => {
      const data = event.data;
      if (data.type === 'audio') {
        // Append new PCM float32 samples to the buffer
        let oldLen = this.buffer.length;
        let newBuffer = new Float32Array(oldLen + data.samples.length);
        newBuffer.set(this.buffer, 0);
        newBuffer.set(data.samples, oldLen);
        this.buffer = newBuffer;
      } else if (data.type === 'mute') {
        this.muted = data.value;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    const channelData = output[0];

    if (this.muted || this.buffer.length < channelData.length) {
      // If muted or not enough data available, fill with silence.
      channelData.fill(0);

      // If not muted but not enough data, we still must output silence to avoid glitches
      // (the missing samples will come later).
    } else {
      // We have enough data to fill this audio block
      channelData.set(this.buffer.slice(0, channelData.length));
      this.buffer = this.buffer.slice(channelData.length);
    }

    return true; // Keep processor alive
  }
}

registerProcessor('pcm-player', PCMPlayerProcessor);
