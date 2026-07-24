import { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { startInterview, sendMessage, endInterview } from '../api/client';

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
  const messagesEnd = useRef(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    startInterview(location.state?.jobId || 'j1').then(data => setInterviewId(data.id)).catch(() => {});
  }, []);

  const handleSend = async () => {
    if (!input.trim() || sending || isEnded) return;
    const userMsg = { role: 'user', content: input.trim(), timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);
    try {
      const reply = await sendMessage(interviewId || 'mock', input.trim());
      setMessages(prev => [...prev, reply]);
    } catch {
      setMessages(prev => [...prev, { role: 'interviewer', content: '抱歉，系统出现错误，请重试。', timestamp: new Date().toISOString() }]);
    } finally { setSending(false); }
  };

  const handleEnd = async () => {
    setSending(true);
    try {
      const data = await endInterview(interviewId || 'mock');
      setMessages(prev => [...prev, { role: 'system', content: '面试已结束，感谢你的参与！🔔', timestamp: new Date().toISOString() }]);
      setResult(data);
      setIsEnded(true);
    } catch {
      setMessages(prev => [...prev, { role: 'system', content: '面试结束，请查看结果。', timestamp: new Date().toISOString() }]);
      setResult({
        score: 85,
        feedback: { overall: '整体表现良好', strengths: ['技术基础扎实', '沟通表达清晰', '项目经验丰富'], weaknesses: ['系统设计能力需加强', '算法基础有待提升'] }
      });
      setIsEnded(true);
    } finally { setSending(false); }
  };

  return (
    <div className="page interview-page">
      <div className="interview-header">
        <div>
          <h2>🎤 模拟面试</h2>
          <span className="text-muted">{jobInfo.company} - {jobInfo.title}</span>
        </div>
        {!isEnded && (
          <button className="btn btn-danger" onClick={handleEnd} disabled={sending}>
            ⏹ 结束面试
          </button>
        )}
      </div>

      {/* 聊天区 */}
      <div className="chat-container">
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
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder="输入你的回答..."
              disabled={sending}
            />
            <button className="btn btn-primary" onClick={handleSend} disabled={sending || !input.trim()}>
              {sending ? '发送中...' : '发送'}
            </button>
          </div>
        )}
      </div>

      {/* 面试结果 */}
      {result && (
        <div className="card interview-result">
          <h3>📊 面试结果</h3>
          <div className="result-score">
            <div className="score-circle" style={{ borderColor: result.score >= 80 ? '#22c55e' : result.score >= 60 ? '#f59e0b' : '#ef4444' }}>
              <span className="score-num">{result.score}</span>
              <span className="score-unit">分</span>
            </div>
          </div>
          <div className="result-feedback">
            <div className="feedback-section">
              <h4>📝 总体评价</h4>
              <p>{result.feedback?.overall}</p>
            </div>
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
      )}
    </div>
  );
}
