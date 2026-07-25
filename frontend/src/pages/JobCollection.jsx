import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { getJobs, createJob, batchImportJobs, getJobDetail } from '../api/client';

const initialForm = { title: '', company: '', location: '', salary_range: '', education: '', experience: '', publish_time: '', skills: '', responsibilities: '', requirements: '', source_link: '' };
const cities = ['北京', '上海', '深圳', '杭州', '广州', '成都', '南京', '武汉', 'Remote', '其他'];
const statusMeta = {
  all: { label: '全部', color: '' },
  pending: { label: '待审核', color: 'warning' },
  approved: { label: '已通过', color: 'success' },
  rejected: { label: '已驳回', color: 'error' },
};

export default function JobCollection() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [showBatch, setShowBatch] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [batchText, setBatchText] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [saving, setSaving] = useState(false);
  const [detailJob, setDetailJob] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    getJobs().then(setJobs).catch(() => setMsg({ type: 'error', text: '加载失败' })).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filteredJobs = useMemo(() => {
    if (statusFilter === 'all') return jobs;
    return jobs.filter(j => j.status === statusFilter);
  }, [jobs, statusFilter]);

  const statusCounts = useMemo(() => {
    const counts = { all: jobs.length, pending: 0, approved: 0, rejected: 0 };
    jobs.forEach(j => { if (counts[j.status] !== undefined) counts[j.status]++; });
    return counts;
  }, [jobs]);

  const updateF = (f) => (e) => setForm({ ...form, [f]: e.target.value });

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.title || !form.company) { setMsg({ type: 'error', text: '岗位名称和公司为必填项' }); return; }
    setSaving(true);
    try {
      const skills = form.skills.split(/[,，、\s]+/).map(s => s.trim()).filter(Boolean);
      await createJob({
        title: form.title.trim(),
        company: form.company.trim(),
        location: form.location || '未标注',
        publish_time: form.publish_time || '未标注',
        skills,
        source_link: form.source_link || `https://manual.local/jobs/${Date.now()}`,
      });
      setMsg({ type: 'success', text: '岗位已导入，等待审核' });
      setShowForm(false);
      setForm(initialForm);
      load();
    } catch { setMsg({ type: 'error', text: '创建失败' }); }
    finally { setSaving(false); }
  };

  const handleBatchImport = async () => {
    if (!batchText.trim()) { setMsg({ type: 'error', text: '请输入岗位数据' }); return; }
    setSaving(true);
    try {
      const lines = batchText.trim().split('\n').filter(Boolean);
      const jobList = lines.map((line, index) => {
        const parts = line.split(/[,，]/).map(s => s.trim());
        return { title: parts[0] || '', company: parts[1] || '', location: parts[2] || '未标注', publish_time: '未标注', skills: [], source_link: parts[3] || `https://manual.local/jobs/${Date.now()}-${index}` };
      });
      await batchImportJobs({ jobs: jobList });
      setMsg({ type: 'success', text: `成功导入${jobList.length}个岗位` });
      setShowBatch(false); setBatchText(''); load();
    } catch { setMsg({ type: 'error', text: '批量导入失败' }); }
    finally { setSaving(false); }
  };

  const viewDetail = async (id) => {
    setDetailLoading(true);
    try {
      const data = await getJobDetail(id);
      setDetailJob(data || jobs.find(j => j.id === id));
    } catch {
      setDetailJob(jobs.find(j => j.id === id));
    } finally { setDetailLoading(false); }
  };

  const getSourceBadge = (link) => {
    if (!link) return null;
    const siteMap = { linkedin: 'LinkedIn', indeed: 'Indeed', glassdoor: 'Glassdoor', zhaopin: '智联', '51job': '前程无忧', bosszhipin: 'BOSS直聘', lagou: '拉勾' };
    for (const [key, name] of Object.entries(siteMap)) {
      if (link.includes(key)) return name;
    }
    return null;
  };

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>💼 岗位管理</h2>
      {msg.text && <div className={`alert alert-${msg.type}`} onClick={() => setMsg({ type: '', text: '' })}>{msg.text}</div>}

      {/* 统计卡片 */}
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

      {/* 工具栏 */}
      <div className="toolbar">
        <button className="btn btn-primary" onClick={() => { setShowForm(!showForm); setShowBatch(false); }}>➕ 新增岗位</button>
        <button className="btn btn-outline" onClick={() => { setShowBatch(!showBatch); setShowForm(false); }}>📥 批量导入</button>
        <button className="btn btn-outline" onClick={() => navigate('/jobs/match')}>🎯 岗位匹配</button>
        <button className="btn btn-outline" onClick={() => navigate('/jobs/compare')}>📊 多岗对比</button>
        <button className="btn btn-outline" onClick={() => navigate('/jobs/review')}>📋 岗位审核</button>
      </div>

      {/* 新增岗位表单 */}
      {showForm && (
        <div className="card">
          <h3>新增岗位</h3>
          <form onSubmit={handleCreate} className="form-grid">
            <div className="form-group">
              <label>岗位名称 *</label>
              <input value={form.title} onChange={updateF('title')} placeholder="如：前端开发工程师" />
            </div>
            <div className="form-group">
              <label>公司 *</label>
              <input value={form.company} onChange={updateF('company')} placeholder="公司名称" />
            </div>
            <div className="form-group">
              <label>城市</label>
              <select value={form.location} onChange={updateF('location')}>
                <option value="">选择城市</option>
                {cities.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>薪资范围</label>
              <input value={form.salary_range} onChange={updateF('salary_range')} placeholder="如：20-40K" />
            </div>
            <div className="form-group">
              <label>学历要求</label>
              <select value={form.education} onChange={updateF('education')}>
                <option value="">不限</option>
                <option>大专</option><option>本科</option><option>硕士</option><option>博士</option>
              </select>
            </div>
            <div className="form-group">
              <label>经验要求</label>
              <select value={form.experience} onChange={updateF('experience')}>
                <option value="">不限</option>
                <option>应届生</option><option>1-3年</option><option>3-5年</option><option>5-10年</option><option>10年以上</option>
              </select>
            </div>
            <div className="form-group">
              <label>发布时间</label>
              <input value={form.publish_time} onChange={updateF('publish_time')} placeholder="如：2026-07-24" />
            </div>
            <div className="form-group">
              <label>来源链接</label>
              <input value={form.source_link} onChange={updateF('source_link')} placeholder="留空自动生成本地链接" />
            </div>
            <div className="form-group form-group-full">
              <label>技能要求（逗号分隔）</label>
              <input value={form.skills} onChange={updateF('skills')} placeholder="如：React, TypeScript, Node.js" />
            </div>
            <div className="form-group form-group-full form-actions">
              <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? '保存中...' : '保存'}</button>
              <button type="button" className="btn btn-outline" onClick={() => { setShowForm(false); setForm(initialForm); }}>取消</button>
            </div>
          </form>
        </div>
      )}

      {/* 批量导入 */}
      {showBatch && (
        <div className="card">
          <h3>📥 批量导入岗位</h3>
          <p className="text-muted">每行一个岗位，格式：岗位名称,公司名称,城市,来源链接</p>
          <textarea className="batch-input" value={batchText} onChange={e => setBatchText(e.target.value)} rows={8}
            placeholder={'前端开发工程师,示例科技,北京,https://example.com/job/1\n后端开发工程师,课程项目公司,深圳,https://example.com/job/2'} />
          <div className="batch-actions">
            <button className="btn btn-primary" onClick={handleBatchImport} disabled={saving}>{saving ? '导入中...' : '确认导入'}</button>
            <button className="btn btn-outline" onClick={() => { setShowBatch(false); setBatchText(''); }}>取消</button>
          </div>
        </div>
      )}

      {/* 岗位列表 */}
      <div className="card">
        <h3>📋 {statusMeta[statusFilter].label}岗位 ({filteredJobs.length})</h3>
        {filteredJobs.length === 0 ? (
          <div className="empty">暂无数据</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>岗位</th>
                <th>公司</th>
                <th>地点</th>
                <th>薪资</th>
                <th>学历/经验</th>
                <th>技能</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map(j => (
                <tr key={j.id}>
                  <td><strong>{j.title}</strong></td>
                  <td>{j.company}</td>
                  <td>{j.location || '-'}</td>
                  <td className="text-muted">{j.salary_range || '-'}</td>
                  <td className="text-muted" style={{ fontSize: '.8rem' }}>
                    {[j.education, j.experience].filter(Boolean).join(' / ') || '-'}
                  </td>
                  <td>
                    {j.skills?.length > 0 ? (
                      <div className="skill-tags">
                        {j.skills.slice(0, 3).map((s, i) => <span key={i} className="tag tag-sm">{s}</span>)}
                        {j.skills.length > 3 && <span className="tag tag-sm">+{j.skills.length - 3}</span>}
                      </div>
                    ) : '-'}
                  </td>
                  <td><span className={`tag tag-${statusMeta[j.status]?.color}`}>{statusMeta[j.status]?.label}</span></td>
                  <td className="actions">
                    <button className="btn btn-sm btn-outline" onClick={() => viewDetail(j.id)}>详情</button>
                    <button className="btn btn-sm btn-outline" onClick={() => navigate('/jobs/match', { state: { jobId: j.id } })}>匹配</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 岗位详情弹窗 */}
      {detailJob && (
        <div className="modal-overlay" onClick={() => setDetailJob(null)}>
          <div className="modal modal-detail" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{detailJob.title}</h3>
                <span className="text-muted">{detailJob.company} · {detailJob.location || '未知地点'}</span>
              </div>
              <button className="btn btn-sm btn-outline" onClick={() => setDetailJob(null)}>✕</button>
            </div>
            {detailLoading ? <div className="loading">加载详情...</div> : (
              <div className="modal-body job-detail-body">
                {/* 基本信息 */}
                <div className="detail-meta-grid">
                  {detailJob.salary_range && <div className="meta-item"><span className="meta-label">💰 薪资</span><span>{detailJob.salary_range}</span></div>}
                  {detailJob.education && <div className="meta-item"><span className="meta-label">🎓 学历</span><span>{detailJob.education}</span></div>}
                  {detailJob.experience && <div className="meta-item"><span className="meta-label">⏱ 经验</span><span>{detailJob.experience}</span></div>}
                  <div className="meta-item"><span className="meta-label">📅 发布</span><span>{detailJob.publish_time || '未标注'}</span></div>
                  <div className="meta-item"><span className="meta-label">📌 状态</span><span className={`tag tag-${statusMeta[detailJob.status]?.color}`}>{statusMeta[detailJob.status]?.label || detailJob.status}</span></div>
                  {detailJob.source_site && <div className="meta-item"><span className="meta-label">🔗 来源</span><span>{detailJob.source_site}</span></div>}
                  {getSourceBadge(detailJob.source_link) && <div className="meta-item"><span className="meta-label">🏢 平台</span><span className="tag tag-info">{getSourceBadge(detailJob.source_link)}</span></div>}
                </div>

                {/* 技能标签 */}
                {detailJob.skills?.length > 0 && (
                  <div className="detail-section">
                    <h4>技能要求</h4>
                    <div className="skill-tags">
                      {detailJob.skills.map((s, i) => <span key={i} className="tag">{s}</span>)}
                    </div>
                  </div>
                )}

                {/* 岗位职责 */}
                {detailJob.responsibilities && (
                  <div className="detail-section">
                    <h4>岗位职责</h4>
                    <pre className="detail-text">{detailJob.responsibilities}</pre>
                  </div>
                )}

                {/* 任职要求 */}
                {detailJob.requirements && (
                  <div className="detail-section">
                    <h4>任职要求</h4>
                    <pre className="detail-text">{detailJob.requirements}</pre>
                  </div>
                )}

                {/* 来源链接 */}
                {detailJob.source_link && (
                  <div className="detail-section">
                    <h4>来源链接</h4>
                    <a href={detailJob.source_link} target="_blank" rel="noopener noreferrer" className="link">{detailJob.source_link}</a>
                  </div>
                )}

                {/* 审核意见 */}
                {detailJob.audit_comment && (
                  <div className="detail-section">
                    <h4>审核意见</h4>
                    <div className="audit-comment">{detailJob.audit_comment}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
