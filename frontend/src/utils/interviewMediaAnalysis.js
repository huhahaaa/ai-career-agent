export const SPEECH_PAUSE_THRESHOLD_MS = 1500;
export const VISION_SAMPLE_INTERVAL_MS = 250;
export const BRIGHTNESS_SAMPLE_INTERVAL_MS = 1500;
export const VISION_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm';
export const FACE_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
export const POSE_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
export const INTERVIEW_MODES = ['技术面', 'HR面', '压力面', '反馈教练'];

export const defaultVisionAnalysis = {
  faceDetected: false,
  poseDetected: false,
  gazeLabel: '未检测',
  headPoseLabel: '未检测',
  postureLabel: '未检测',
  attentionLabel: '待检测',
  attentionScore: 0,
  headTilt: 0,
  shoulderTilt: 0,
  torsoOffset: 0,
  advice: ['开启摄像头后，视线和姿态会自动分析。'],
  lastUpdated: '',
};

export function countSpeechUnits(text) {
  const chineseChars = text.match(/[\u4e00-\u9fa5]/g)?.length || 0;
  const latinWords = text.match(/[A-Za-z0-9_]+/g)?.length || 0;
  return chineseChars + latinWords;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function distance(a, b) {
  return Math.hypot((a?.x || 0) - (b?.x || 0), (a?.y || 0) - (b?.y || 0));
}

function midpoint(a, b) {
  if (!a || !b) return null;
  return {
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
    z: ((a.z ?? 0) + (b.z ?? 0)) / 2,
  };
}

function averagePoint(points) {
  const validPoints = points.filter(Boolean);
  if (!validPoints.length) return null;
  const total = validPoints.reduce(
    (acc, point) => {
      acc.x += point.x;
      acc.y += point.y;
      acc.z += point.z ?? 0;
      return acc;
    },
    { x: 0, y: 0, z: 0 },
  );
  return {
    x: total.x / validPoints.length,
    y: total.y / validPoints.length,
    z: total.z / validPoints.length,
  };
}

function analyzeGaze(faceLandmarks) {
  const eyeSpecs = [
    { corners: [33, 133], iris: [468, 469, 470, 471, 472] },
    { corners: [362, 263], iris: [473, 474, 475, 476, 477] },
  ];

  const ratios = eyeSpecs
    .map(({ corners, iris }) => {
      const cornerA = faceLandmarks[corners[0]];
      const cornerB = faceLandmarks[corners[1]];
      const irisCenter = averagePoint(iris.map(index => faceLandmarks[index]));
      if (!cornerA || !cornerB || !irisCenter) return null;

      const minX = Math.min(cornerA.x, cornerB.x);
      const maxX = Math.max(cornerA.x, cornerB.x);
      const width = Math.max(0.001, maxX - minX);
      return clamp((irisCenter.x - minX) / width, 0, 1);
    })
    .filter(value => value !== null);

  let average = 0.5;
  let source = 'iris';

  if (ratios.length) {
    average = ratios.reduce((sum, value) => sum + value, 0) / ratios.length;
  } else {
    const leftEye = faceLandmarks[33];
    const rightEye = faceLandmarks[263];
    const nose = faceLandmarks[1] || faceLandmarks[4];
    if (!leftEye || !rightEye || !nose) {
      return { label: '未检测', average, source: 'unknown' };
    }
    const eyeMid = midpoint(leftEye, rightEye);
    const eyeDistance = Math.max(distance(leftEye, rightEye), 0.001);
    average = clamp(0.5 + ((nose.x - eyeMid.x) * 2.2) / eyeDistance, 0, 1);
    source = 'fallback';
  }

  if (average < 0.38) {
    return { label: '偏左', average, source };
  }
  if (average > 0.62) {
    return { label: '偏右', average, source };
  }
  return { label: '居中', average, source };
}

function analyzeHeadPose(faceLandmarks) {
  const leftEye = faceLandmarks[33];
  const rightEye = faceLandmarks[263];
  const nose = faceLandmarks[1] || faceLandmarks[4] || faceLandmarks[168];

  if (!leftEye || !rightEye || !nose) {
    return { label: '未检测', roll: 0, yaw: 0, pitch: 0 };
  }

  const eyeMid = midpoint(leftEye, rightEye);
  const eyeDistance = Math.max(distance(leftEye, rightEye), 0.001);
  const roll = (Math.atan2(rightEye.y - leftEye.y, rightEye.x - leftEye.x) * 180) / Math.PI;
  const yaw = (nose.x - eyeMid.x) / eyeDistance;
  const pitch = (nose.y - eyeMid.y) / eyeDistance;

  let label = '正对';
  if (Math.abs(roll) > 10) {
    label = roll > 0 ? '头部右倾' : '头部左倾';
  } else if (yaw < -0.13) {
    label = '偏左';
  } else if (yaw > 0.13) {
    label = '偏右';
  } else if (pitch > 0.18) {
    label = '低头';
  } else if (pitch < -0.05) {
    label = '抬头';
  }

  return { label, roll, yaw, pitch };
}

function analyzePosture(poseLandmarks) {
  const leftShoulder = poseLandmarks[11];
  const rightShoulder = poseLandmarks[12];
  const leftHip = poseLandmarks[23];
  const rightHip = poseLandmarks[24];

  if (!leftShoulder || !rightShoulder || !leftHip || !rightHip) {
    return { label: '未检测', shoulderTilt: 0, hipTilt: 0, torsoOffset: 0, leanAngle: 0 };
  }

  const shoulderMid = midpoint(leftShoulder, rightShoulder);
  const hipMid = midpoint(leftHip, rightHip);
  const torsoDistance = Math.max(distance(shoulderMid, hipMid), 0.001);
  const shoulderTilt = (Math.atan2(rightShoulder.y - leftShoulder.y, rightShoulder.x - leftShoulder.x) * 180) / Math.PI;
  const hipTilt = (Math.atan2(rightHip.y - leftHip.y, rightHip.x - leftHip.x) * 180) / Math.PI;
  const torsoOffset = (shoulderMid.x - hipMid.x) / torsoDistance;
  const leanAngle = (Math.atan2(shoulderMid.x - hipMid.x, hipMid.y - shoulderMid.y) * 180) / Math.PI;

  let label = '坐姿端正';
  if (Math.abs(shoulderTilt) > 9) {
    label = shoulderTilt > 0 ? '右肩偏高' : '左肩偏高';
  } else if (Math.abs(torsoOffset) > 0.12) {
    label = torsoOffset > 0 ? '身体偏右' : '身体偏左';
  } else if (Math.abs(leanAngle) > 9) {
    label = leanAngle > 0 ? '上身右倾' : '上身左倾';
  }

  return { label, shoulderTilt, hipTilt, torsoOffset, leanAngle };
}

function buildVisionAdvice({ faceDetected, poseDetected, gazeLabel, headPoseLabel, postureLabel }) {
  const advice = [];

  if (!faceDetected) {
    advice.push('请让脸部完整进入摄像头画面，并尽量保持正对镜头。');
  } else {
    if (gazeLabel !== '居中') {
      advice.push('请把视线拉回镜头附近，减少频繁看向两侧。');
    }
    if (headPoseLabel !== '正对') {
      advice.push('请保持头部端正，避免明显歪头或低头。');
    }
  }

  if (!poseDetected) {
    advice.push('请让上半身也进入画面，方便分析姿态。');
  } else if (postureLabel !== '坐姿端正') {
    advice.push('请把肩膀放平，坐姿尽量稳定。');
  }

  if (!advice.length) {
    advice.push('当前视线和姿态较稳定，可以继续面试。');
  }

  return advice.slice(0, 3);
}

function buildAttentionScore({ faceDetected, poseDetected, gazeLabel, headPoseLabel, postureLabel }) {
  if (!faceDetected) return 0;

  let score = 100;
  if (gazeLabel !== '居中') score -= 18;
  if (headPoseLabel !== '正对') score -= 16;
  if (poseDetected && postureLabel !== '坐姿端正') score -= 14;
  if (!poseDetected) score -= 8;
  return clamp(Math.round(score), 0, 100);
}

export function buildVisionAnalysis(faceResult, poseResult) {
  const faceLandmarks = faceResult?.faceLandmarks?.[0] || [];
  const poseLandmarks = poseResult?.poseLandmarks?.[0] || [];
  const faceDetected = faceLandmarks.length > 0;
  const poseDetected = poseLandmarks.length > 0;
  const gaze = faceDetected ? analyzeGaze(faceLandmarks) : { label: '未检测', average: 0.5, source: 'unknown' };
  const headPose = faceDetected ? analyzeHeadPose(faceLandmarks) : { label: '未检测', roll: 0, yaw: 0, pitch: 0 };
  const posture = poseDetected ? analyzePosture(poseLandmarks) : { label: '未检测', shoulderTilt: 0, hipTilt: 0, torsoOffset: 0, leanAngle: 0 };
  const attentionScore = buildAttentionScore({
    faceDetected,
    poseDetected,
    gazeLabel: gaze.label,
    headPoseLabel: headPose.label,
    postureLabel: posture.label,
  });

  return {
    faceDetected,
    poseDetected,
    gazeLabel: gaze.label,
    headPoseLabel: headPose.label,
    postureLabel: posture.label,
    attentionLabel: attentionScore >= 85 ? '良好' : attentionScore >= 70 ? '正常' : attentionScore >= 50 ? '需调整' : '注意',
    attentionScore,
    headTilt: Number(headPose.roll.toFixed(1)),
    shoulderTilt: Number(posture.shoulderTilt.toFixed(1)),
    torsoOffset: Number(posture.torsoOffset.toFixed(2)),
    advice: buildVisionAdvice({
      faceDetected,
      poseDetected,
      gazeLabel: gaze.label,
      headPoseLabel: headPose.label,
      postureLabel: posture.label,
    }),
    lastUpdated: new Date().toLocaleTimeString(),
  };
}
