import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { endInterview, sendMessage, startInterview } from '../api/client';

const POSITIONS = ["前端", "后端", "产品", "运营", "算法", "数媒"];
const INTERVIEW_MODES = ["技术面", "HR面", "压力面", "反馈教练"];

export default function MockInterview() {
  const location = useLocation();
  const [resumeText, setResumeText] = useState(location.state?.resumeText || '');
  const [targetPosition, setTargetPosition] = useState(location.state?.targetPosition || POSITIONS[0]);
  const [interviewMode, setInterviewMode] = useState(INTERVIEW_MODES[0]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [scores, setScores] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [busy, setBusy] = useState(false);
  const [ended, setEnded] = useState(false);
  const [finalReport, setFinalReport] = useState(null);
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
        interviewMode: interviewMode,
      });
      setSessionId(result.session_id);
      setMessages([{
        role: 'interviewer',
        content: `第 1/${result.total_questions || 8} 题：${result.question}`,
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
            <div className="form-group">
              <label>目标岗位（接岗位题库）</label>
              <select value={targetPosition} onChange={event => setTargetPosition(event.target.value)}>
                {POSITIONS.map(pos => (
                  <option key={pos} value={pos}>{pos}</option>
                ))}
              </select>
              <span className="text-muted">选择岗位后，面试官将从对应岗位专属题库出题</span>
            </div>
            <div className="form-group">
              <label>面试模式</label>
              <select value={interviewMode} onChange={event => setInterviewMode(event.target.value)}>
                {INTERVIEW_MODES.map(mode => (
                  <option key={mode} value={mode}>{mode}</option>
                ))}
              </select>
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
          <span className="text-muted">{targetPosition || '综合'} · {interviewMode}</span>
        </div>
        {!ended && (
          <button className="btn btn-danger" onClick={handleEnd} disabled={busy}>
            {busy ? '生成报告中...' : '结束面试'}
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
