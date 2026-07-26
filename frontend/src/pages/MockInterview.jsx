import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Camera, Mic, MicOff, VideoOff, Volume2, VolumeX } from 'lucide-react';
import { endInterview, getResumeDetail, getResumes, sendMessage, startInterview } from '../api/client';
import RadarChart from '../components/RadarChart';
import { mapDimensionScores } from '../utils/dimensionLabels';

import {
  BRIGHTNESS_SAMPLE_INTERVAL_MS,
  FACE_MODEL_URL,
  INTERVIEW_MODES,
  POSE_MODEL_URL,
  SPEECH_PAUSE_THRESHOLD_MS,
  VISION_SAMPLE_INTERVAL_MS,
  VISION_WASM_URL,
  buildVisionAnalysis,
  countSpeechUnits,
  defaultVisionAnalysis,
} from '../utils/interviewMediaAnalysis';

export default function MockInterview() {
  const location = useLocation();
  const [resumeText, setResumeText] = useState(location.state?.resumeText || '');
  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState(location.state?.resumeId ? String(location.state.resumeId) : '');
  const [resumeLoading, setResumeLoading] = useState(false);
  const [targetPosition, setTargetPosition] = useState(location.state?.targetPosition || '');
  const [interviewMode, setInterviewMode] = useState(location.state?.interviewMode || '技术面');
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
  const [speechStatus, setSpeechStatus] = useState('未启动');
  const [micLevel, setMicLevel] = useState(0);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(true);
  const [voiceOutputStatus, setVoiceOutputStatus] = useState('待朗读');
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
  const microphoneStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioLevelFrameRef = useRef(null);
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
  const lastSpokenMessageRef = useRef('');

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const speakInterviewerText = text => {
    if (!voiceOutputEnabled || !window.speechSynthesis || !text?.trim()) return;
    const cleaned = text
      .replace(/【[^】]+】/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!cleaned) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleaned);
    utterance.lang = 'zh-CN';
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.onstart = () => setVoiceOutputStatus('面试官正在朗读');
    utterance.onend = () => setVoiceOutputStatus('朗读完成');
    utterance.onerror = () => setVoiceOutputStatus('朗读失败，可继续文字面试');
    window.speechSynthesis.speak(utterance);
  };

  useEffect(() => {
    if (!messages.length || ended) return;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage.role !== 'interviewer') return;
    const key = `${lastMessage.timestamp}-${lastMessage.content}`;
    if (lastSpokenMessageRef.current === key) return;
    lastSpokenMessageRef.current = key;
    speakInterviewerText(lastMessage.content);
  }, [messages, ended, voiceOutputEnabled]);

  useEffect(() => {
    getResumes()
      .then(data => {
        const list = data || [];
        setResumes(list);
        const defaultResume = list.find(item => item.is_default) || list[0];
        if (!selectedResumeId && defaultResume && !resumeText.trim()) {
          setSelectedResumeId(String(defaultResume.id));
        }
      })
      .catch(() => setResumes([]));
  }, []);

  useEffect(() => {
    if (!selectedResumeId) return;
    setResumeLoading(true);
    setError('');
    getResumeDetail(selectedResumeId)
      .then(detail => {
        const versions = detail?.versions || [];
        const version = versions[versions.length - 1];
        setResumeText(version?.content || '');
      })
      .catch(error => setError(error.message || '简历正文加载失败'))
      .finally(() => setResumeLoading(false));
  }, [selectedResumeId]);

  useEffect(() => () => {
    stopSpeechRecognition();
    window.speechSynthesis?.cancel();
    stopCamera();
  }, []);

  const averageScore = useMemo(() => {
    if (!scores.length) return null;
    return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length);
  }, [scores]);

  const reportDimensionData = useMemo(() => {
    const dimensionScores = finalReport?.dimension_averages || {};
    return mapDimensionScores(dimensionScores).filter(item => item.originalName !== 'total');
  }, [finalReport]);

  const speechCoachTip = useMemo(() => {
    if (!listening && speechStats.durationSeconds === 0) return '';
    if (speechStats.rate > 220) return '语速偏快，建议放慢并留出重点停顿。';
    if (speechStats.longestPauseSeconds >= 5) return '停顿偏长，建议先用一句话概括再展开细节。';
    if (speechStats.pauseCount >= 4) return '停顿较多，建议按“背景-行动-结果”组织回答。';
    if (speechStats.rate >= 90 && speechStats.rate <= 200 && speechStats.units > 20) {
      return '语速较稳定，可以继续保持。';
    }
    return '';
  }, [listening, speechStats]);

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

  const stopMicrophoneLevel = () => {
    if (audioLevelFrameRef.current) {
      window.cancelAnimationFrame(audioLevelFrameRef.current);
      audioLevelFrameRef.current = null;
    }
    microphoneStreamRef.current?.getTracks().forEach(track => track.stop());
    microphoneStreamRef.current = null;
    audioContextRef.current?.close?.().catch(() => {});
    audioContextRef.current = null;
    setMicLevel(0);
  };

  const startMicrophoneLevel = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setSpeechStatus('浏览器不支持麦克风权限检测');
      return;
    }

    stopMicrophoneLevel();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    microphoneStreamRef.current = stream;

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      setSpeechStatus('已取得麦克风权限，但无法读取音量');
      return;
    }

    const audioContext = new AudioContextClass();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    audioContext.createMediaStreamSource(stream).connect(analyser);
    audioContextRef.current = audioContext;
    const data = new Uint8Array(analyser.fftSize);

    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let index = 0; index < data.length; index += 1) {
        const centered = data[index] - 128;
        sum += centered * centered;
      }
      const rms = Math.sqrt(sum / data.length);
      const nextLevel = Math.min(100, Math.round(rms * 6));
      setMicLevel(nextLevel);
      if (nextLevel > 6 && listeningRef.current) {
        setSpeechStatus(current => (
          current.includes('转写') || current.includes('写入') ? current : '麦克风有输入，等待转写结果'
        ));
      }
      audioLevelFrameRef.current = window.requestAnimationFrame(tick);
    };

    tick();
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

  const startSpeechRecognition = async () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      setSpeechStatus('当前浏览器不支持语音识别');
      setError('当前浏览器不支持语音识别，请使用 Chrome 或 Edge。');
      return;
    }

    setSpeechSupported(true);
    setError('');
    setSpeechStatus('正在请求麦克风权限...');
    try {
      await startMicrophoneLevel();
    } catch (permissionError) {
      setSpeechStatus('麦克风权限不可用');
      setError(permissionError.message || '麦克风权限被拒绝或设备不可用');
      return;
    }

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

    recognition.onstart = () => {
      setSpeechStatus('正在监听，请开始说话');
    };

    recognition.onaudiostart = () => {
      setSpeechStatus('检测到麦克风输入');
    };

    recognition.onspeechstart = () => {
      setSpeechStatus('检测到讲话，正在转写');
    };

    recognition.onspeechend = () => {
      setSpeechStatus('讲话结束，等待转写结果');
    };

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
      setSpeechStatus(finalText.trim() ? '已写入回答框' : interimText.trim() ? '正在转写' : '正在监听');
      updateSpeechStats();
    };

    recognition.onnomatch = () => {
      setSpeechStatus('没有识别到明确内容');
    };

    recognition.onerror = event => {
      const messages = {
        'no-speech': '没有检测到讲话，请靠近麦克风或提高音量',
        'audio-capture': '没有检测到可用麦克风',
        'not-allowed': '麦克风权限被拒绝',
        'service-not-allowed': '浏览器语音识别服务不可用',
        network: '语音识别网络服务不可用',
        aborted: '语音识别已中断',
      };
      const message = messages[event.error] || `语音识别异常：${event.error || 'unknown'}`;
      setSpeechStatus(message);
      setError(message);
      if (['not-allowed', 'service-not-allowed', 'audio-capture'].includes(event.error)) {
        listeningRef.current = false;
        setListening(false);
        stopMicrophoneLevel();
      }
    };

    recognition.onend = () => {
      if (listeningRef.current) {
        try {
          setSpeechStatus('识别暂停，正在重新监听');
          recognition.start();
        } catch {
          listeningRef.current = false;
          setListening(false);
          setSpeechStatus('语音识别已停止');
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
      stopMicrophoneLevel();
      setSpeechStatus('语音识别启动失败');
      setError(requestError.message || '语音识别启动失败');
    }
  };

  const stopSpeechRecognition = () => {
    const pendingTranscript = interimTranscript.trim();
    if (pendingTranscript) {
      speechUnitsRef.current += countSpeechUnits(pendingTranscript);
      setInput(current => `${current}${current ? ' ' : ''}${pendingTranscript}`);
    }
    listeningRef.current = false;
    setListening(false);
    setSpeechStatus('已停止');
    setInterimTranscript('');
    try {
      recognitionRef.current?.stop();
    } catch {
      // Ignore repeated stop calls from browser recognition implementations.
    }
    recognitionRef.current = null;
    stopMicrophoneLevel();
    updateSpeechStats();
  };

  const toggleVoiceOutput = () => {
    setVoiceOutputEnabled(current => {
      const next = !current;
      if (!next) {
        window.speechSynthesis?.cancel();
        setVoiceOutputStatus('已关闭');
      } else {
        setVoiceOutputStatus('已开启，下一题将自动朗读');
      }
      return next;
    });
  };

  const repeatLastInterviewerMessage = () => {
    const lastInterviewerMessage = [...messages].reverse().find(message => message.role === 'interviewer');
    if (!lastInterviewerMessage) return;
    speakInterviewerText(lastInterviewerMessage.content);
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
        resumeId: selectedResumeId || null,
        targetPosition: targetPosition.trim(),
        targetJobId: location.state?.targetJobId || null,
        interviewMode,
      });

      setSessionId(result.session_id);
      setInterviewMode(result.interview_mode || interviewMode);
      setMessages([
        {
          role: 'interviewer',
          content: `【${result.interview_mode || interviewMode}】第 1/${result.total_questions || 8} 题：${result.question}`,
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

      setMessages(current => {
        const updated = [...current];
        for (let index = updated.length - 1; index >= 0; index -= 1) {
          if (updated[index].role === 'user' && updated[index].score == null) {
            updated[index] = {
              ...updated[index],
              score: typeof result.score === 'number' ? result.score : undefined,
              feedback: result.feedback || '',
              strengths: result.strengths || '',
              issues: result.issues || '',
              improvementSuggestions: result.improvement_suggestions || '',
            };
            break;
          }
        }
        return [...updated, {
          role: 'interviewer',
          content: responseText.trim(),
          timestamp: new Date().toISOString(),
        }];
      });
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
              <label>面试模式</label>
              <select value={interviewMode} onChange={event => setInterviewMode(event.target.value)}>
                {INTERVIEW_MODES.map(mode => (
                  <option key={mode} value={mode}>{mode}</option>
                ))}
              </select>
            </div>
            <div className="form-group form-group-full">
              <label>使用已有简历</label>
              <select
                value={selectedResumeId}
                onChange={event => setSelectedResumeId(event.target.value)}
              >
                <option value="">手动粘贴简历文本</option>
                {resumes.map(item => (
                  <option key={item.id} value={item.id}>
                    {item.is_default ? '默认 - ' : ''}{item.filename}（v{item.version}）
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group form-group-full">
              <label>简历文本 *</label>
              <textarea
                value={resumeText}
                onChange={event => {
                  setResumeText(event.target.value);
                  if (selectedResumeId) setSelectedResumeId('');
                }}
                rows={10}
                placeholder={resumeLoading ? '正在加载简历正文...' : '粘贴简历文本'}
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
          <span className="text-muted">{location.state?.jobInfo?.company || '目标岗位'} - {targetPosition || '综合面试'} - {interviewMode}</span>
        </div>
        <div className="interview-header-actions">
          <button className="btn btn-sm btn-outline" onClick={toggleVoiceOutput} type="button">
            {voiceOutputEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            {voiceOutputEnabled ? '朗读开启' : '朗读关闭'}
          </button>
          {!ended && (
            <button className="btn btn-danger" onClick={handleEnd} disabled={busy}>
              {busy ? '生成报告中...' : '结束面试'}
            </button>
          )}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      <div className="interview-room">
        <section className="interview-stage">
          <div className="assist-card camera-card immersive-camera-card">
          <div className="assist-card-header">
            <div>
              <h3>候选人画面</h3>
              <span className="text-muted">摄像头分析开启后会在面试中给出轻量提醒</span>
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

          <div className="assist-metrics compact-camera-metrics">
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

          <div className="interview-live-coach">
            <div>
              <strong>语音状态</strong>
              <span>{listening ? speechStatus : '点击回答框旁的麦克风开始语音输入'}</span>
            </div>
            <div>
              <strong>面试官语音</strong>
              <span>{voiceOutputEnabled ? voiceOutputStatus : '已关闭'}</span>
            </div>
            {speechCoachTip && <p>{speechCoachTip}</p>}
          </div>
        </section>

        <section className="interview-console">
          <div className="chat-container immersive-chat-container">
            <div className="chat-panel-top">
              <div>
                <strong>AI 面试官</strong>
                <span>{voiceOutputEnabled ? voiceOutputStatus : '文字面试模式'}</span>
              </div>
              <div className="chat-panel-actions">
                <button className="btn btn-sm btn-outline" type="button" onClick={repeatLastInterviewerMessage}>
                  <Volume2 size={15} />
                  重读题目
                </button>
                <div className="speech-compact-status">
                  <span className={listening ? 'recording-dot active' : 'recording-dot'} />
                  {listening ? speechStatus : '语音未启动'}
                </div>
              </div>
            </div>
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="empty">当前面试题目未显示，请刷新页面后重新开始一次面试。</div>
          )}
          {messages.map((message, index) => (
            <div key={`${message.timestamp}-${index}`} className={`chat-message ${message.role}`}>
              <div className="chat-bubble">
                <div className="chat-role">{message.role === 'interviewer' ? 'AI 面试官' : '你'}</div>
                {message.role === 'user' && typeof message.score === 'number' && (
                  <div className="chat-score-badge">{message.score} 分</div>
                )}
                <div className="chat-content" style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
                {message.role === 'user' && message.feedback && (
                  <div className="chat-feedback-hint">
                    <strong>反馈：</strong>{message.feedback}
                    {message.strengths && <span> 优点：{message.strengths}</span>}
                    {message.issues && <span> 问题：{message.issues}</span>}
                    {message.improvementSuggestions && <span> 建议：{message.improvementSuggestions}</span>}
                  </div>
                )}
                <div className="chat-time">{new Date(message.timestamp).toLocaleTimeString()}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEnd} />
        </div>

        {!ended && (
          <div className="chat-input-area">
            <button
              className={`voice-input-button ${listening ? 'active' : ''}`}
              onClick={listening ? stopSpeechRecognition : startSpeechRecognition}
              type="button"
              title={listening ? '停止语音输入' : '开始语音输入'}
              aria-label={listening ? '停止语音输入' : '开始语音输入'}
            >
              {listening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
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
            <div className="speech-inline-panel">
              <div className="mic-level" aria-label="麦克风音量">
                <div className="mic-level-bar" style={{ width: `${micLevel}%` }} />
              </div>
              <span>{interimTranscript || (listening ? '正在等待转写结果，可继续说话' : '语音会写入回答框，可手动修改后提交')}</span>
            </div>
          </div>
        )}
          </div>
        </section>
      </div>

      {ended && (
        <div className="card interview-result">
          <h3>本次面试小结</h3>
          <p><strong>面试模式：</strong>{finalReport?.interview_mode || interviewMode}</p>
          <p><strong>平均得分：</strong>{finalReport?.overall_score ?? averageScore ?? '尚未完成作答'}</p>
          {finalReport?.summary && <p>{finalReport.summary}</p>}
          {reportDimensionData.length > 0 && (
            <div className="result-radar-section">
              <h4>能力维度评估</h4>
              <RadarChart data={reportDimensionData} height={260} />
              <div className="dimension-scores-grid">
                {reportDimensionData.map(item => (
                  <div className="dimension-score-item" key={item.originalName}>
                    <span className="dimension-name">{item.name}</span>
                    <div className="dimension-bar-wrap">
                      <div
                        className="dimension-bar"
                        style={{ width: `${Math.min(100, Math.max(0, item.score))}%` }}
                      />
                    </div>
                    <span className="dimension-value">{item.score}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="interview-media-summary">
            <div>
              <strong>语音表达</strong>
              <span>语速 {speechStats.rate} 字/分钟 · 停顿 {speechStats.pauseCount} 次 · 最长停顿 {speechStats.longestPauseSeconds}s</span>
              {speechCoachTip && <p>{speechCoachTip}</p>}
            </div>
            <div>
              <strong>镜头表现</strong>
              <span>视线 {visionAnalysis.gazeLabel} · 头部 {visionAnalysis.headPoseLabel} · 姿态 {visionAnalysis.postureLabel}</span>
              <p>专注度：{visionAnalysis.attentionLabel} {visionAnalysis.attentionScore ? `${visionAnalysis.attentionScore} 分` : ''}</p>
            </div>
          </div>
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
