import { useState, useEffect } from 'react';
import { getJobs, updateJobStatus } from '../api/client';

export default function JobReview() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const load = () => {
    getJobs({ status: 'pending' })
      .then(data => setJobs(Array.isArray(data) ? data : data.filter(j => j.status === 'pending')))
      .catch(() => setMsg({ type: 'error', text: '加载失败' }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAction = async (id, status) => {
    try {
      await updateJobStatus(id, status);
      setMsg({ type: 'success', text: status === 'published' ? '已通过审核' : '已驳回' });
      load();
    } catch {
      setMsg({ type: 'error', text: '操作失败' });
    }
  };

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>🔍 岗位审核管理</h2>
      {msg.text && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      <div className="card">
        <h3>待审核岗位 ({jobs.length})</h3>
        {jobs.length === 0 ? (
          <div className="empty">✅ 暂无待审核的岗位</div>
        ) : (
          <div className="review-list">
            {jobs.map(j => (
              <div key={j.id} className="review-card">
                <div className="review-card-header">
                  <div>
                    <h4>{j.title}</h4>
                    <span className="text-muted">{j.company} | {j.city} | {j.experience || '经验不限'}</span>
                  </div>
                  <span className="tag tag-warning">待审核</span>
                </div>
                <div className="review-card-body">
                  <div className="review-info">
                    <span>💰 {j.salary_min / 1000}k - {j.salary_max / 1000}k</span>
                    <span>🎓 {j.education || '本科'}</span>
                  </div>
                  {j.skills_required?.length > 0 && (
                    <div className="tag-group">
                      {j.skills_required.map(s => <span key={s} className="tag">{s}</span>)}
                    </div>
                  )}
                  {j.description && <p className="info-desc">{j.description}</p>}
                </div>
                <div className="review-card-actions">
                  <button className="btn btn-sm btn-success" onClick={() => handleAction(j.id, 'published')}>✅ 通过</button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleAction(j.id, 'rejected')}>❌ 驳回</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
