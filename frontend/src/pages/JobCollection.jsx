import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getJobs, createJob, batchImportJobs } from '../api/client';

const initialForm = {
  title: '',
  company: '',
  location: '',
  publish_time: '',
  skills: '',
  source_link: '',
};
const cities = ['北京', '上海', '深圳', '杭州', '广州', '成都', '南京', '武汉', '其他'];

const statusMeta = {
  pending: { label: '待审核', color: 'warning' },
  approved: { label: '已通过', color: 'success' },
  rejected: { label: '已驳回', color: 'error' },
};

export default function JobCollection() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showBatch, setShowBatch] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [batchText, setBatchText] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    getJobs().then(setJobs).catch(() => setMsg({ type: 'error', text: '加载失败' })).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const updateF = (f) => (e) => setForm({ ...form, [f]: e.target.value });

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.title || !form.company) {
      setMsg({ type: 'error', text: '岗位名称和公司为必填项' });
      return;
    }
    setSaving(true);
    try {
      const skills = form.skills.split(/[,，]/).map(s => s.trim()).filter(Boolean);
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
    } catch {
      setMsg({ type: 'error', text: '创建失败' });
    } finally { setSaving(false); }
  };

  const handleBatchImport = async () => {
    if (!batchText.trim()) { setMsg({ type: 'error', text: '请输入岗位数据' }); return; }
    setSaving(true);
    try {
      const lines = batchText.trim().split('\n').filter(Boolean);
      const jobs = lines.map((line, index) => {
        const [title, company, location, sourceLink] = line.split(/[,，]/).map(s => s.trim());
        return {
          title,
          company,
          location: location || '未标注',
          publish_time: '未标注',
          skills: [],
          source_link: sourceLink || `https://manual.local/jobs/${Date.now()}-${index}`,
        };
      });
      await batchImportJobs({ jobs });
      setMsg({ type: 'success', text: `成功导入${jobs.length}个岗位` });
      setShowBatch(false);
      setBatchText('');
      load();
    } catch {
      setMsg({ type: 'error', text: '批量导入失败' });
    } finally { setSaving(false); }
  };

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>💼 岗位管理</h2>
      {msg.text && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={() => { setShowForm(!showForm); setShowBatch(false); }}>
          ➕ 新增岗位
        </button>
        <button className="btn btn-outline" onClick={() => { setShowBatch(!showBatch); setShowForm(false); }}>
          📥 批量导入
        </button>
        <button className="btn btn-outline" onClick={() => navigate('/jobs/match')}>
          🎯 岗位匹配
        </button>
      </div>

      {/* 新增岗位表单 */}
      {showForm && (
        <div className="card">
          <h3>新增岗位</h3>
          <form onSubmit={handleCreate} className="form-grid">
            <div className="form-group">
              <label>岗位名称 *</label>
              <input type="text" value={form.title} onChange={updateF('title')} placeholder="如：前端开发工程师" />
            </div>
            <div className="form-group">
              <label>公司 *</label>
              <input type="text" value={form.company} onChange={updateF('company')} placeholder="公司名称" />
            </div>
            <div className="form-group">
              <label>城市</label>
              <select value={form.location} onChange={updateF('location')}>
                <option value="">选择城市</option>
                {cities.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>发布时间</label>
              <input type="text" value={form.publish_time} onChange={updateF('publish_time')} placeholder="如：2026-07-24 或 未标注" />
            </div>
            <div className="form-group">
              <label>来源链接</label>
              <input type="url" value={form.source_link} onChange={updateF('source_link')} placeholder="留空时生成本地导入链接" />
            </div>
            <div className="form-group form-group-full">
              <label>技能要求(逗号分隔)</label>
              <input type="text" value={form.skills} onChange={updateF('skills')} placeholder="如：React, TypeScript, Node.js" />
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
          <textarea
            className="batch-input"
            value={batchText}
            onChange={e => setBatchText(e.target.value)}
            rows={8}
            placeholder={'前端开发工程师,示例科技,北京,https://example.com/job/1\n后端开发工程师,课程项目公司,深圳,https://example.com/job/2'}
          />
          <div className="batch-actions">
            <button className="btn btn-primary" onClick={handleBatchImport} disabled={saving}>
              {saving ? '导入中...' : '确认导入'}
            </button>
            <button className="btn btn-outline" onClick={() => { setShowBatch(false); setBatchText(''); }}>取消</button>
          </div>
        </div>
      )}

      {/* 岗位列表 */}
      <div className="card">
        <h3>📋 岗位列表 ({jobs.length})</h3>
        {jobs.length === 0 ? (
          <div className="empty">暂无岗位数据</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>岗位</th>
                <th>公司</th>
                <th>城市</th>
                <th>发布时间</th>
                <th>技能</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.id}>
                  <td><strong>{j.title}</strong></td>
                  <td>{j.company}</td>
                  <td>{j.location || '-'}</td>
                  <td>{j.publish_time || '-'}</td>
                  <td>{j.skills?.join('、') || '-'}</td>
                  <td><span className={`tag tag-${statusMeta[j.status]?.color || ''}`}>{statusMeta[j.status]?.label || j.status}</span></td>
                  <td className="actions">
                    <button className="btn btn-sm btn-outline" onClick={() => navigate('/jobs/match', { state: { jobId: j.id } })}>匹配</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
