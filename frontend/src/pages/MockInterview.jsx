import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  startInterview,
  sendMessage,
  endInterview,
  getKnowledgeBase,
  getInterviewHistory,
} from '../api/client';
import RadarChart from '../components/RadarChart';
import { mapDimensionScores } from '../utils/dimensionLabels';


export default function MockInterview() {
  const navigate = useNavigate();
  const location = useLocation();

  const [jobId, setJobId] = useState('j1');
  const [mode, setMode] = useState('comprehensive');
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [ended, setEnded] = useState(false);
  const [result, setResult] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [knowledgeText, setKnowledgeText] = useState('');
  const [showKnowledgePopup, setShowKnowledgePopup] = useState(false);

  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // New: knowledge tags state
  const [selectedKnowledgeTag, setSelectedKnowledgeTag] = useState(null);
  const [knowledgeMiniContent, setKnowledgeMiniContent] = useState('');

  const chatEndRef = useRef(null);
  const startedRef = useRef(false);
  const recognitionRef = useRef(null);

  // 语音输入状态
  const [isRecording, setIsRecording] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechError, setSpeechError] = useState('');

  useEffect(() => {
    setJobId(location.state?.jobId || 'j1');
  }, [location.state]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 初始化语音识别
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.lang = 'zh-CN';
      rec.interimResults = true;
      rec.continuous = true;
      rec.maxAlternatives = 1;

      rec.onresult = (event) => {
        let final = '';
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            final += t;
          } else {
            interim += t;
          }
        }
        if (final) {
          setInput((prev) => prev + final);
          setInterimText('');
        } else {
          setInterimText(interim);
        }
      };

      rec.onerror = (event) => {
        if (event.error === 'no-speech') return;
        if (event.error === 'aborted') return;
        const errMsg = event.error === 'not-allowed'
          ? '麦克风权限被拒绝，请在浏览器设置中允许麦克风访问'
          : `语音识别错误: ${event.error}`;
        setSpeechError(errMsg);
        setIsRecording(false);
        setInterimText('');
      };

      rec.onend = () => {
        setIsRecording(false);
        setInterimText('');
      };

      recognitionRef.current = rec;
      setSpeechSupported(true);
    }
  }, []);

  const handleStart = async () => {
    setBusy(true);
    setShowHelp(false);
    try {
      const titleMap = { j1: '前端工程师', j2: '后端工程师', j3: '产品经理' };
      const targetPosition = titleMap[jobId] || '目标岗位';
      const resumeText = `我是一名应聘${targetPosition}的候选人，具备相关项目经验与技术能力，希望能在该岗位持续成长并创造价值。`;
      const data = await startInterview({ resumeText, targetPosition, targetJobId: jobId });
      setSessionId(data.session_id);
      setMessages([
        {
          role: 'interviewer',
          content: data.question,
          timestamp: new Date().toISOString(),
        },
      ]);
      setResult(null);
      setEnded(false);
      startedRef.current = true;
    } catch (e) {
      alert('面试启动失败: ' + e.message);
    } finally {
      setBusy(false);
    }
  };

  const startRecording = () => {
    const rec = recognitionRef.current;
    if (!rec) return;
    setSpeechError('');
    setInterimText('');
    try {
      rec.start();
      setIsRecording(true);
    } catch {
      // already started
    }
  };

  const stopRecording = () => {
    const rec = recognitionRef.current;
    if (!rec) return;
    try {
      rec.stop();
    } catch {
      // already stopped
    }
    setIsRecording(false);
    setInterimText('');
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || busy || !sessionId) return;
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, timestamp: new Date().toISOString() },
    ]);
    setInput('');
    setBusy(true);
    try {
      const reply = await sendMessage(sessionId, text);
      setMessages((prev) => {
        // 给前一条 user 消息补上分数
        const updated = [...prev];
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'user' && !updated[i].score) {
            updated[i] = {
              ...updated[i],
              score: reply.score ?? undefined,
              feedback: reply.feedback ?? undefined,
            };
            break;
          }
        }
        return [
          ...updated,
          {
            role: reply.role,
            content: reply.content,
            timestamp: reply.timestamp || new Date().toISOString(),
          },
        ];
      });
    } catch (e) {
      alert('发送失败: ' + e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleEnd = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      const res = await endInterview(sessionId);
      setResult(res);
      setEnded(true);
      setShowHelp(false);
    } catch (e) {
      alert('生成报告失败: ' + e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleKnowledge = async () => {
    if (knowledgeText) {
      setShowKnowledgePopup(!showKnowledgePopup);
      return;
    }
    setBusy(true);
    try {
      const data = await getKnowledgeBase({ session_id: sessionId });
      setKnowledgeText(data.content || '暂无相关知识库提示');
      setShowKnowledgePopup(true);
    } catch (e) {
      alert('知识库获取失败: ' + e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleKnowledgeTag = async (tag) => {
    if (selectedKnowledgeTag === tag) {
      setSelectedKnowledgeTag(null);
      setKnowledgeMiniContent('');
      return;
    }
    setSelectedKnowledgeTag(tag);
    try {
      const data = await getKnowledgeBase({ session_id: sessionId, tag });
      setKnowledgeMiniContent(data.content || `暂无"${tag}"相关提示`);
    } catch {
      setKnowledgeMiniContent(`无法获取"${tag}"相关内容`);
    }
  };

  const loadHistory = async () => {
    try {
      const list = await getInterviewHistory();
      setHistory(Array.isArray(list) ? list : []);
    } catch {
      setHistory([]);
    }
    setShowHistory(true);
  };

  const handleHistorySelect = (item) => {
    setShowHistory(false);
    setSessionId(item.session_id || item.id);
    setMessages(
      (item.messages || []).map((m) => ({
        ...m,
        timestamp: m.timestamp || new Date().toISOString(),
      })),
    );
    setEnded(true);
    setResult(item.result || null);
    startedRef.current = true;
  };

  // radar chart data
  const radarData = result?.dimension_scores
    ? mapDimensionScores(result.dimension_scores)
    : [
        { name: '技术能力', score: 78, maxScore: 100 },
        { name: '项目经验', score: 72, maxScore: 100 },
        { name: '沟通表达', score: 85, maxScore: 100 },
        { name: '问题解决', score: 70, maxScore: 100 },
        { name: '系统设计', score: 65, maxScore: 100 },
        { name: '行业理解', score: 80, maxScore: 100 },
      ];

  const guidanceSteps = [
    {
      letter: 'S',
      title: '情境',
      desc: 'Situation — 描述项目背景与环境',
      tip: '例："在我实习期间，团队需要3个月内上线一个新用户系统。"',
    },
    {
      letter: 'T',
      title: '任务',
      desc: 'Task — 明确你的职责与目标',
      tip: '例："我负责前端模块开发，目标是提升页面加载速度20%。"',
    },
    {
      letter: 'A',
      title: '行动',
      desc: 'Action — 说明你采取的具体措施',
      tip: '例："我引入了Vue3 Composition API重构，配合懒加载。"',
    },
    {
      letter: 'R',
      title: '结果',
      desc: 'Result — 展示量化成果',
      tip: '例："加载时间从2.8s降到1.2s，提升57%，用户留存+12%。"',
    },
  ];

  const knowledgeTags = [
    '系统设计',
    '算法优化',
    '项目管理',
    '团队协作',
    '性能调优',
    '安全规范',
  ];

  return (
    <div className="page" style={{ height: 'calc(100vh - 108px)', display: 'flex', flexDirection: 'column' }}>
      {/* -------- 头部 -------- */}
      <div className="interview-header">
        <div>
          <h2 style={{ margin: 0 }}>模拟面试</h2>
          {!sessionId ? <span className="text-muted">选择岗位后开始面试</span> : null}
        </div>
        <div className="interview-header-actions">
          {sessionId && (
            <button
              className="btn btn-outline btn-sm"
              onClick={loadHistory}
              disabled={busy}
            >
              历史
            </button>
          )}
          {!sessionId && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setShowHelp(!showHelp)}
            >
              {showHelp ? '收起' : '面试提示'}
            </button>
          )}
        </div>
      </div>

      {/* -------- 未开始 -------- */}
      {!sessionId && (
        <div className="interview-layout" style={{ flex: 1, overflow: 'hidden' }}>
          {/* 左侧：知识库面板 */}
          <div className="interview-sidebar">
            <div className="knowledge-panel">
              <h4>内容知识库</h4>
              <div className="knowledge-tags">
                {knowledgeTags.map((tag) => (
                  <span
                    key={tag}
                    className={`tag ${selectedKnowledgeTag === tag ? 'tag-active' : ''}`}
                    onClick={() => handleKnowledgeTag(tag)}
                  >
                    {tag}
                  </span>
                ))}
              </div>
              {selectedKnowledgeTag && (
                <div className="knowledge-mini-card">
                  <strong>{selectedKnowledgeTag}</strong>
                  <p>{knowledgeMiniContent || '加载中...'}</p>
                </div>
              )}
            </div>
          </div>

          {/* 中间：启动表单 */}
          <div className="card" style={{ flex: 1, overflow: 'auto', marginBottom: 0 }}>
            <div className="form-grid">
              <div className="form-group form-group-full">
                <label>目标岗位</label>
                <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
                  <option value="j1">前端工程师</option>
                  <option value="j2">后端工程师</option>
                  <option value="j3">产品经理</option>
                </select>
              </div>
              <div className="form-group form-group-full">
                <label>面试模式</label>
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="comprehensive">综合面试</option>
                  <option value="technical">技术面试</option>
                  <option value="behavioral">行为面试</option>
                </select>
              </div>
              <div className="form-group form-group-full form-actions">
                <button
                  className="btn btn-primary btn-block"
                  onClick={handleStart}
                  disabled={busy}
                >
                  {busy ? '生成问题中...' : '开始面试'}
                </button>
              </div>
            </div>
          </div>

          {/* 右侧：STAR 面试提示 */}
          {showHelp && (
            <div className="interview-sidebar-right">
              <div className="star-guide-card">
                <h4>STAR 结构化回答</h4>
                {guidanceSteps.map((s) => (
                  <div className="star-item" key={s.letter}>
                    <div className="star-letter">{s.letter}</div>
                    <div>
                      <strong>{s.title}</strong>
                      <p>{s.desc}</p>
                      <small>{s.tip}</small>
                    </div>
                  </div>
                ))}
              </div>
              <div className="interview-tip-card">
                <h4>面试建议</h4>
                <ul>
                  <li>团队协作中，使用"我们"而非"我"</li>
                  <li>善用数字和数据量化成果</li>
                  <li>展示从失败中的学习与成长</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* -------- 面试进行中 -------- */}
      {sessionId && (
        <div className="interview-layout" style={{ flex: 1, overflow: 'hidden' }}>
          {/* 左侧：STAR 提示 */}
          <div className="interview-sidebar">
            <div className="star-guide-card">
              <h4>STAR 结构化回答</h4>
              {guidanceSteps.map((s) => (
                <div className="star-item" key={s.letter}>
                  <div className="star-letter">{s.letter}</div>
                  <div>
                    <strong>{s.title}</strong>
                    <p>{s.desc}</p>
                    <small>{s.tip}</small>
                  </div>
                </div>
              ))}
            </div>
            <div className="interview-tip-card">
              <h4>面试建议</h4>
              <ul>
                <li>团队协作中，使用"我们"而非"我"</li>
                <li>善用数字和数据量化成果</li>
                <li>展示从失败中的学习与成长</li>
              </ul>
            </div>
          </div>

          {/* 中间：聊天区 */}
          <div className="chat-container">
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <div key={i} className={`chat-message ${msg.role}`}>
                  <div className="chat-avatar">
                    {msg.role === 'interviewer' ? '🤖' : msg.role === 'system' ? '⚙' : '👤'}
                  </div>
                  <div className="chat-bubble">
                    <div className="chat-role">
                      {msg.role === 'interviewer' ? 'AI 面试官' : msg.role === 'system' ? '系统' : '你'}
                      {msg.role === 'user' && msg.score != null && (
                        <span className="chat-score-badge" title={msg.feedback || ''}>
                          {msg.score}分
                        </span>
                      )}
                    </div>
                    <div className="chat-content" style={{ whiteSpace: 'pre-wrap' }}>
                      {msg.content}
                    </div>
                    <div className="chat-time">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                      {msg.role === 'user' && msg.feedback && (
                        <span className="chat-feedback-hint"> — {msg.feedback}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* 知识库弹窗 */}
            {showKnowledgePopup && (
              <div className="knowledge-popup">
                <div className="knowledge-popup-header">
                  <span>知识库提示</span>
                  <button
                    className="btn-close-small"
                    onClick={() => setShowKnowledgePopup(false)}
                  >
                    ✕
                  </button>
                </div>
                <p>{knowledgeText}</p>
                <div className="knowledge-popup-footer">
                  <button
                    className="btn-link-small"
                    onClick={() => setShowKnowledgePopup(false)}
                  >
                    关闭
                  </button>
                </div>
              </div>
            )}

            {/* 输入区 */}
            {!ended && (
              <div className="chat-input-area">
                <button
                  className="btn btn-outline btn-sm"
                  onClick={handleKnowledge}
                  disabled={busy}
                  title="知识库提示"
                >
                  💡
                </button>
                {speechSupported && (
                  <button
                    className={`btn-voice ${isRecording ? 'recording' : ''}`}
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={busy}
                    title={isRecording ? '停止录音' : '语音输入'}
                  >
                    🎤
                  </button>
                )}
                <input
                  value={isRecording ? input + (interimText ? ' ' + interimText : '') : input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={
                    isRecording
                      ? '正在聆听...'
                      : speechSupported
                      ? '输入你的回答，或点击🎤语音输入...'
                      : '输入你的回答（可使用 STAR 方法）...'
                  }
                  disabled={busy}
                />
                <button
                  className="btn btn-primary"
                  onClick={handleSend}
                  disabled={busy || !input.trim()}
                >
                  {busy ? '思考中...' : '发送'}
                </button>
              </div>
            )}

            {/* 录音中状态条 */}
            {isRecording && (
              <div className="recording-bar">
                <span className="pulse-dot" />
                <span className="recording-label">正在录音...</span>
                <span className="recording-preview">
                  {interimText || input.substring(input.lastIndexOf('\n') + 1).slice(-50) || '请说话...'}
                </span>
                <button className="recording-stop-btn" onClick={stopRecording}>
                  停止
                </button>
              </div>
            )}

            {/* 语音错误提示 */}
            {speechError && (
              <div className="speech-error-bar">
                <span>⚠</span>
                <span>{speechError}</span>
                <button
                  className="btn-close-small"
                  onClick={() => setSpeechError('')}
                  style={{ marginLeft: 'auto' }}
                >
                  ✕
                </button>
              </div>
            )}
          </div>

          {/* 右侧：知识点 */}
          <div className="interview-sidebar-right">
            <div className="knowledge-panel">
              <h4>内容知识库</h4>
              <div className="knowledge-tags">
                {knowledgeTags.map((tag) => (
                  <span
                    key={tag}
                    className={`tag ${selectedKnowledgeTag === tag ? 'tag-active' : ''}`}
                    onClick={() => handleKnowledgeTag(tag)}
                  >
                    {tag}
                  </span>
                ))}
              </div>
              {selectedKnowledgeTag && (
                <div className="knowledge-mini-card">
                  <strong>{selectedKnowledgeTag}</strong>
                  <p>{knowledgeMiniContent || '加载中...'}</p>
                </div>
              )}
            </div>

            {messages.length > 0 && !ended && (
              <div style={{ marginTop: 12 }}>
                <button
                  className="btn btn-danger btn-block btn-sm"
                  onClick={handleEnd}
                  disabled={busy}
                >
                  {busy ? '生成报告中...' : '结束面试'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* -------- 面试报告 -------- */}
      {ended && result && (
        <div className="card interview-result" style={{ marginTop: 0, overflow: 'auto', flex: 1 }}>
          <div className="result-score">
            <div className="score-circle large">
              <span className="score-num">{result.score}</span>
              <span className="score-unit">分</span>
            </div>
          </div>

          <div style={{ marginBottom: 24, textAlign: 'center', color: 'var(--text-secondary)' }}>
            {result.jobTitle || '综合评估'}
          </div>

          {/* 雷达图 */}
          <div className="result-radar-section">
            <h4>能力维度评估</h4>
            <RadarChart data={radarData} />
            <div className="dimension-scores-grid">
              {radarData.map((d) => (
                <div className="dimension-score-item" key={d.name}>
                  <span className="dimension-name">
                    <span className="dimension-dot" style={{ background: 'var(--primary)' }} />
                    {d.name}
                  </span>
                  <div className="dimension-bar-wrap">
                    <div
                      className="dimension-bar"
                      style={{ width: `${(d.score / d.maxScore) * 100}%`, background: 'var(--primary)' }}
                    />
                  </div>
                  <span className="dimension-value">{d.score}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 反馈 */}
          {result.feedback && (
            <>
              <div className="feedback-section">
                <h4>综合评价</h4>
                <p>{result.feedback.overall}</p>
              </div>
              <div className="feedback-columns">
                <div className="feedback-section">
                  <h4>优势亮点</h4>
                  <ul>
                    {result.feedback.strengths?.map((s, i) => (
                      <li key={i}>{s}</li>
                    )) || <li>暂无</li>}
                  </ul>
                </div>
                <div className="feedback-section">
                  <h4>改进方向</h4>
                  <ul>
                    {result.feedback.weaknesses?.map((w, i) => (
                      <li key={i}>{w}</li>
                    )) || <li>暂无</li>}
                  </ul>
                </div>
              </div>
            </>
          )}

          {/* STAR 总结卡片 */}
          <div className="star-summary-card">
            <h4>STAR 表达建议</h4>
            <p>
              建议在回答中更多使用 STAR 方法组织语言：先介绍项目背景（Situation），
              明确你的角色和目标（Task），详细说明你采取的具体行动（Action），
              最后展示可量化的成果（Result）。这能让你的回答更有说服力。
            </p>
          </div>

          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <button
              className="btn btn-primary"
              onClick={() => {
                setSessionId(null);
                setMessages([]);
                setResult(null);
                setEnded(false);
                startedRef.current = false;
              }}
            >
              重新面试
            </button>
            <button
              className="btn btn-outline"
              style={{ marginLeft: 12 }}
              onClick={() => navigate('/interviews/history')}
            >
              查看历史
            </button>
          </div>
        </div>
      )}

      {/* -------- 历史记录弹窗 -------- */}
      {showHistory && (
        <div className="modal-overlay" onClick={() => setShowHistory(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxHeight: '70vh' }}>
            <div className="modal-header">
              <span style={{ fontWeight: 600 }}>面试历史记录</span>
              <button className="btn btn-sm" onClick={() => setShowHistory(false)}>
                关闭
              </button>
            </div>
            <div className="modal-body">
              {history.length === 0 ? (
                <div className="empty">暂无历史记录</div>
              ) : (
                <div className="review-list">
                  {history.map((item) => (
                    <div
                      key={item.session_id || item.id}
                      className="review-card"
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleHistorySelect(item)}
                    >
                      <div className="review-card-header">
                        <h4>{item.jobTitle || '面试记录'}</h4>
                        <span className="text-muted">
                          {new Date(item.timestamp || item.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="review-info">
                        <span>总分: {item.score ?? item.overall_score ?? 'N/A'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
