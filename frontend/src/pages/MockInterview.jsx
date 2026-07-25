import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Camera, Mic, MicOff, VideoOff } from 'lucide-react';
import { endInterview, sendMessage, startInterview } from '../api/client';

const SPEECH_PAUSE_THRESHOLD_MS = 1500;
const VISION_SAMPLE_INTERVAL_MS = 250;
const BRIGHTNESS_SAMPLE_INTERVAL_MS = 1500;
const VISION_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm';
const FACE_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
const POSE_MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

const defaultVisionAnalysis = {
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

function countSpeechUnits(text) {
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

function buildVisionAnalysis(faceResult, poseResult) {
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

export default function MockInterview() {
  const location = useLocation();
  const [resumeText, setResumeText] = useState(location.state?.resumeText || '');
  const [targetPosition, setTargetPosition] = useState(location.state?.targetPosition || '');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [scores, setScores] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [busy, setBusy] = useState(false);
  const [ended, setEnded] = useState(false);
  const [finalReport, setFinalReport] = useState(null);
  const [error, setError] = useState('');
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [lightingStatus, setLightingStatus] = useState('未检测');
  const [visionLoading, setVisionLoading] = useState(false);
  const [visionError, setVisionError] = useState('');
  const [visionAnalysis, setVisionAnalysis] = useState(defaultVisionAnalysis);
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [speechStats, setSpeechStats] = useState({
    durationSeconds: 0,
    units: 0,
    rate: 0,
    pauseCount: 0,
    longestPauseSeconds: 0,
  });
  const messagesEnd = useRef(null);
  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const brightnessTimerRef = useRef(null);
  const analysisFrameRef = useRef(null);
  const recognitionRef = useRef(null);
  const listeningRef = useRef(false);
  const speechStartedAtRef = useRef(null);
  const lastSpeechAtRef = useRef(null);
  const speechUnitsRef = useRef(0);
  const pauseCountRef = useRef(0);
  const longestPauseMsRef = useRef(0);
  const visionInitPromiseRef = useRef(null);
  const faceLandmarkerRef = useRef(null);
  const poseLandmarkerRef = useRef(null);
  const visionRunningRef = useRef(false);
  const lastVisionSampleRef = useRef(0);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => {
    stopSpeechRecognition();
    stopCamera();
  }, []);

  const averageScore = useMemo(() => {
    if (!scores.length) return null;
    return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length);
  }, [scores]);

  const updateSpeechStats = () => {
    const startedAt = speechStartedAtRef.current;
    if (!startedAt) return;
    const durationSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
    setSpeechStats({
      durationSeconds,
      units: speechUnitsRef.current,
      rate: Math.round((speechUnitsRef.current / durationSeconds) * 60),
      pauseCount: pauseCountRef.current,
      longestPauseSeconds: Number((longestPauseMsRef.current / 1000).toFixed(1)),
    });
  };

  const analyzeBrightness = () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return;

    const canvas = document.createElement('canvas');
    canvas.width = 80;
    canvas.height = 45;
    const context = canvas.getContext('2d');
    if (!context) return;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
    let total = 0;
    for (let index = 0; index < data.length; index += 4) {
      total += (data[index] + data[index + 1] + data[index + 2]) / 3;
    }

    const average = total / (data.length / 4);
    if (average < 55) {
      setLightingStatus('偏暗');
    } else if (average > 205) {
      setLightingStatus('偏亮');
    } else {
      setLightingStatus('正常');
    }
  };

  const ensureVisionModels = async () => {
    if (faceLandmarkerRef.current && poseLandmarkerRef.current) {
      return;
    }

    if (!visionInitPromiseRef.current) {
      visionInitPromiseRef.current = (async () => {
        const { FaceLandmarker, FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision');
        const vision = await FilesetResolver.forVisionTasks(VISION_WASM_URL);

        const createLandmarkers = delegate => Promise.all([
          FaceLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: FACE_MODEL_URL,
              delegate,
            },
            runningMode: 'VIDEO',
            numFaces: 1,
            outputFaceBlendshapes: true,
            outputFacialTransformationMatrixes: true,
          }),
          PoseLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: POSE_MODEL_URL,
              delegate,
            },
            runningMode: 'VIDEO',
            numPoses: 1,
          }),
        ]);

        let faceLandmarker;
        let poseLandmarker;
        try {
          [faceLandmarker, poseLandmarker] = await createLandmarkers('GPU');
        } catch {
          [faceLandmarker, poseLandmarker] = await createLandmarkers('CPU');
        }

        faceLandmarkerRef.current = faceLandmarker;
        poseLandmarkerRef.current = poseLandmarker;
      })().catch(error => {
        visionInitPromiseRef.current = null;
        throw error;
      });
    }

    return visionInitPromiseRef.current;
  };

  const runVisionAnalysis = () => {
    if (!visionRunningRef.current) return;

    analysisFrameRef.current = window.requestAnimationFrame(runVisionAnalysis);
    const video = videoRef.current;
    if (!video || video.readyState < 2) return;

    const now = performance.now();
    if (now - lastVisionSampleRef.current < VISION_SAMPLE_INTERVAL_MS) return;
    lastVisionSampleRef.current = now;

    const faceLandmarker = faceLandmarkerRef.current;
    const poseLandmarker = poseLandmarkerRef.current;
    if (!faceLandmarker || !poseLandmarker) return;

    try {
      const faceResult = faceLandmarker.detectForVideo(video, now);
      const poseResult = poseLandmarker.detectForVideo(video, now);
      setVisionAnalysis(buildVisionAnalysis(faceResult, poseResult));
      setVisionError('');
    } catch (analysisError) {
      visionRunningRef.current = false;
      if (analysisFrameRef.current) {
        window.cancelAnimationFrame(analysisFrameRef.current);
        analysisFrameRef.current = null;
      }
      setVisionError(analysisError.message || 'MediaPipe 分析失败');
    }
  };

  const startCamera = async () => {
    setCameraError('');
    setVisionError('');
    setVisionAnalysis(defaultVisionAnalysis);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 360, facingMode: 'user' },
        audio: false,
      });

      cameraStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      setCameraActive(true);

      if (brightnessTimerRef.current) {
        window.clearInterval(brightnessTimerRef.current);
      }
      brightnessTimerRef.current = window.setInterval(analyzeBrightness, BRIGHTNESS_SAMPLE_INTERVAL_MS);

      setVisionLoading(true);
      try {
        await ensureVisionModels();
        if (!visionRunningRef.current && cameraStreamRef.current) {
          visionRunningRef.current = true;
          lastVisionSampleRef.current = 0;
          analysisFrameRef.current = window.requestAnimationFrame(runVisionAnalysis);
        }
      } catch (visionLoadError) {
        setVisionError(visionLoadError.message || 'MediaPipe 模型加载失败');
      } finally {
        setVisionLoading(false);
      }
    } catch (requestError) {
      setCameraError(requestError.message || '摄像头开启失败');
      setCameraActive(false);
      setVisionLoading(false);
    }
  };

  const stopCamera = () => {
    visionRunningRef.current = false;
    if (analysisFrameRef.current) {
      window.cancelAnimationFrame(analysisFrameRef.current);
      analysisFrameRef.current = null;
    }

    if (brightnessTimerRef.current) {
      window.clearInterval(brightnessTimerRef.current);
      brightnessTimerRef.current = null;
    }

    cameraStreamRef.current?.getTracks().forEach(track => track.stop());
    cameraStreamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraActive(false);
    setVisionLoading(false);
    setLightingStatus('未检测');
    setVisionAnalysis(defaultVisionAnalysis);
  };

  const startSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      setError('当前浏览器不支持语音识别，请使用 Chrome 或 Edge。');
      return;
    }

    setSpeechSupported(true);
    setInterimTranscript('');
    speechStartedAtRef.current = Date.now();
    lastSpeechAtRef.current = null;
    speechUnitsRef.current = 0;
    pauseCountRef.current = 0;
    longestPauseMsRef.current = 0;
    updateSpeechStats();

    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = event => {
      let finalText = '';
      let interimText = '';

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0]?.transcript || '';
        if (event.results[index].isFinal) {
          finalText += transcript;
        } else {
          interimText += transcript;
        }
      }

      const now = Date.now();
      if (finalText.trim()) {
        const previousSpeechAt = lastSpeechAtRef.current;
        if (previousSpeechAt && now - previousSpeechAt > SPEECH_PAUSE_THRESHOLD_MS) {
          pauseCountRef.current += 1;
          longestPauseMsRef.current = Math.max(longestPauseMsRef.current, now - previousSpeechAt);
        }
        lastSpeechAtRef.current = now;
        speechUnitsRef.current += countSpeechUnits(finalText);
        setInput(current => `${current}${current ? ' ' : ''}${finalText.trim()}`);
      }

      setInterimTranscript(interimText.trim());
      updateSpeechStats();
    };

    recognition.onerror = event => {
      setError(`语音识别异常：${event.error || 'unknown'}`);
    };

    recognition.onend = () => {
      if (listeningRef.current) {
        try {
          recognition.start();
        } catch {
          listeningRef.current = false;
          setListening(false);
        }
      }
    };

    recognitionRef.current = recognition;
    listeningRef.current = true;
    setListening(true);
    try {
      recognition.start();
    } catch (requestError) {
      listeningRef.current = false;
      setListening(false);
      setError(requestError.message || '语音识别启动失败');
    }
  };

  const stopSpeechRecognition = () => {
    listeningRef.current = false;
    setListening(false);
    setInterimTranscript('');
    try {
      recognitionRef.current?.stop();
    } catch {
      // Ignore repeated stop calls from browser recognition implementations.
    }
    recognitionRef.current = null;
    updateSpeechStats();
  };

  const handleStart = async () => {
    if (!resumeText.trim()) {
      setError('请先输入简历文本');
      return;
    }

    setBusy(true);
    setError('');
    try {
      const result = await startInterview({
        resumeText: resumeText.trim(),
        targetPosition: targetPosition.trim(),
        targetJobId: location.state?.targetJobId || null,
      });

      setSessionId(result.session_id);
      setMessages([
        {
          role: 'interviewer',
          content: `第 1/${result.total_questions || 8} 题：${result.question}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (requestError) {
      setError(requestError.message || '面试启动失败');
    } finally {
      setBusy(false);
    }
  };

  const handleSend = async () => {
    const answer = input.trim();
    if (!answer || busy || !sessionId || ended) return;

    setMessages(current => [...current, { role: 'user', content: answer, timestamp: new Date().toISOString() }]);
    setInput('');
    setBusy(true);
    setError('');
    try {
      const result = await sendMessage(sessionId, answer);
      if (typeof result.score === 'number') {
        setScores(current => [...current, result.score]);
      }
      if (result.feedback) {
        setFeedback(current => [...current, result.feedback]);
      }

      const responseText = result.is_followup
        ? `追问：${result.followup_question || result.next_question}`
        : `${result.feedback || ''}${result.next_question ? `\n\n第 ${(result.current_index || 0) + 1}/${result.total_questions || 8} 题：${result.next_question}` : '\n\n本轮题目已完成，可以点击“结束面试”生成报告。'}`;

      setMessages(current => [...current, {
        role: 'interviewer',
        content: responseText.trim(),
        timestamp: new Date().toISOString(),
      }]);
    } catch (requestError) {
      setError(requestError.message || '回答提交失败');
    } finally {
      setBusy(false);
    }
  };

  const handleEnd = async () => {
    if (!sessionId || busy) return;

    setBusy(true);
    setError('');
    try {
      const report = await endInterview(sessionId);
      setFinalReport(report);
      setEnded(true);
    } catch (requestError) {
      setError(requestError.message || '面试报告生成失败');
    } finally {
      setBusy(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="page interview-page">
        <h2>模拟面试</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="card">
          <div className="form-grid">
            <div className="form-group form-group-full">
              <label>目标岗位</label>
              <input
                value={targetPosition}
                onChange={event => setTargetPosition(event.target.value)}
                placeholder="如：Python 后端工程师"
              />
            </div>
            <div className="form-group form-group-full">
              <label>简历文本 *</label>
              <textarea
                value={resumeText}
                onChange={event => setResumeText(event.target.value)}
                rows={10}
                placeholder="粘贴简历文本"
              />
            </div>
            <div className="form-group form-group-full form-actions">
              <button className="btn btn-primary" onClick={handleStart} disabled={busy}>
                {busy ? '生成问题中...' : '开始面试'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page interview-page">
      <div className="interview-header">
        <div>
          <h2>模拟面试</h2>
          <span className="text-muted">{location.state?.jobInfo?.company || '目标岗位'} - {targetPosition || '综合面试'}</span>
        </div>
        {!ended && (
          <button className="btn btn-danger" onClick={handleEnd} disabled={busy}>
            {busy ? '生成报告中...' : '结束面试'}
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      <div className="interview-assist-panel">
        <div className="assist-card camera-card">
          <div className="assist-card-header">
            <div>
              <h3>摄像头</h3>
              <span className="text-muted">预览与视线、姿态分析</span>
            </div>
            <button
              className="btn btn-sm btn-outline"
              onClick={cameraActive ? stopCamera : startCamera}
              type="button"
            >
              {cameraActive ? <VideoOff size={16} /> : <Camera size={16} />}
              {cameraActive ? '关闭' : '开启'}
            </button>
          </div>

          <div className={`camera-preview ${cameraActive ? 'active' : ''}`}>
            <video ref={videoRef} autoPlay playsInline muted />
            {!cameraActive && <span>摄像头未开启</span>}
          </div>

          {cameraError && <div className="assist-warning">{cameraError}</div>}
          {visionError && <div className="assist-warning">{visionError}</div>}

          <div className="assist-metrics">
            <span>画面亮度：{lightingStatus}</span>
            <span>模型状态：{visionLoading ? '加载中' : visionError ? '异常' : cameraActive ? '已就绪' : '未启动'}</span>
            <span>视线：{visionAnalysis.gazeLabel}</span>
            <span>头部：{visionAnalysis.headPoseLabel}</span>
            <span>姿态：{visionAnalysis.postureLabel}</span>
            <span>专注度：{visionAnalysis.attentionLabel} {visionAnalysis.attentionScore ? `${visionAnalysis.attentionScore} 分` : ''}</span>
          </div>

          <ul className="vision-advice">
            {visionAnalysis.advice.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </div>

        <div className="assist-card voice-card">
          <div className="assist-card-header">
            <div>
              <h3>语音输入</h3>
              <span className="text-muted">转写、语速和停顿统计</span>
            </div>
            <button
              className="btn btn-sm btn-outline"
              onClick={listening ? stopSpeechRecognition : startSpeechRecognition}
              type="button"
            >
              {listening ? <MicOff size={16} /> : <Mic size={16} />}
              {listening ? '停止' : '开始'}
            </button>
          </div>

          {!speechSupported && <div className="assist-warning">当前浏览器不支持语音识别</div>}
          <div className="assist-metrics voice-metrics">
            <span>时长：{speechStats.durationSeconds}s</span>
            <span>字数：{speechStats.units}</span>
            <span>语速：{speechStats.rate} 字/分钟</span>
            <span>停顿：{speechStats.pauseCount} 次</span>
            <span>最长停顿：{speechStats.longestPauseSeconds}s</span>
          </div>
          <div className="interim-transcript">
            {interimTranscript || '语音转写会自动填入回答框'}
          </div>
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((message, index) => (
            <div key={`${message.timestamp}-${index}`} className={`chat-message ${message.role}`}>
              <div className="chat-bubble">
                <div className="chat-role">{message.role === 'interviewer' ? 'AI 面试官' : '你'}</div>
                <div className="chat-content" style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
                <div className="chat-time">{new Date(message.timestamp).toLocaleTimeString()}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEnd} />
        </div>

        {!ended && (
          <div className="chat-input-area">
            <input
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => event.key === 'Enter' && handleSend()}
              placeholder="输入你的回答"
              disabled={busy}
            />
            <button className="btn btn-primary" onClick={handleSend} disabled={busy || !input.trim()}>
              {busy ? '分析中...' : '提交回答'}
            </button>
          </div>
        )}
      </div>

      {ended && (
        <div className="card interview-result">
          <h3>本次面试小结</h3>
          <p><strong>平均得分：</strong>{finalReport?.overall_score ?? averageScore ?? '尚未完成作答'}</p>
          {finalReport?.summary && <p>{finalReport.summary}</p>}
          {feedback.length > 0 && (
            <ul>{feedback.map((item, index) => <li key={index}>{item}</li>)}</ul>
          )}
          {finalReport?.star_suggestions?.length > 0 && (
            <>
              <h4>STAR 改写建议</h4>
              <ul>
                {finalReport.star_suggestions.map((item, index) => (
                  <li key={index}>
                    <strong>{item.question}</strong>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{item.star_rewrite}</p>
                  </li>
                ))}
              </ul>
            </>
          )}
          {finalReport?.practice_plan && (
            <>
              <h4>下一步练习计划</h4>
              <p style={{ whiteSpace: 'pre-wrap' }}>{finalReport.practice_plan}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
