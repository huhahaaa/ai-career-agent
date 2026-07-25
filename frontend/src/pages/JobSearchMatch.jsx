import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getApprovedJobs, runMatching, rebuildApprovedJobIndex } from '../api/client';

export default function JobSearchMatch() {
  const location = useLocation();
  const preselectedId = location.state?.jobId;
  const navigate = useNavigate();

  const [jobs, setJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [selectedId, setSelectedId] = useState(preselectedId || '');
  const [searchText, setSearchText] = useState('');
  const [searchMode, setSearchMode] = useState('job'); // 'job' | 'text'
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  useEffect(() => {
    getApprovedJobs()
      .then(data => { setJobs(data); setLoadingJobs(false); })
      .catch(() => { setMsg({ type: 'error', text: '加载岗位列表失败' }); setLoadingJobs(false); });
  }, []);

  useEffect(() => {
    if (preselectedId && jobs.length > 0) setSelectedId(preselectedId);
  }, [preselectedId, jobs]);

  const handleRebuildIndex = async () => {
    setIndexing(true);
    setMsg({ type: '', text: '' });
    try {
      await rebuildApprovedJobIndex();
      setMsg({ type: 'success', text: '向量索引重建成功！可以开始匹配了' });
    } catch (e) {
      setMsg({ type: 'error', text: e.message || '索引重建失败' });
    } finally { setIndexing(false); }
  };

  const doMatch = async () => {
    setSearching(true);
    setMsg({ type: '', text: '' });
    try {
      let resumeText = '';
      let targetPosition = '';
      let topK = 10;

      if (searchMode === 'job') {
        if (!selectedJob) return;
        const parts = [
          selectedJob.title,
          selectedJob.skills?.join(' ') || '',
          selectedJob.responsibilities || '',
          selectedJob.requirements || '',
        ].filter(Boolean);
        resumeText = parts.join('\n');
        targetPosition = selectedJob.title;
      } else if (searchMode === 'text' && searchText.trim()) {
        resumeText = searchText.trim();
        targetPosition = searchText.trim();
      }

      const data = await runMatching(resumeText, targetPosition, topK);
      setResults(data.matches || data.results || data || []);
    } catch (e) {
      setMsg({ type: 'error', text: e.message || '匹配失败，请先重建索引' });
    } finally { setSearching(false); }
  };

  const selectedJob = jobs.find(j => String(j.id) === String(selectedId));

  const formatScore = (s) => {
    if (typeof s === 'number') return s.toFixed(1) + '%';
    return s || '-';
  };

  return (
    <div className="page">
      <h2>🎯 岗位语义匹配</h2>
      {msg.text && <div className={`alert alert-${msg.type}`} onClick={() => setMsg({ type: '', text: '' })}>{msg.text}</div>}

      {/* 索引管理 */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0 }}>匹配引擎</h3>
            <p className="text-muted" style={{ margin: '4px 0 0' }}>基于语义向量的岗位相似度匹配。需要先构建向量索引。</p>
          </div>
          <button className="btn btn-outline" onClick={handleRebuildIndex} disabled={indexing}>
            {indexing ? '🔄 重建中...' : '🔄 重建向量索引'}
          </button>
        </div>
      </div>

      {/* 搜索模式切换 */}
      <div className="card">
        <div className="match-tabs">
          <button className={`match-tab ${searchMode === 'job' ? 'active' : ''}`} onClick={() => setSearchMode('job')}>
            以岗搜岗
          </button>
          <button className={`match-tab ${searchMode === 'text' ? 'active' : ''}`} onClick={() => setSearchMode('text')}>
            文本搜索
          </button>
        </div>

        {searchMode === 'job' ? (
          <div className="match-controls">
            <select value={selectedId} onChange={e => setSelectedId(e.target.value)} style={{ flex: 1 }}>
              <option value="">-- 选择基准岗位 --</option>
              {jobs.map(j => (
                <option key={j.id} value={j.id}>{j.title} @ {j.company} ({j.location})</option>
              ))}
            </select>
            {selectedJob && (
              <div className="selected-job-preview">
                <span className="tag">{selectedJob.company}</span>
                {selectedJob.salary_range && <span className="tag tag-info">{selectedJob.salary_range}</span>}
                <span className="text-muted">{selectedJob.skills?.length || 0} 项技能</span>
              </div>
            )}
            <button className="btn btn-primary" onClick={doMatch} disabled={searching || !selectedId}>
              {searching ? '匹配中...' : '🔍 查找相似岗位'}
            </button>
          </div>
        ) : (
          <div className="match-controls">
            <input
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              placeholder="输入技能关键词或岗位描述"
              onKeyDown={e => e.key === 'Enter' && doMatch()}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" onClick={doMatch} disabled={searching || !searchText.trim()}>
              {searching ? '匹配中...' : '🔍 搜索'}
            </button>
          </div>
        )}
      </div>

      {/* 结果 */}
      {results.length > 0 && (
        <div className="card">
          <h3>匹配结果 ({results.length})</h3>
          <div className="match-results">
            {results.map((item, idx) => {
              const job = item;
              const score = Number(item.score || 0);
              return (
                <div key={idx} className="match-card">
                  <div className="match-card-header">
                    <div className="match-rank">
                      <span className="match-rank-num">#{idx + 1}</span>
                      <span className="match-score" style={{ color: score > 70 ? '#10b981' : score > 40 ? '#f59e0b' : '#ef4444' }}>
                        {formatScore(score)}
                      </span>
                    </div>
                    <div className="match-title">
                      <strong>{job.title}</strong>
                      <span className="text-muted">@ {job.company}</span>
                    </div>
                  </div>
                  <div className="match-card-body">
                    <div className="match-meta-row">
                      {job.location && <span className="tag tag-sm">📍 {job.location}</span>}
                      {job.salary_range && <span className="tag tag-sm tag-info">💰 {job.salary_range}</span>}
                      {job.education && <span className="tag tag-sm">{job.education}</span>}
                      {job.experience && <span className="tag tag-sm">⏱ {job.experience}</span>}
                    </div>
                    {job.skills?.length > 0 && (
                      <div className="skill-tags">
                        {job.skills.slice(0, 8).map((s, i) => <span key={i} className="tag tag-sm">{s}</span>)}
                        {job.skills.length > 8 && <span className="tag tag-sm">+{job.skills.length - 8}</span>}
                      </div>
                    )}
                    {job.reason && (
                      <details className="match-detail-toggle">
                        <summary>匹配原因</summary>
                        <p className="match-detail-text">{job.reason}</p>
                      </details>
                    )}
                    {job.responsibilities && (
                      <details className="match-detail-toggle">
                        <summary>查看职责描述</summary>
                        <p className="match-detail-text">{job.responsibilities.substring(0, 300)}{job.responsibilities.length > 300 ? '...' : ''}</p>
                      </details>
                    )}
                    {job.requirements && (
                      <details className="match-detail-toggle">
                        <summary>查看任职要求</summary>
                        <p className="match-detail-text">{job.requirements.substring(0, 300)}{job.requirements.length > 300 ? '...' : ''}</p>
                      </details>
                    )}
                  </div>
                  <div className="match-card-footer">
                    {job.source_link && (
                      <a href={job.source_link} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline">查看原文</a>
                    )}
                    {job.job_id && (
                      <button className="btn btn-sm btn-outline" onClick={() => navigate('/jobs/compare', { state: { jobId: job.job_id } })}>加入对比</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
