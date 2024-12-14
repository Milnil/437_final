import * as mobilenet from '@tensorflow-models/mobilenet';
import * as tf from '@tensorflow/tfjs';

let model;

self.onmessage = async (event) => {
  const { type, imageData } = event.data;

  if (type === 'loadModel') {
    try {
      await tf.setBackend('webgl');
      await tf.ready();
      model = await mobilenet.load();
      self.postMessage({ type: 'modelLoaded' });
    } catch (error) {
      console.error('Error loading model in worker:', error);
    }
  }

  if (type === 'classify' && model) {
    try {
      const imgTensor = tf.browser.fromPixels(imageData)
        .resizeNearestNeighbor([224, 224])
        .toFloat()
        .expandDims();

      const predictions = await model.classify(imgTensor);
      imgTensor.dispose();

      self.postMessage({ type: 'classificationResult', predictions });
    } catch (error) {
      console.error('Error during image classification in worker:', error);
    }
  }
};
