import { useEffect, useState } from 'react';
import { getInterviewHistory, getInterviewReport } from '../api/client';
import RadarChart from '../components/RadarChart';
import { mapDimensionScores } from '../utils/dimensionLabels';
import TrendChart from '../components/TrendChart';

export default function InterviewHistory() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getInterviewHistory();
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleViewReport = async (id) => {
    try {
      const report = await getInterviewReport(id);
      setSelectedReport(report);
      setShowModal(true);
    } catch {
      alert('获取报告失败');
    }
  };

  const trendData = history
    .filter((h) => h.score != null || h.overall_score != null)
    .map((h, idx) => ({
      index: idx + 1,
      date: h.timestamp || '--',
      score: h.score ?? h.overall_score ?? 0,
    }));

  const reportRadar = selectedReport?.dimension_scores
    ? mapDimensionScores(selectedReport.dimension_scores)
    : [
        { name: '技术能力', score: 78, maxScore: 100 },
        { name: '项目经验', score: 72, maxScore: 100 },
        { name: '沟通表达', score: 85, maxScore: 100 },
        { name: '问题解决', score: 70, maxScore: 100 },
        { name: '系统设计', score: 65, maxScore: 100 },
        { name: '行业理解', score: 80, maxScore: 100 },
      ];

  return (
    <div className="page">
      <h2>面试历史记录</h2>

      {loading ? (
        <div className="loading">加载中...</div>
      ) : history.length === 0 ? (
        <div className="empty">暂无面试记录，去模拟面试试试吧</div>
      ) : (
        <>
          {/* 趋势图 */}
          {trendData.length >= 2 && (
            <div className="chart-card">
              <h3>成绩趋势</h3>
              <TrendChart
                data={trendData}
                xKey="index"
                yKey="score"
                color="var(--primary)"
              />
            </div>
          )}

          {/* 历史列表 */}
          <div className="review-list">
            {history.map((h) => {
              const score = h.score ?? h.overall_score ?? 0;
              return (
                <div className="review-card" key={h.session_id || h.id}>
                  <div className="review-card-header">
                    <h4>{h.jobTitle || '面试记录'}</h4>
                    <span className={`tag ${score >= 80 ? 'tag-success' : score >= 60 ? 'tag-warning' : ''}`}>
                      {score}分
                    </span>
                  </div>
                  <div className="review-card-body">
                    <div className="review-info">
                      <span>⏰ {new Date(h.timestamp || h.created_at).toLocaleDateString()}</span>
                    </div>
                    {h.feedback?.overall && (
                      <p style={{ fontSize: '.85rem', color: 'var(--text-secondary)', marginTop: 8 }}>
                        {h.feedback.overall.substring(0, 80)}...
                      </p>
                    )}
                  </div>
                  <div className="review-card-actions">
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleViewReport(h.session_id || h.id)}
                    >
                      查看报告
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* 报告弹窗 */}
      {showModal && selectedReport && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 700 }}>
            <div className="modal-header">
              <span style={{ fontWeight: 600 }}>
                面试报告 - {selectedReport.jobTitle || '综合评估'}
              </span>
              <button className="btn btn-sm" onClick={() => setShowModal(false)}>
                关闭
              </button>
            </div>
            <div className="modal-body">
              <div className="result-score">
                <div className="score-circle large">
                  <span className="score-num">{selectedReport.score}</span>
                  <span className="score-unit">分</span>
                </div>
              </div>

              {/* 雷达图 */}
              <div className="result-radar-section">
                <h4>能力维度评估</h4>
                <RadarChart data={reportRadar} />
                <div className="dimension-scores-grid">
                  {reportRadar.map((d) => (
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

              {selectedReport.feedback && (
                <>
                  <div className="feedback-section">
                    <h4>综合评价</h4>
                    <p>{selectedReport.feedback.overall}</p>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div className="feedback-section">
                      <h4>优势亮点</h4>
                      <ul>
                        {selectedReport.feedback.strengths?.map((s, i) => (
                          <li key={i}>{s}</li>
                        )) || <li>暂无</li>}
                      </ul>
                    </div>
                    <div className="feedback-section">
                      <h4>改进方向</h4>
                      <ul>
                        {selectedReport.feedback.weaknesses?.map((w, i) => (
                          <li key={i}>{w}</li>
                        )) || <li>暂无</li>}
                      </ul>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
