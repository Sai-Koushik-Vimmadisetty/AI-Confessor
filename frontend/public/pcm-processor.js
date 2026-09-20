/* AudioWorklet processor: forwards raw float32 mono samples to the main thread.
   Loaded via audioWorklet.addModule('/pcm-processor.js'). */
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input.length > 0 && input[0].length > 0) {
      // Copy the buffer — the underlying memory is reused by the audio thread.
      this.port.postMessage(input[0].slice(0));
    }
    return true; // keep alive
  }
}

registerProcessor('pcm-processor', PCMProcessor);
