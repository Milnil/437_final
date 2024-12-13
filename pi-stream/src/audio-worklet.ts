class AudioStreamProcessor extends AudioWorkletProcessor {
  process(inputs: Float32Array[][], outputs: Float32Array[][], parameters: Record<string, Float32Array>) {
    const output = outputs[0];
    const input = inputs[0];

    for (let channel = 0; channel < output.length; ++channel) {
      const outputChannel = output[channel];
      const inputChannel = input[channel];
      
      if (inputChannel) {
        outputChannel.set(inputChannel);
      }
    }

    return true;
  }
}

registerProcessor('audio-stream-processor', AudioStreamProcessor); 