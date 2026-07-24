import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { sendMessage, startInterview } from '../api/client';

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
  const [error, setError] = useState('');
  const messagesEnd = useRef(null);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const averageScore = useMemo(() => {
    if (!scores.length) return null;
    return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length);
  }, [scores]);

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
      setMessages([{
        role: 'interviewer',
        content: result.question,
        timestamp: new Date().toISOString(),
      }]);
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
      setScores(current => [...current, result.score]);
      setFeedback(current => [...current, result.feedback]);
      setMessages(current => [...current, {
        role: 'interviewer',
        content: `${result.feedback}\n\n${result.next_question}`,
        timestamp: new Date().toISOString(),
      }]);
    } catch (requestError) {
      setError(requestError.message || '回答提交失败');
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
              <input value={targetPosition} onChange={event => setTargetPosition(event.target.value)} placeholder="如：Python 后端工程师" />
            </div>
            <div className="form-group form-group-full">
              <label>简历文本 *</label>
              <textarea value={resumeText} onChange={event => setResumeText(event.target.value)} rows={10} placeholder="粘贴简历文本" />
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
          <button className="btn btn-danger" onClick={() => setEnded(true)} disabled={busy}>
            结束面试
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
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
          <p><strong>平均得分：</strong>{averageScore ?? '尚未完成作答'}</p>
          {feedback.length > 0 && (
            <ul>{feedback.map((item, index) => <li key={index}>{item}</li>)}</ul>
          )}
          <p className="text-muted">面试记录持久化与完整报告将在后续模块接入。</p>
        </div>
      )}
    </div>
  );
}
