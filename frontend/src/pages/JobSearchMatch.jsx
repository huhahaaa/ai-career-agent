import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getMatches, runMatching } from '../api/client';

export default function JobSearchMatch() {
  const [keyword, setKeyword] = useState('');
  const [city, setCity] = useState('');
  const [matches, setMatches] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });
  const navigate = useNavigate();

  const handleSearch = async () => {
    setLoading(true);
    setMsg({ type: '', text: '' });
    try {
      const data = await getMatches();
      let filtered = data;
      if (keyword) filtered = filtered.filter(m => m.job_title.includes(keyword) || m.company.includes(keyword));
      setMatches(filtered);
      if (filtered.length === 0) setMsg({ type: 'info', text: '暂无匹配结果' });
    } catch {
      setMsg({ type: 'error', text: '匹配查询失败' });
    } finally { setLoading(false); }
  };

  const handleRunMatching = async () => {
    setLoading(true);
    try {
      const data = await runMatching('r1');
      setMatches(data.matches);
      setMsg({ type: 'success', text: '匹配计算完成' });
    } catch {
      setMsg({ type: 'error', text: '匹配计算失败' });
    } finally { setLoading(false); }
  };

  const getScoreColor = (s) => s >= 80 ? '#22c55e' : s >= 60 ? '#f59e0b' : '#ef4444';

  return (
    <div className="page">
      <h2>🎯 岗位搜索与匹配</h2>

      {/* 搜索栏 */}
      <div className="card">
        <div className="search-bar">
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="输入岗位或公司关键词搜索..."
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
            🔍 {loading ? '匹配中...' : '开始匹配'}
          </button>
          <button className="btn btn-outline" onClick={handleRunMatching} disabled={loading}>
            🚀 重新计算匹配
          </button>
        </div>
      </div>

      {msg.text && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      {/* 匹配结果 */}
      {matches && matches.length > 0 && (
        <>
          <div className="chart-card">
            <h3>📊 匹配分数对比</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={matches.map(m => ({ name: `${m.company.slice(0, 4)}(${m.job_title.slice(0, 4)})`, score: m.overall_score, color: getScoreColor(m.overall_score) }))} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => `${v}分`} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {matches.map((m, idx) => (
                    <rect key={idx} fill={getScoreColor(m.overall_score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="match-grid">
            {matches.map(m => (
              <div key={m.job_id} className="match-card" onClick={() => navigate('/jobs/compare', { state: { matches } })}>
                <div className="match-header">
                  <div>
                    <h4>{m.job_title}</h4>
                    <span className="text-muted">{m.company}</span>
                  </div>
                  <div className="match-score" style={{ color: getScoreColor(m.overall_score) }}>
                    <span className="score-num">{m.overall_score}</span>
                    <span className="score-unit">分</span>
                  </div>
                </div>
                <div className="match-details">
                  <div className="match-stat">
                    <span>技能匹配</span>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${m.skill_match_score}%`, backgroundColor: getScoreColor(m.skill_match_score) }} />
                    </div>
                    <strong>{m.skill_match_score}%</strong>
                  </div>
                  <div className="match-stat">
                    <span>经验匹配</span>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${m.experience_match_score}%`, backgroundColor: getScoreColor(m.experience_match_score) }} />
                    </div>
                    <strong>{m.experience_match_score}%</strong>
                  </div>
                  <div className="match-stat">
                    <span>学历匹配</span>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${m.education_match_score}%`, backgroundColor: getScoreColor(m.education_match_score) }} />
                    </div>
                    <strong>{m.education_match_score}%</strong>
                  </div>
                </div>
                <div className="match-skills">
                  <div className="skill-section">
                    <span className="skill-label success">✅ 匹配技能</span>
                    <div className="tag-group">
                      {m.matched_skills.map(s => <span key={s} className="tag tag-success">{s}</span>)}
                    </div>
                  </div>
                  {m.missing_skills.length > 0 && (
                    <div className="skill-section">
                      <span className="skill-label error">⚠️ 待提升技能</span>
                      <div className="tag-group">
                        {m.missing_skills.map(s => <span key={s} className="tag tag-error">{s}</span>)}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!matches && !loading && !msg.text && (
        <div className="card">
          <div className="empty">
            <p>👆 点击"开始匹配"按钮，查看你的简历与岗位的匹配度</p>
          </div>
        </div>
      )}
    </div>
  );
}
