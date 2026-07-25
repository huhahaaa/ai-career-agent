import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getResumeDetail, getResumes, runMatching } from '../api/client';

function buildMatchSearchText(item) {
  const values = [
    item.title,
    item.company,
    item.reason,
    item.source_link,
    item.gap_analysis,
    item.suggestion,
    ...(item.skills || []),
    ...(item.matched_skills || []),
    ...(item.missing_skills || []),
  ];
  return values.filter(Boolean).join(' ').toLowerCase();
}

export default function JobSearchMatch() {
  const [resumeText, setResumeText] = useState('');
  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [resumeLoading, setResumeLoading] = useState(false);
  const [targetPosition, setTargetPosition] = useState('');
  const [keyword, setKeyword] = useState('');
  const [matches, setMatches] = useState([]);
  const [hasRun, setHasRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    getResumes()
      .then(data => {
        const list = data || [];
        setResumes(list);
        const defaultResume = list.find(item => item.is_default) || list[0];
        if (defaultResume && !resumeText.trim()) {
          setSelectedResumeId(String(defaultResume.id));
        }
      })
      .catch(() => {
        setResumes([]);
      });
  }, []);

  useEffect(() => {
    if (!selectedResumeId) return;
    setResumeLoading(true);
    setMessage('');
    getResumeDetail(selectedResumeId)
      .then(detail => {
        const versions = detail?.versions || [];
        const version = versions[versions.length - 1];
        setResumeText(version?.content || '');
      })
      .catch(error => setMessage(error.message || '简历正文加载失败'))
      .finally(() => setResumeLoading(false));
  }, [selectedResumeId]);

  const visibleMatches = useMemo(() => {
    const normalized = keyword.trim().toLowerCase();
    if (!normalized) return matches;
    return matches.filter(item => buildMatchSearchText(item).includes(normalized));
  }, [keyword, matches]);

  const handleRunMatching = async () => {
    if (!resumeText.trim()) {
      setMessage('请先输入简历文本');
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      const result = await runMatching(
        resumeText.trim(),
        targetPosition.trim(),
        8,
        selectedResumeId || null,
      );
      setMatches(result.matches || []);
      setHasRun(true);
    } catch (error) {
      setMessage(error.message || '匹配计算失败');
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = score => score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--error)';

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
            <label>使用已有简历</label>
            <select
              value={selectedResumeId}
              onChange={event => setSelectedResumeId(event.target.value)}
            >
              <option value="">手动粘贴简历文本</option>
              {resumes.map(item => (
                <option key={item.id} value={item.id}>
                  {item.is_default ? '默认 - ' : ''}{item.filename}（v{item.version}）
                </option>
              ))}
            </select>
          </div>
          <div className="form-group form-group-full">
            <label>简历文本 *</label>
            <textarea
              value={resumeText}
              onChange={event => {
                setResumeText(event.target.value);
                if (selectedResumeId) setSelectedResumeId('');
              }}
              rows={8}
              placeholder={resumeLoading ? '正在加载简历正文...' : '粘贴教育经历、技能、项目和实习经历'}
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
                {(item.matched_skills?.length > 0 || item.missing_skills?.length > 0) && (
                  <div className="feedback-section">
                    {item.matched_skills?.length > 0 && (
                      <>
                        <h4>命中技能</h4>
                        <div className="tag-group">
                          {item.matched_skills.map(skill => (
                            <span key={skill} className="tag tag-success">{skill}</span>
                          ))}
                        </div>
                      </>
                    )}
                    {item.missing_skills?.length > 0 && (
                      <>
                        <h4>缺失技能</h4>
                        <div className="tag-group">
                          {item.missing_skills.map(skill => (
                            <span key={skill} className="tag tag-warning">{skill}</span>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
                {(item.gap_analysis || item.suggestion) && (
                  <div className="info-block">
                    {item.gap_analysis && <div className="info-title">{item.gap_analysis}</div>}
                    {item.suggestion && <p className="info-desc">{item.suggestion}</p>}
                  </div>
                )}
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
                        resumeId: selectedResumeId || null,
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
        <div className="card">
          <div className="empty">
            {matches.length
              ? '当前匹配结果中没有符合筛选关键词的岗位，可清空结果筛选查看全部结果。'
              : '当前索引中没有可匹配的已审核岗位，请先审核岗位并更新索引。'}
          </div>
        </div>
      )}
    </div>
  );
}
