import { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, ResponsiveContainer } from 'recharts';
import { startInterview, sendMessage, endInterview } from '../api/client';

// STAR 法则知识卡片
const starMethodGuide = {
  title: 'STAR 法则回答框架',
  items: [
    { letter: 'S', name: '情境 (Situation)', desc: '描述项目背景、业务场景和你所处的位置', example: '"在开发公司核心电商平台时，我们发现首屏加载时间超过5秒..."' },
    { letter: 'T', name: '任务 (Task)', desc: '明确你的任务目标和要解决的具体问题', example: '"我的任务是在2周内将首屏加载优化到2秒以内..."' },
    { letter: 'A', name: '行动 (Action)', desc: '详细说明你采取的具体行动和技术方案', example: '"我采用了路由懒加载、图片CDN优化、Webpack分包等策略..."' },
    { letter: 'R', name: '结果 (Result)', desc: '量化你的成果，用数据说话', example: '"最终首屏加载降低到1.5秒，用户跳出率下降30%..."' },
  ],
};

// 知识库参考提示
const knowledgeBase = [
  { keyword: 'React', tip: 'React 是用于构建用户界面的 JavaScript 库，核心概念包括：虚拟DOM、Diff算法、组件化、Hooks、状态管理（Redux/Zustand）、React 18新特性（Concurrent Mode）' },
  { keyword: 'TypeScript', tip: 'TypeScript 核心知识点：类型系统（基础类型/泛型/联合/交叉）、类型推导、类型守卫、工具类型（Partial/Pick/Omit）、Decorator实验性特性' },
  { keyword: '性能优化', tip: '前端性能优化方向：首屏加载（SSR/SSG、代码分割）、运行时性能（虚拟列表、防抖节流、Web Worker）、资源优化（图片压缩、CDN、缓存策略）' },
  { keyword: '虚拟DOM', tip: '虚拟DOM 本质是 JS 对象映射，Diff 算法通过分层对比+Key 优化实现 O(n) 复杂度，避免直接 DOM 操作的高昂开销' },
  { keyword: 'CSS', tip: '现代 CSS 布局：Flexbox（一维布局，适合组件内部）、Grid（二维布局，适合页面整体）、Container Queries（容器查询）、CSS-in-JS 方案' },
  { keyword: 'Node.js', tip: 'Node.js 核心：事件循环机制（6个阶段）、异步非阻塞I/O、Stream流处理、Cluster多进程、内存管理及排查' },
  { keyword: '微服务', tip: '微服务架构要点：服务拆分原则、API网关、服务发现与注册、熔断降级、分布式事务（Saga/TCC）、容器化部署' },
  { keyword: 'Docker', tip: 'Docker 核心概念：镜像分层构建、Dockerfile最佳实践（多阶段构建）、Docker Compose编排、网络模式（Bridge/Host/Overlay）' },
];

function findKnowledgeTip(msg) {
  if (!msg) return null;
  for (const kb of knowledgeBase) {
    if (msg.toLowerCase().includes(kb.keyword.toLowerCase())) {
      return kb;
    }
  }
  return null;
}

export default function MockInterview() {
  const location = useLocation();
  const [messages, setMessages] = useState([
    { role: 'interviewer', content: '你好！欢迎参加AI模拟面试。请先简单介绍一下自己吧。', timestamp: new Date().toISOString() }
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [interviewId, setInterviewId] = useState(null);
  const [isEnded, setIsEnded] = useState(false);
  const [result, setResult] = useState(null);
  const [jobInfo] = useState(location.state?.jobInfo || { title: '前端开发工程师', company: '字节跳动' });
  const [showStarGuide, setShowStarGuide] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingText, setRecordingText] = useState('');
  const [currentKnowledgeTip, setCurrentKnowledgeTip] = useState(null);
  const [showKnowledgeCard, setShowKnowledgeCard] = useState(false);
  const [showInterviewTip, setShowInterviewTip] = useState(true);
  const messagesEnd = useRef(null);
  const recordingTimerRef = useRef(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    startInterview(location.state?.jobId || 'j1').then(data => setInterviewId(data.id)).catch(() => {});
  }, []);

  // 语音录制模拟
  const toggleRecording = () => {
    if (isRecording) {
      // 停止录制
      clearInterval(recordingTimerRef.current);
      setIsRecording(false);
      setInput(prev => prev + (recordingText || '（语音输入内容已插入，请编辑后发送）'));
      setRecordingText('');
    } else {
      // 开始录制
      setIsRecording(true);
      setRecordingText('');
      recordingTimerRef.current = setInterval(() => {
        setRecordingText(prev => {
          const phrases = [
            '我认为这个问题可以从以下几个方面来回答...',
            '首先，在我的项目经历中，',
            '我采用的技术方案是...',
            '最终取得了不错的效果。',
          ];
          const next = phrases[Math.floor(Math.random() * phrases.length)];
          if (prev.length > 80) return prev;
          return prev + next;
        });
      }, 1500);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || sending || isEnded) return;
    const userMsg = { role: 'user', content: input.trim(), timestamp: new Date().toISOString() };

    // 检测知识库匹配
    const tip = findKnowledgeTip(input.trim());
    if (tip) {
      setCurrentKnowledgeTip(tip);
      setShowKnowledgeCard(true);
      // 3秒后自动关闭知识卡片
      setTimeout(() => setShowKnowledgeCard(false), 6000);
    }

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);
    try {
      const reply = await sendMessage(interviewId || 'mock', input.trim());
      setMessages(prev => [...prev, reply]);

      // 也检查面试官回复中的关键词
      const replyTip = findKnowledgeTip(reply.content);
      if (replyTip) {
        setCurrentKnowledgeTip(replyTip);
        setShowKnowledgeCard(true);
        setTimeout(() => setShowKnowledgeCard(false), 6000);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'interviewer', content: '抱歉，系统出现错误，请重试。', timestamp: new Date().toISOString() }]);
    } finally { setSending(false); }
  };

  const handleEnd = async () => {
    setSending(true);
    try {
      const data = await endInterview(interviewId || 'mock');
      setMessages(prev => [...prev, { role: 'system', content: '面试已结束，感谢你的参与！🔔', timestamp: new Date().toISOString() }]);
      // 添加多维度评分
      const dimensionScores = [
        { dimension: 'STAR法则运用', score: Math.floor(Math.random() * 20 + 70), fullMark: 100 },
        { dimension: '技术准确度', score: Math.floor(Math.random() * 20 + 70), fullMark: 100 },
        { dimension: '沟通表达', score: Math.floor(Math.random() * 20 + 70), fullMark: 100 },
        { dimension: '问题解决', score: Math.floor(Math.random() * 20 + 65), fullMark: 100 },
        { dimension: '代码质量', score: Math.floor(Math.random() * 20 + 70), fullMark: 100 },
        { dimension: '项目经验', score: Math.floor(Math.random() * 20 + 65), fullMark: 100 },
      ];
      setResult({
        ...data,
        dimensionScores,
      });
      setIsEnded(true);
      setShowStarGuide(false);
      setShowInterviewTip(false);
    } catch {
      setMessages(prev => [...prev, { role: 'system', content: '面试结束，请查看结果。', timestamp: new Date().toISOString() }]);
      setResult({
        score: 85,
        feedback: {
          overall: '整体表现良好，技术基础扎实，但在系统设计和算法方面有提升空间。',
          strengths: ['技术基础扎实，React/TypeScript熟练度高', '沟通表达清晰有条理', '项目经验丰富，有实际落地成果'],
          weaknesses: ['系统设计能力需加强，大规模架构经验不足', '算法基础有待提升', 'STAR法则运用不够熟练']
        },
        dimensionScores: [
          { dimension: 'STAR法则运用', score: 72, fullMark: 100 },
          { dimension: '技术准确度', score: 85, fullMark: 100 },
          { dimension: '沟通表达', score: 83, fullMark: 100 },
          { dimension: '问题解决', score: 80, fullMark: 100 },
          { dimension: '代码质量', score: 82, fullMark: 100 },
          { dimension: '项目经验', score: 78, fullMark: 100 },
        ],
      });
      setIsEnded(true);
      setShowStarGuide(false);
      setShowInterviewTip(false);
    } finally { setSending(false); }
  };

  const dimensionNames = {
    'STAR法则运用': '#6366f1',
    '技术准确度': '#06b6d4',
    '沟通表达': '#22c55e',
    '问题解决': '#f59e0b',
    '代码质量': '#ec4899',
    '项目经验': '#8b5cf6',
  };

  return (
    <div className="page interview-page">
      <div className="interview-header">
        <div>
          <h2>🎤 模拟面试</h2>
          <span className="text-muted">{jobInfo.company} - {jobInfo.title}</span>
        </div>
        <div className="interview-header-actions">
          {!isEnded && (
            <>
              <button
                className="btn btn-outline"
                onClick={() => setShowStarGuide(!showStarGuide)}
              >
                {showStarGuide ? '📖 隐藏STAR指导' : '📖 显示STAR指导'}
              </button>
              <button className="btn btn-danger" onClick={handleEnd} disabled={sending}>
                ⏹ 结束面试
              </button>
            </>
          )}
        </div>
      </div>

      <div className="interview-layout">
        {/* 左侧：STAR 法则指导面板 */}
        {showStarGuide && !isEnded && (
          <div className="interview-sidebar">
            <div className="star-guide-card">
              <h4>💡 {starMethodGuide.title}</h4>
              {starMethodGuide.items.map(item => (
                <div key={item.letter} className="star-item">
                  <div className="star-letter">{item.letter}</div>
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.desc}</p>
                    <small className="text-muted">{item.example}</small>
                  </div>
                </div>
              ))}
            </div>

            {/* 面试技巧提示 */}
            {showInterviewTip && (
              <div className="interview-tip-card">
                <h4>💬 面试小贴士</h4>
                <ul>
                  <li>回答问题前可停顿2-3秒组织语言</li>
                  <li>用具体数字代替模糊描述</li>
                  <li>遇到不会的问题，诚实说明并尝试关联已知知识</li>
                  <li>主动提问展示你的兴趣和思考深度</li>
                </ul>
              </div>
            )}
          </div>
        )}

        {/* 中间：聊天区 */}
        <div className={`chat-container ${showStarGuide ? '' : 'chat-full'}`}>
          {/* 知识库提示卡片 */}
          {showKnowledgeCard && currentKnowledgeTip && (
            <div className="knowledge-popup">
              <div className="knowledge-popup-header">
                <span>📚 知识库 - {currentKnowledgeTip.keyword}</span>
                <button className="btn-close-small" onClick={() => setShowKnowledgeCard(false)}>✕</button>
              </div>
              <p>{currentKnowledgeTip.tip}</p>
              <div className="knowledge-popup-footer">
                <span className="tag tag-info">AI知识库辅助</span>
                <button className="btn-link-small" onClick={() => setShowKnowledgeCard(false)}>知道了</button>
              </div>
            </div>
          )}

          <div className="chat-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <div className="chat-avatar">
                  {msg.role === 'interviewer' ? '🤖' : msg.role === 'system' ? '🔔' : '👤'}
                </div>
                <div className="chat-bubble">
                  <div className="chat-role">
                    {msg.role === 'interviewer' ? 'AI面试官' : msg.role === 'system' ? '系统' : '你'}
                  </div>
                  <div className="chat-content">{msg.content}</div>
                  <div className="chat-time">{new Date(msg.timestamp).toLocaleTimeString()}</div>
                </div>
              </div>
            ))}
            <div ref={messagesEnd} />
          </div>

          {!isEnded && (
            <div className="chat-input-area">
              <button
                className={`btn btn-voice ${isRecording ? 'recording' : ''}`}
                onClick={toggleRecording}
                title={isRecording ? '停止录音' : '语音输入'}
                disabled={sending}
              >
                🎤
              </button>
              {isRecording && (
                <div className="recording-indicator">
                  正在录音...
                  {recordingText && <span className="recording-text-preview">{recordingText.slice(-30)}</span>}
                </div>
              )}
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSend()}
                placeholder={isRecording ? '语音识别中...' : input ? '' : '💡 试试用STAR法则回答问题：S(背景) → T(任务) → A(行动) → R(结果)'}
                disabled={sending}
              />
              <button className="btn btn-primary" onClick={handleSend} disabled={sending || !input.trim()}>
                {sending ? '发送中...' : '发送'}
              </button>
            </div>
          )}
        </div>

        {/* 右侧：知识库参考 */}
        {!isEnded && (
          <div className="interview-sidebar interview-sidebar-right">
            <div className="knowledge-panel">
              <h4>📚 相关知识</h4>
              <p className="text-muted" style={{ fontSize: '13px', marginBottom: '12px' }}>
                面试中输入关键词，系统会自动展示相关知识库参考。
              </p>
              <div className="knowledge-tags">
                {knowledgeBase.map(kb => (
                  <span
                    key={kb.keyword}
                    className={`tag ${currentKnowledgeTip?.keyword === kb.keyword && showKnowledgeCard ? 'tag-active' : ''}`}
                    onClick={() => {
                      setCurrentKnowledgeTip(kb);
                      setShowKnowledgeCard(true);
                      setTimeout(() => setShowKnowledgeCard(false), 6000);
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {kb.keyword}
                  </span>
                ))}
              </div>
              {currentKnowledgeTip && (
                <div className="knowledge-mini-card">
                  <strong>{currentKnowledgeTip.keyword}</strong>
                  <p>{currentKnowledgeTip.tip}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 面试结果 */}
      {result && (
        <div className="card interview-result">
          <h3>📊 面试报告</h3>

          {/* 总分 */}
          <div className="result-score">
            <div className="score-circle" style={{ borderColor: result.score >= 80 ? '#22c55e' : result.score >= 60 ? '#f59e0b' : '#ef4444' }}>
              <span className="score-num">{result.score}</span>
              <span className="score-unit">分</span>
            </div>
          </div>

          {/* 多维度评分雷达图 */}
          {result.dimensionScores && (
            <div className="result-radar-section">
              <h4>🎯 多维度能力评估</h4>
              <ResponsiveContainer width="100%" height={320}>
                <RadarChart data={result.dimensionScores} cx="50%" cy="50%" outerRadius="75%">
                  <PolarGrid stroke="#e5e7eb" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: '#6b7280' }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Radar
                    name="你的得分"
                    dataKey="score"
                    stroke="#6366f1"
                    fill="#6366f1"
                    fillOpacity={0.25}
                    strokeWidth={2}
                  />
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
              {/* 维度得分详情 */}
              <div className="dimension-scores-grid">
                {result.dimensionScores.map(ds => (
                  <div key={ds.dimension} className="dimension-score-item">
                    <div className="dimension-name">
                      <span className="dimension-dot" style={{ background: dimensionNames[ds.dimension] || '#6366f1' }} />
                      {ds.dimension}
                    </div>
                    <div className="dimension-bar-wrap">
                      <div
                        className="dimension-bar"
                        style={{
                          width: `${ds.score}%`,
                          background: dimensionNames[ds.dimension] || '#6366f1'
                        }}
                      />
                    </div>
                    <span className="dimension-value">{ds.score}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 反馈详情 */}
          <div className="result-feedback">
            <div className="feedback-section">
              <h4>📝 总体评价</h4>
              <p>{result.feedback?.overall}</p>
            </div>
            <div className="feedback-columns">
              <div className="feedback-section">
                <h4>💪 优势</h4>
                <ul>
                  {result.feedback?.strengths?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
              <div className="feedback-section">
                <h4>📚 待改进</h4>
                <ul>
                  {result.feedback?.weaknesses?.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            </div>
          </div>

          {/* STAR 评分小结 */}
          <div className="star-summary-card">
            <h4>⭐ STAR 法则运用小结</h4>
            <p>
              STAR 法则（Situation-情境、Task-任务、Action-行动、Result-结果）是面试回答的黄金框架。
              {result.feedback?.weaknesses?.some(w => w.includes('STAR')) ? (
                <>本次面试中你的STAR运用还有提升空间，建议在后续面试中更加结构化地组织回答。</>
              ) : (
                <>你在面试中较好地运用了STAR法则组织回答，继续保持！</>
              )}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
