import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend } from 'recharts';
import { getInterviewHistory, getInterviewReport } from '../api/client';

export default function InterviewHistory() {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    getInterviewHistory()
      .then(setInterviews)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const viewReport = async (id) => {
    setReportLoading(true);
    try {
      const data = await getInterviewReport(id);
      setSelectedReport(data);
    } catch {
      setSelectedReport(interviews.find(i => i.id === id));
    } finally { setReportLoading(false); }
  };

  const trendData = interviews
    .slice()
    .reverse()
    .map((item, i) => ({
      date: new Date(item.created_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }),
      score: item.score,
      index: i + 1,
    }));

  const avgScore = interviews.length ? (interviews.reduce((s, i) => s + i.score, 0) / interviews.length).toFixed(1) : 0;

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>📋 面试记录与报告</h2>

      {interviews.length > 0 && (
        <>
          {/* 统计概览 */}
          <div className="stats-grid">
            <div className="stat-card" style={{ borderTopColor: '#6366f1' }}>
              <div className="stat-icon">🎤</div>
              <div className="stat-info">
                <div className="stat-value">{interviews.length}</div>
                <div className="stat-label">总面试次数</div>
              </div>
            </div>
            <div className="stat-card" style={{ borderTopColor: '#22c55e' }}>
              <div className="stat-icon">⭐</div>
              <div className="stat-info">
                <div className="stat-value">{avgScore}</div>
                <div className="stat-label">平均得分</div>
              </div>
            </div>
            <div className="stat-card" style={{ borderTopColor: '#f59e0b' }}>
              <div className="stat-icon">🏆</div>
              <div className="stat-info">
                <div className="stat-value">{Math.max(...interviews.map(i => i.score))}</div>
                <div className="stat-label">最高得分</div>
              </div>
            </div>
          </div>

          {/* 面试趋势图 */}
          <div className="chart-card">
            <h3>📈 历次面试得分趋势</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={v => `${v}分`} />
                <Line type="monotone" dataKey="score" name="面试得分" stroke="#6366f1" strokeWidth={3} dot={{ r: 6, fill: '#6366f1' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* 面试列表 */}
      <div className="card">
        <div className="card-header-row">
          <h3>📝 面试记录</h3>
          <button className="btn btn-primary" onClick={() => navigate('/interview')}>开始新面试</button>
        </div>
        {interviews.length === 0 ? (
          <div className="empty">
            <p>暂无面试记录</p>
            <button className="btn btn-primary" onClick={() => navigate('/interview')}>开始第一次面试</button>
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
              {interviews.map(item => (
                <tr key={item.id}>
                  <td>{item.company}</td>
                  <td>{item.job_title}</td>
                  <td><span className="tag">{item.mode}</span></td>
                  <td>
                    <strong style={{ color: item.score >= 80 ? '#22c55e' : item.score >= 60 ? '#f59e0b' : '#ef4444' }}>
                      {item.score}
                    </strong>
                  </td>
                  <td>{item.duration_minutes}分钟</td>
                  <td>{item.questions_count}题</td>
                  <td>{new Date(item.created_at).toLocaleDateString()}</td>
                  <td>
                    <button className="btn btn-sm btn-outline" onClick={() => viewReport(item.id)}>
                      📊 查看报告
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
              <h3>📊 面试报告 - {selectedReport.company}</h3>
              <button className="btn btn-sm btn-outline" onClick={() => setSelectedReport(null)}>✕</button>
            </div>
            {reportLoading ? (
              <div className="loading">加载报告中...</div>
            ) : (
              <div className="modal-body">
                <div className="result-score">
                  <div className="score-circle large" style={{ borderColor: selectedReport.score >= 80 ? '#22c55e' : selectedReport.score >= 60 ? '#f59e0b' : '#ef4444' }}>
                    <span className="score-num">{selectedReport.score}</span>
                    <span className="score-unit">分</span>
                  </div>
                </div>

                <div className="report-grid">
                  <div className="report-item"><strong>岗位：</strong>{selectedReport.job_title}</div>
                  <div className="report-item"><strong>时长：</strong>{selectedReport.duration_minutes}分钟</div>
                  <div className="report-item"><strong>题数：</strong>{selectedReport.questions_count}题</div>
                  <div className="report-item"><strong>日期：</strong>{new Date(selectedReport.created_at).toLocaleDateString()}</div>
                </div>

                {selectedReport.feedback && (
                  <>
                    {/* 多维度评分雷达图 */}
                    {selectedReport.feedback.dimension_scores && (
                      <div className="result-radar-section" style={{ marginBottom: '16px' }}>
                        <h4 style={{ textAlign: 'center', marginBottom: '8px' }}>🎯 多维度能力评估</h4>
                        <ResponsiveContainer width="100%" height={280}>
                          <RadarChart
                            data={Object.entries(selectedReport.feedback.dimension_scores).map(([key, val]) => ({
                              dimension: key === 'star_method' ? 'STAR法则' :
                                        key === 'technical_accuracy' ? '技术准确度' :
                                        key === 'communication' ? '沟通表达' :
                                        key === 'problem_solving' ? '问题解决' :
                                        key === 'code_quality' ? '代码质量' :
                                        key === 'project_experience' ? '项目经验' : key,
                              score: val,
                            }))}
                            cx="50%" cy="50%" outerRadius="70%"
                          >
                            <PolarGrid stroke="#e5e7eb" />
                            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
                            <PolarRadiusAxis angle={30} domain={[0, 100]} />
                            <Radar name="得分" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    <div className="feedback-section">
                      <h4>📝 总体评价</h4>
                      <p>{selectedReport.feedback.overall}</p>
                    </div>
                    <div className="feedback-section">
                      <h4>💪 优势</h4>
                      <ul>
                        {selectedReport.feedback.strengths?.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                    <div className="feedback-section">
                      <h4>📚 待改进</h4>
                      <ul>
                        {selectedReport.feedback.weaknesses?.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
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
