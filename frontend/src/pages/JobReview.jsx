import { useState, useEffect, useMemo } from 'react';
import { getJobs, updateJobStatus } from '../api/client';

const statusMeta = {
  all: { label: '全部', color: '' },
  pending: { label: '待审核', color: 'warning' },
  approved: { label: '已通过', color: 'success' },
  rejected: { label: '已驳回', color: 'error' },
};

export default function JobReview() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [auditing, setAuditing] = useState(null); // job id being audited
  const [comment, setComment] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });

  const load = () => {
    setLoading(true);
    getJobs()
      .then(setJobs)
      .catch(() => setMsg({ type: 'error', text: '加载岗位列表失败' }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filteredJobs = useMemo(() => {
    if (statusFilter === 'all') return jobs;
    return jobs.filter(j => j.status === statusFilter);
  }, [jobs, statusFilter]);

  const statusCounts = useMemo(() => {
    const c = { all: jobs.length, pending: 0, approved: 0, rejected: 0 };
    jobs.forEach(j => { if (c[j.status] !== undefined) c[j.status]++; });
    return c;
  }, [jobs]);

  const handleAudit = async (jobId, status) => {
    setAuditing(jobId);
    try {
      await updateJobStatus(jobId, status, comment || (status === 'approved' ? '审核通过' : '不符合要求'));
      setMsg({ type: 'success', text: `岗位已${status === 'approved' ? '通过' : '驳回'}` });
      setComment('');
      load();
    } catch (e) {
      setMsg({ type: 'error', text: e.message || '审核操作失败' });
    } finally { setAuditing(null); }
  };

  const openSource = (link) => {
    if (link && link.startsWith('http')) window.open(link, '_blank', 'noopener');
  };

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>📋 岗位审核</h2>
      {msg.text && <div className={`alert alert-${msg.type}`} onClick={() => setMsg({ type: '', text: '' })}>{msg.text}</div>}

      {/* 状态统计 */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {['all', 'pending', 'approved', 'rejected'].map(k => (
          <div
            key={k}
            className={`stat-card ${statusFilter === k ? 'stat-card-active' : ''}`}
            style={{ borderTopColor: k === 'all' ? '#6366f1' : k === 'approved' ? '#10b981' : k === 'pending' ? '#f59e0b' : '#ef4444', cursor: 'pointer' }}
            onClick={() => setStatusFilter(k)}
          >
            <div className="stat-icon">{k === 'all' ? '📊' : k === 'approved' ? '✅' : k === 'pending' ? '⏳' : '❌'}</div>
            <div className="stat-info">
              <div className="stat-value">{statusCounts[k]}</div>
              <div className="stat-label">{statusMeta[k].label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* 岗位列表 */}
      <div className="card">
        <div className="card-header-row">
          <h3>{statusMeta[statusFilter].label}岗位 ({filteredJobs.length})</h3>
          {statusFilter === 'pending' && filteredJobs.length > 0 && (
            <div>
              <input
                placeholder="批量审核备注（可选）"
                value={comment}
                onChange={e => setComment(e.target.value)}
                style={{ width: 200, marginRight: 8, padding: '6px 10px', fontSize: '.82rem' }}
              />
            </div>
          )}
        </div>

        {filteredJobs.length === 0 ? (
          <div className="empty">
            {statusFilter === 'pending' ? '🎉 没有待审核的岗位' : '暂无该状态的岗位'}
          </div>
        ) : (
          <div className="review-grid">
            {filteredJobs.map(job => (
              <div key={job.id} className="review-card">
                <div className="review-card-header">
                  <div className="review-card-title">
                    <h4>{job.title}</h4>
                    <span className="text-muted">{job.company}</span>
                  </div>
                  <span className={`tag tag-${statusMeta[job.status]?.color}`}>{statusMeta[job.status]?.label}</span>
                </div>

                <div className="review-card-meta">
                  {job.location && <span className="tag tag-sm">📍 {job.location}</span>}
                  {job.salary_range && <span className="tag tag-sm tag-info">{job.salary_range}</span>}
                  {job.education && <span className="tag tag-sm">🎓 {job.education}</span>}
                  {job.experience && <span className="tag tag-sm">⏱ {job.experience}</span>}
                </div>

                {job.skills?.length > 0 && (
                  <div className="skill-tags">
                    {job.skills.slice(0, 6).map((s, i) => <span key={i} className="tag tag-sm">{s}</span>)}
                    {job.skills.length > 6 && <span className="tag tag-sm">+{job.skills.length - 6}</span>}
                  </div>
                )}

                <div className="review-card-detail">
                  {job.responsibilities && (
                    <p className="review-text">{job.responsibilities.substring(0, 120)}{job.responsibilities.length > 120 ? '...' : ''}</p>
                  )}
                  {!job.responsibilities && job.requirements && (
                    <p className="review-text">{job.requirements.substring(0, 120)}{job.requirements.length > 120 ? '...' : ''}</p>
                  )}
                </div>

                <div className="review-card-footer">
                  <div className="review-card-info">
                    {job.source_link && (
                      <button className="btn btn-sm btn-text" onClick={() => openSource(job.source_link)}>
                        🔗 查看来源
                      </button>
                    )}
                    <span className="text-muted" style={{ fontSize: '.72rem' }}>
                      发布: {job.publish_time || '未标注'}
                    </span>
                  </div>

                  <div className="review-card-actions">
                    {job.status === 'pending' && (
                      <>
                        <button
                          className="btn btn-sm btn-success"
                          onClick={() => handleAudit(job.id, 'approved')}
                          disabled={auditing === job.id}
                        >
                          ✓ 通过
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => handleAudit(job.id, 'rejected')}
                          disabled={auditing === job.id}
                        >
                          ✕ 驳回
                        </button>
                      </>
                    )}
                    {job.audit_comment && (
                      <span className="review-comment-tip" title={job.audit_comment}>
                        💬 {job.audit_comment.substring(0, 20)}{job.audit_comment.length > 20 ? '...' : ''}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
