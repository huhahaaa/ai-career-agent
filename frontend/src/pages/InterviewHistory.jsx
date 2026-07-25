import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileBarChart, Mic, Play, Star, Trophy, X } from 'lucide-react';
import { getInterviewHistory, getInterviewReport } from '../api/client';

const scoreColor = score => (
  score == null ? 'var(--text-muted)' : score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--error)'
);

export default function InterviewHistory() {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    getInterviewHistory()
      .then(setInterviews)
      .catch(requestError => setError(requestError.message || '面试历史加载失败'))
      .finally(() => setLoading(false));
  }, []);

  const viewReport = async (id) => {
    setReportLoading(true);
    try {
      const data = await getInterviewReport(id);
      setSelectedReport(data);
    } catch (requestError) {
      setError(requestError.message || '面试报告详情加载失败');
      setSelectedReport(null);
    } finally { setReportLoading(false); }
  };

  const validInterviews = interviews.filter(
    item => item.status === 'completed' && item.score != null && item.questions_count > 0,
  );
  const scoredInterviews = validInterviews.filter(item => item.score != null);

  const trendData = scoredInterviews
    .slice()
    .reverse()
    .map((item, i) => ({
      date: new Date(item.created_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }),
      pointLabel: `${new Date(item.created_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })} 第${i + 1}次`,
      tooltipLabel: new Date(item.created_at).toLocaleString('zh-CN'),
      score: item.score,
      index: i + 1,
    }));

  const avgScore = scoredInterviews.length
    ? (scoredInterviews.reduce((s, i) => s + i.score, 0) / scoredInterviews.length).toFixed(1)
    : '--';
  const maxScore = scoredInterviews.length ? Math.max(...scoredInterviews.map(i => i.score)) : '--';

  if (loading) return <div className="loading">加载中...</div>;
  if (error) return <div className="alert alert-info">{error}</div>;

  return (
    <div className="page">
      <h2>面试记录与报告</h2>

      {validInterviews.length > 0 && (
        <>
          {/* 统计概览 */}
          <div className="stats-grid">
            <div className="stat-card" style={{ borderTopColor: 'var(--chart-primary)' }}>
              <div className="stat-icon" style={{ color: 'var(--chart-primary)' }}><Mic size={22} /></div>
              <div className="stat-info">
                <div className="stat-value">{validInterviews.length}</div>
                <div className="stat-label">总面试次数</div>
              </div>
            </div>
            <div className="stat-card" style={{ borderTopColor: 'var(--chart-success)' }}>
              <div className="stat-icon" style={{ color: 'var(--chart-success)' }}><Star size={22} /></div>
              <div className="stat-info">
                <div className="stat-value">{avgScore}</div>
                <div className="stat-label">平均得分</div>
              </div>
            </div>
            <div className="stat-card" style={{ borderTopColor: 'var(--chart-warning)' }}>
              <div className="stat-icon" style={{ color: 'var(--chart-warning)' }}><Trophy size={22} /></div>
              <div className="stat-info">
                <div className="stat-value">{maxScore}</div>
                <div className="stat-label">最高得分</div>
              </div>
            </div>
          </div>

          {/* 面试趋势图 */}
          <div className="chart-card">
            <h3>历次面试得分趋势</h3>
            {trendData.length ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="pointLabel" tickFormatter={value => value.split(' ')[0]} />
                  <YAxis domain={[0, 100]} />
                  <Tooltip formatter={v => `${v}分`} labelFormatter={(_, payload) => payload?.[0]?.payload?.tooltipLabel || ''} />
                  <Line type="monotone" dataKey="score" name="面试得分" stroke="var(--chart-primary)" strokeWidth={3} dot={{ r: 6, fill: 'var(--chart-primary)' }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">暂无有效面试得分，请先完成一次面试。</div>
            )}
          </div>
        </>
      )}

      {/* 面试列表 */}
      <div className="card">
        <div className="card-header-row">
          <h3>面试记录</h3>
          <button className="btn btn-primary" onClick={() => navigate('/interview')}>
            <Play size={16} />
            开始新面试
          </button>
        </div>
        {validInterviews.length === 0 ? (
          <div className="empty">
            <p>暂无面试记录</p>
            <button className="btn btn-primary" onClick={() => navigate('/interview')}>
              <Play size={16} />
              开始第一次面试
            </button>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>公司</th>
                <th>岗位</th>
                <th>模式</th>
                <th>得分</th>
                <th>时长</th>
                <th>题目数</th>
                <th>日期</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {validInterviews.map(item => (
                <tr key={item.id}>
                  <td>{item.company}</td>
                  <td>{item.job_title}</td>
                  <td><span className="tag">{item.mode}</span></td>
                  <td>
                    <strong style={{ color: scoreColor(item.score) }}>
                      {item.score == null ? '--' : item.score}
                    </strong>
                  </td>
                  <td>{item.duration_minutes == null ? '--' : `${item.duration_minutes}分钟`}</td>
                  <td>{item.questions_count}题</td>
                  <td>{new Date(item.created_at).toLocaleDateString()}</td>
                  <td>
                    <button className="btn btn-sm btn-outline" onClick={() => viewReport(item.id)}>
                      <FileBarChart size={14} />
                      查看报告
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 面试报告弹窗 */}
      {selectedReport && (
        <div className="modal-overlay" onClick={() => setSelectedReport(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>面试报告 - {selectedReport.company}</h3>
              <button className="btn btn-sm btn-outline" onClick={() => setSelectedReport(null)}>
                <X size={14} />
              </button>
            </div>
            {reportLoading ? (
              <div className="loading">加载报告中...</div>
            ) : (
              <div className="modal-body">
                <div className="result-score">
                  <div className="score-circle large" style={{ borderColor: scoreColor(selectedReport.score) }}>
                    <span className="score-num">{selectedReport.score == null ? '--' : selectedReport.score}</span>
                    <span className="score-unit">分</span>
                  </div>
                </div>

                <div className="report-grid">
                  <div className="report-item"><strong>岗位：</strong>{selectedReport.job_title}</div>
                  <div className="report-item"><strong>时长：</strong>{selectedReport.duration_minutes == null ? '--' : `${selectedReport.duration_minutes}分钟`}</div>
                  <div className="report-item"><strong>题数：</strong>{selectedReport.questions_count}题</div>
                  <div className="report-item"><strong>日期：</strong>{new Date(selectedReport.created_at).toLocaleDateString()}</div>
                </div>

                {selectedReport.feedback && (
                  <>
                    <div className="feedback-section">
                      <h4>总体评价</h4>
                      <p>{selectedReport.feedback.overall}</p>
                    </div>
                    <div className="feedback-section">
                      <h4>优势</h4>
                      <ul>
                        {selectedReport.feedback.strengths?.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                    <div className="feedback-section">
                      <h4>待改进</h4>
                      <ul>
                        {selectedReport.feedback.weaknesses?.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </div>
                  </>
                )}
                {selectedReport.agent_report && (
                  <>
                    <div className="feedback-section">
                      <h4>STAR 改写建议</h4>
                      <ul>
                        {selectedReport.agent_report.star_suggestions?.map((item, index) => (
                          <li key={index}>
                            <strong>{item.question}</strong>
                            <p style={{ whiteSpace: 'pre-wrap' }}>{item.star_rewrite}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="feedback-section">
                      <h4>下一步练习计划</h4>
                      <p style={{ whiteSpace: 'pre-wrap' }}>{selectedReport.agent_report.practice_plan}</p>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
