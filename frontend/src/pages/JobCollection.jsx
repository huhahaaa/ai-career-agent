import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getJobs, createJob, batchImportJobs } from '../api/client';

const initialForm = { title: '', company: '', city: '', salary_min: '', salary_max: '', experience: '', education: '本科', skills_required: '', description: '' };
const cities = ['北京', '上海', '深圳', '杭州', '广州', '成都', '南京', '武汉', '其他'];
const experienceOpts = ['应届', '1年以下', '1-3年', '3-5年', '5-10年', '10年以上'];

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
      const skills = form.skills_required.split(/[,，]/).map(s => s.trim()).filter(Boolean);
      await createJob({ ...form, salary_min: Number(form.salary_min) || 0, salary_max: Number(form.salary_max) || 0, skills_required: skills });
      setMsg({ type: 'success', text: '创建成功' });
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
      const jobs = lines.map(line => {
        const [title, company, city] = line.split(/[,，]/).map(s => s.trim());
        return { title, company, city: city || '北京', status: 'pending', skills_required: [], description: '' };
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
              <select value={form.city} onChange={updateF('city')}>
                <option value="">选择城市</option>
                {cities.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>经验要求</label>
              <select value={form.experience} onChange={updateF('experience')}>
                <option value="">不限</option>
                {experienceOpts.map(e => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>最低薪资(K)</label>
              <input type="number" value={form.salary_min} onChange={updateF('salary_min')} placeholder="如：15" />
            </div>
            <div className="form-group">
              <label>最高薪资(K)</label>
              <input type="number" value={form.salary_max} onChange={updateF('salary_max')} placeholder="如：30" />
            </div>
            <div className="form-group form-group-full">
              <label>技能要求(逗号分隔)</label>
              <input type="text" value={form.skills_required} onChange={updateF('skills_required')} placeholder="如：React, TypeScript, Node.js" />
            </div>
            <div className="form-group form-group-full">
              <label>岗位描述</label>
              <textarea value={form.description} onChange={updateF('description')} rows={3} placeholder="岗位职责描述..." />
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
          <p className="text-muted">每行一个岗位，格式：岗位名称,公司名称,城市</p>
          <textarea
            className="batch-input"
            value={batchText}
            onChange={e => setBatchText(e.target.value)}
            rows={8}
            placeholder={'前端开发工程师,字节跳动,北京\n后端开发工程师,腾讯,深圳\n全栈工程师,阿里巴巴,杭州'}
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
                <th>薪资范围</th>
                <th>经验</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.id}>
                  <td><strong>{j.title}</strong></td>
                  <td>{j.company}</td>
                  <td>{j.city}</td>
                  <td>{j.salary_min / 1000}k - {j.salary_max / 1000}k</td>
                  <td>{j.experience || '-'}</td>
                  <td><span className={`tag tag-${j.status === 'published' ? 'success' : 'warning'}`}>{j.status === 'published' ? '已发布' : '待审核'}</span></td>
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
