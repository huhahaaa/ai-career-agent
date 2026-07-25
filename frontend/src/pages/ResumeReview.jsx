import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { auditResume, getResumeDetail, getResumes } from '../api/client';

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : '-';
}

function statusLabel(status) {
  return ({ pending: '待审核', approved: '已审核', rejected: '已驳回' })[status] || status || '-';
}

function statusColor(status) {
  return ({ pending: 'warning', approved: 'success', rejected: 'error' })[status] || 'info';
}

function latestVersion(detail) {
  const versions = detail?.versions || [];
  return versions[versions.length - 1] || null;
}

export default function ResumeReview() {
  const location = useLocation();
  const navigate = useNavigate();
  const [resumes, setResumes] = useState([]);
  const [selectedId, setSelectedId] = useState(location.state?.resumeId || '');
  const [detail, setDetail] = useState(null);
  const [targetPosition, setTargetPosition] = useState(location.state?.targetPosition || '');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [auditing, setAuditing] = useState(false);
  const [message, setMessage] = useState('');

  const version = latestVersion(detail);
  const report = detail?.latest_report || null;
  const scoreData = report ? [{ name: '综合评分', score: report.score }] : [];

  const auditButtonText = useMemo(() => {
    if (auditing) return '审核中...';
    return report ? '重新审核' : '开始审核';
  }, [auditing, report]);

  const loadResumes = async () => {
    setLoading(true);
    setMessage('');
    try {
      const data = await getResumes();
      setResumes(data || []);
      if (!selectedId && data?.length) {
        setSelectedId(data[0].id);
      }
    } catch (error) {
      setMessage(error.message || '简历列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async id => {
    if (!id) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setMessage('');
    try {
      const data = await getResumeDetail(id);
      setDetail(data);
    } catch (error) {
      setMessage(error.message || '简历详情加载失败');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadResumes();
  }, []);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId]);

  const handleAudit = async () => {
    const resumeText = version?.content || '';
    if (resumeText.trim().length < 10) {
      setMessage('当前简历文本过短，无法审核。TXT/MD 文件可直接解析；PDF/DOC/DOCX 后续还需要接入正文解析。');
      return;
    }

    setAuditing(true);
    setMessage('');
    try {
      await auditResume({
        resumeId: Number(selectedId),
        resumeText: resumeText.trim(),
        targetPosition: targetPosition.trim(),
      });
      await Promise.all([loadDetail(selectedId), loadResumes()]);
      setMessage('简历审核已完成，结果来自后端真实接口。');
    } catch (error) {
      setMessage(error.message || '简历审核失败');
    } finally {
      setAuditing(false);
    }
  };

  if (loading) return <div className="loading">加载真实简历...</div>;

  return (
    <div className="page">
      <h2>简历审核</h2>

      {message && <div className={`alert ${message.includes('失败') || message.includes('无法') ? 'alert-error' : 'alert-info'}`}>{message}</div>}

      <div className="card">
        <div className="card-header-row">
          <h3>真实简历列表</h3>
          <button className="btn btn-sm btn-outline" onClick={() => navigate('/resume')}>去上传简历</button>
        </div>
        {resumes.length === 0 ? (
          <div className="empty">暂无真实简历，请先在简历管理页上传 TXT 或 MD 简历。</div>
        ) : (
          <div className="form-grid">
            <div className="form-group">
              <label>选择简历</label>
              <select value={selectedId} onChange={event => setSelectedId(event.target.value)}>
                {resumes.map(item => (
                  <option key={item.id} value={item.id}>
                    {item.filename} - {statusLabel(item.status)}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>目标岗位</label>
              <input
                value={targetPosition}
                onChange={event => setTargetPosition(event.target.value)}
                placeholder="如：Python 后端工程师"
              />
            </div>
          </div>
        )}
      </div>

      {detailLoading && <div className="loading">加载简历详情...</div>}

      {detail && !detailLoading && (
        <>
          <div className="card">
            <div className="resume-header">
              <div className="resume-avatar">📄</div>
              <div className="resume-basic">
                <h3>{detail.filename}</h3>
                <p>版本 v{detail.version} | 上传时间：{formatTime(detail.created_at)}</p>
              </div>
              <div className="review-badge">
                <span className={`tag tag-${statusColor(detail.status)}`}>{statusLabel(detail.status)}</span>
                {report && <div className="review-score">综合评分：{report.score} 分</div>}
              </div>
            </div>

            <div className="form-group">
              <label>简历正文</label>
              <textarea value={version?.content || ''} readOnly rows={9} />
            </div>

            <button className="btn btn-primary" onClick={handleAudit} disabled={auditing}>
              {auditButtonText}
            </button>
          </div>

          {report ? (
            <>
              <div className="charts-row">
                <div className="chart-card">
                  <h3>审核评分</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={scoreData} margin={{ top: 20, right: 20, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis domain={[0, 100]} />
                      <Tooltip formatter={value => `${value} 分`} />
                      <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                        <Cell fill={report.score >= 80 ? '#16a34a' : report.score >= 60 ? '#d97706' : '#dc2626'} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="card">
                  <h3>审核结论</h3>
                  <div className="info-block">
                    <div className="info-title">风险等级：{report.risk_level}</div>
                    <div className="info-sub">生成时间：{formatTime(report.created_at)}</div>
                  </div>
                  <div className="tag-group">
                    {(report.missing_keywords || []).length > 0
                      ? report.missing_keywords.map(item => <span key={item} className="tag tag-warning">{item}</span>)
                      : <span className="tag tag-success">暂无明确缺失关键词</span>}
                  </div>
                </div>
              </div>

              <div className="card">
                <h3>风险问题</h3>
                {(report.risk_flags || []).length === 0 ? (
                  <div className="empty">暂无明显风险问题</div>
                ) : (
                  <ul className="feedback-section">
                    {report.risk_flags.map((item, index) => <li key={index}>{item}</li>)}
                  </ul>
                )}
              </div>

              <div className="card">
                <h3>修改建议</h3>
                <ul className="feedback-section">
                  {(report.suggestions || []).map((item, index) => <li key={index}>{item}</li>)}
                </ul>
              </div>
            </>
          ) : (
            <div className="card">
              <div className="empty">这份简历还没有审核报告，点击“开始审核”生成真实结果。</div>
            </div>
          )}

          {(detail.audit_reports || []).length > 1 && (
            <div className="card">
              <h3>历史审核记录</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>评分</th>
                    <th>风险等级</th>
                    <th>问题数</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.audit_reports.map(item => (
                    <tr key={item.id}>
                      <td>{formatTime(item.created_at)}</td>
                      <td>{item.score}</td>
                      <td>{item.risk_level}</td>
                      <td>{item.risk_flags?.length || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
