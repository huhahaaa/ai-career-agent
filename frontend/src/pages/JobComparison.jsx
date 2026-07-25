import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { getApprovedJobs } from '../api/client';

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

function getAllSkills(jobs) {
  const set = new Set();
  jobs.forEach(j => (j.skills || []).forEach(s => set.add(s)));
  return Array.from(set);
}

export default function JobComparison() {
  const [allJobs, setAllJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState([]);
  const [detailJobs, setDetailJobs] = useState([]);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    getApprovedJobs()
      .then(data => { setAllJobs(data); setLoading(false); })
      .catch(e => { setError(e.message || '加载失败'); setLoading(false); });
  }, []);

  const toggleSelect = (id) => {
    setSelected(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= 5) return prev;
      return [...prev, id];
    });
  };

  const startCompare = useCallback(async () => {
    if (selected.length < 2) { setError('请至少选择2个岗位'); return; }
    setComparing(true);
    setError('');
    try {
      const details = selected.map(id => allJobs.find(job => String(job.id) === String(id))).filter(Boolean);
      setDetailJobs(details);
    } catch (e) {
      setError('加载岗位详情失败');
    } finally {
      setComparing(false);
    }
  }, [selected, allJobs]);

  const clearCompare = () => { setDetailJobs([]); setSelected([]); };

  // ---- chart data ----
  const allSkills = getAllSkills(detailJobs);
  const radarData = allSkills.map(skill => {
    const entry = { skill };
    detailJobs.forEach((j, i) => {
      entry[`job${i}`] = (j.skills || []).includes(skill) ? 100 : 0;
    });
    return entry;
  });

  const basicCompareData = detailJobs.map(j => ({
    name: `${j.company} - ${j.title}`.substring(0, 20),
    salaryRank: j.salary_range ? 1 : 0,
    educationRank: j.education?.includes('硕士') ? 5 : j.education?.includes('本科') ? 3 : 1,
    skillsCount: (j.skills || []).length,
  }));

  const skillCountData = detailJobs.map(j => ({
    name: j.company?.substring(0, 12) || '?',
    skills: (j.skills || []).length,
  }));

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>📊 多岗对比</h2>
      {error && <div className="alert alert-error">{error}</div>}

      {/* === Select === */}
      {detailJobs.length === 0 && (
        <div className="card">
          <h3>选择对比岗位（已选 {selected.length}/5）</h3>
          <p className="text-muted">点击行选择要对比的岗位，最多5个</p>
          {allJobs.length === 0 ? (
            <div className="empty">暂无已审核通过的岗位</div>
          ) : (
            <>
              <table className="table">
                <thead>
                  <tr>
                    <th>选择</th><th>岗位</th><th>公司</th><th>地点</th><th>薪资</th><th>技能数</th>
                  </tr>
                </thead>
                <tbody>
                  {allJobs.map(j => (
                    <tr
                      key={j.id}
                      className={selected.includes(j.id) ? 'row-selected' : ''}
                      onClick={() => toggleSelect(j.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <span className={`compare-checkbox ${selected.includes(j.id) ? 'checked' : ''}`}>
                          {selected.includes(j.id) ? '✓' : '○'}
                        </span>
                      </td>
                      <td><strong>{j.title}</strong></td>
                      <td>{j.company}</td>
                      <td>{j.location}</td>
                      <td className="text-muted">{j.salary_range || '-'}</td>
                      <td>{j.skills?.length || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="batch-actions">
                <button className="btn btn-primary" onClick={startCompare} disabled={selected.length < 2 || comparing}>
                  {comparing ? '加载中...' : `开始对比 (${selected.length})`}
                </button>
                <button className="btn btn-outline" onClick={() => setSelected([])}>清除选择</button>
              </div>
            </>
          )}
        </div>
      )}

      {/* === Results === */}
      {detailJobs.length >= 2 && (
        <>
          <div className="toolbar">
            <button className="btn btn-outline" onClick={clearCompare}>← 返回选择</button>
            <button className="btn btn-outline" onClick={() => navigate('/jobs')}>岗位列表</button>
          </div>

          {/* Basic Info Table */}
          <div className="card">
            <h3>基本信息对比</h3>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>维度</th>
                    {detailJobs.map((j, i) => (
                      <th key={i} style={{ borderBottomColor: COLORS[i] }}>{j.company}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr><td><strong>岗位</strong></td>{detailJobs.map((j, i) => <td key={i}>{j.title}</td>)}</tr>
                  <tr><td><strong>地点</strong></td>{detailJobs.map((j, i) => <td key={i}>{j.location || '-'}</td>)}</tr>
                  <tr><td><strong>薪资</strong></td>{detailJobs.map((j, i) => <td key={i}>{j.salary_range || '-'}</td>)}</tr>
                  <tr><td><strong>学历</strong></td>{detailJobs.map((j, i) => <td key={i}>{j.education || '-'}</td>)}</tr>
                  <tr><td><strong>经验</strong></td>{detailJobs.map((j, i) => <td key={i}>{j.experience || '-'}</td>)}</tr>
                  <tr><td><strong>技能数</strong></td>{detailJobs.map((j, i) => <td key={i}>{(j.skills || []).length}</td>)}</tr>
                  <tr><td><strong>来源</strong></td>{detailJobs.map((j, i) => <td key={i} className="text-muted">{j.source_site || '-'}</td>)}</tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Skills Radar Chart */}
          {allSkills.length > 0 && (
            <div className="card">
              <h3>技能覆盖雷达图</h3>
              <div className="chart-container" style={{ height: 400 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="skill" fontSize={12} />
                    {detailJobs.map((j, i) => (
                      <Radar key={i} name={j.company?.substring(0, 10) || `Job${i}`} dataKey={`job${i}`} stroke={COLORS[i]} fill={COLORS[i]} fillOpacity={0.1} />
                    ))}
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Skills Count Bar Chart */}
          <div className="card">
            <h3>技能数量对比</h3>
            <div className="chart-container" style={{ height: 250 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={skillCountData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" fontSize={12} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="skills" name="技能数量" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Skills Detail Comparison */}
          {allSkills.length > 0 && (
            <div className="card">
              <h3>技能详情对比</h3>
              <div className="table-scroll">
                <table className="table">
                  <thead>
                    <tr>
                      <th>技能</th>
                      {detailJobs.map((j, i) => (
                        <th key={i} style={{ borderBottomColor: COLORS[i], textAlign: 'center' }}>
                          {j.company?.substring(0, 8)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {allSkills.map(skill => (
                      <tr key={skill}>
                        <td><span className="tag">{skill}</span></td>
                        {detailJobs.map((j, i) => (
                          <td key={i} style={{ textAlign: 'center' }}>
                            {(j.skills || []).includes(skill)
                              ? <span style={{ color: '#10b981', fontWeight: 700 }}>✓</span>
                              : <span style={{ color: '#d1d5db' }}>—</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Requirements / Responsibilities comparison */}
          {detailJobs.some(j => j.responsibilities || j.requirements) && (
            <div className="card">
              <h3>岗位描述对比</h3>
              <div className="compare-descriptions">
                {detailJobs.map((j, i) => (
                  <div key={i} className="compare-desc-panel" style={{ borderTopColor: COLORS[i] }}>
                    <h4 style={{ color: COLORS[i] }}>{j.company} - {j.title}</h4>
                    {j.responsibilities && (
                      <div className="desc-block">
                        <span className="desc-label">岗位职责</span>
                        <pre className="compare-text">{j.responsibilities}</pre>
                      </div>
                    )}
                    {j.requirements && (
                      <div className="desc-block">
                        <span className="desc-label">任职要求</span>
                        <pre className="compare-text">{j.requirements}</pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
