import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { runMatching } from '../api/client';

export default function JobSearchMatch() {
  const [resumeText, setResumeText] = useState('');
  const [targetPosition, setTargetPosition] = useState('');
  const [keyword, setKeyword] = useState('');
  const [matches, setMatches] = useState([]);
  const [hasRun, setHasRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  const visibleMatches = useMemo(() => {
    const normalized = keyword.trim().toLowerCase();
    if (!normalized) return matches;
    return matches.filter(item =>
      `${item.title} ${item.company}`.toLowerCase().includes(normalized),
    );
  }, [keyword, matches]);

  const handleRunMatching = async () => {
    if (!resumeText.trim()) {
      setMessage('请先输入简历文本');
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      const result = await runMatching(resumeText.trim(), targetPosition.trim(), 8);
      setMatches(result.matches || []);
      setHasRun(true);
    } catch (error) {
      setMessage(error.message || '匹配计算失败');
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = score => score >= 80 ? '#16a34a' : score >= 60 ? '#d97706' : '#dc2626';

  return (
    <div className="page">
      <h2>岗位语义匹配</h2>

      <div className="card">
        <div className="form-grid">
          <div className="form-group">
            <label>目标岗位</label>
            <input
              value={targetPosition}
              onChange={event => setTargetPosition(event.target.value)}
              placeholder="如：Python 后端工程师"
            />
          </div>
          <div className="form-group">
            <label>结果筛选</label>
            <input
              value={keyword}
              onChange={event => setKeyword(event.target.value)}
              placeholder="岗位或公司关键词"
            />
          </div>
          <div className="form-group form-group-full">
            <label>简历文本 *</label>
            <textarea
              value={resumeText}
              onChange={event => setResumeText(event.target.value)}
              rows={8}
              placeholder="粘贴教育经历、技能、项目和实习经历"
            />
          </div>
          <div className="form-group form-group-full form-actions">
            <button className="btn btn-primary" onClick={handleRunMatching} disabled={loading}>
              {loading ? '计算中...' : '开始匹配'}
            </button>
          </div>
        </div>
      </div>

      {message && <div className="alert alert-error">{message}</div>}

      {visibleMatches.length > 0 && (
        <>
          <div className="chart-card">
            <h3>匹配分数</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={visibleMatches.map(item => ({ ...item, name: `${item.company} / ${item.title}` }))}
                layout="vertical"
                margin={{ left: 100 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="name" type="category" width={160} tick={{ fontSize: 11 }} />
                <Tooltip formatter={value => `${Number(value).toFixed(1)}分`} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {visibleMatches.map(item => <Cell key={item.job_id} fill={scoreColor(item.score)} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="match-grid">
            {visibleMatches.map(item => (
              <div key={item.job_id} className="match-card">
                <div className="match-header">
                  <div>
                    <h4>{item.title}</h4>
                    <span className="text-muted">{item.company}</span>
                  </div>
                  <div className="match-score" style={{ color: scoreColor(item.score) }}>
                    <span className="score-num">{Number(item.score).toFixed(1)}</span>
                    <span className="score-unit">分</span>
                  </div>
                </div>
                <p>{item.reason}</p>
                <div className="form-actions">
                  {item.source_link && (
                    <a className="btn btn-sm btn-outline" href={item.source_link} target="_blank" rel="noreferrer">
                      岗位来源
                    </a>
                  )}
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => navigate('/interview', {
                      state: {
                        targetJobId: item.job_id,
                        targetPosition: item.title,
                        resumeText,
                        jobInfo: { title: item.title, company: item.company },
                      },
                    })}
                  >
                    针对此岗位面试
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {hasRun && visibleMatches.length === 0 && !loading && (
        <div className="card"><div className="empty">当前索引中没有符合条件的已审核岗位</div></div>
      )}
    </div>
  );
}
