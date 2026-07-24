import { useState, useEffect } from 'react';
import { getJobs, rebuildApprovedJobIndex, updateJobStatus } from '../api/client';

export default function JobReview() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const load = () => {
    getJobs({ status: 'pending' })
      .then(data => setJobs(Array.isArray(data) ? data : []))
      .catch(() => setMsg({ type: 'error', text: '加载失败' }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAction = async (id, status) => {
    try {
      await updateJobStatus(id, status);
      setMsg({ type: 'success', text: status === 'approved' ? '已通过审核' : '已驳回' });
      load();
    } catch {
      setMsg({ type: 'error', text: '操作失败' });
    }
  };

  const handleReindex = async () => {
    try {
      const result = await rebuildApprovedJobIndex();
      setMsg({ type: 'success', text: `向量索引已更新，共写入 ${result.indexed_count} 个岗位` });
    } catch (error) {
      setMsg({ type: 'error', text: error.message || '向量索引更新失败' });
    }
  };

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>🔍 岗位审核管理</h2>
      {msg.text && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      <div className="toolbar">
        <button className="btn btn-outline" onClick={handleReindex}>更新已审核岗位索引</button>
      </div>

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
                    <span className="text-muted">{j.company} | {j.location || '地点未标注'} | {j.publish_time || '时间未标注'}</span>
                  </div>
                  <span className="tag tag-warning">待审核</span>
                </div>
                <div className="review-card-body">
                  {j.skills?.length > 0 && (
                    <div className="tag-group">
                      {j.skills.map(s => <span key={s} className="tag">{s}</span>)}
                    </div>
                  )}
                  {j.source_link && <a href={j.source_link} target="_blank" rel="noreferrer">查看岗位来源</a>}
                </div>
                <div className="review-card-actions">
                  <button className="btn btn-sm btn-success" onClick={() => handleAction(j.id, 'approved')}>✅ 通过</button>
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
