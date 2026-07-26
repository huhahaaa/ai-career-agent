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

const ROLE_LABELS = {
  backend: '后端/服务端',
  frontend: '前端/客户端',
  machine_learning: 'AI/机器学习',
  data: '数据/算法',
  product: '产品策划',
  operations: '运营增长',
  content: '内容/新媒体',
  system: '系统/运维',
  testing: '测试/质量',
  design: '设计体验',
};

function normalizeList(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === 'string' && value.trim()) return [value.trim()];
  return [];
}

function formatRoleList(value) {
  const roles = normalizeList(value);
  if (!roles.length) return '未识别';
  return roles.map(role => ROLE_LABELS[role] || role).join('、');
}

function formatScore(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : '--';
}

function compatibilityTone(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 'tag-info';
  if (number >= 80) return 'tag-success';
  if (number >= 50) return 'tag-warning';
  return 'tag-error';
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

  const detectedTargetRoles = useMemo(() => {
    const firstWithRoles = matches.find(item => normalizeList(item.ability_breakdown?.target_roles).length);
    return firstWithRoles?.ability_breakdown?.target_roles || [];
  }, [matches]);

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
          <div className="match-insight-card">
            <div>
              <span>目标方向识别</span>
              <strong>{formatRoleList(detectedTargetRoles)}</strong>
            </div>
            <div>
              <span>分数构成</span>
              <strong>语义匹配 60% + 能力覆盖 40%</strong>
            </div>
            <p>若候选岗位方向与目标方向明显不一致，系统会自动降权，所以最终分不是单纯的文本相似度。</p>
          </div>

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
            {visibleMatches.map(item => {
              const ability = item.ability_breakdown || {};
              const compatibility = ability.target_compatibility_score;
              const directionLimited = Number(compatibility) < 80;
              return (
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

                  <div className="score-explain-grid">
                    <div>
                      <span>目标方向</span>
                      <strong>{formatRoleList(ability.target_roles)}</strong>
                    </div>
                    <div>
                      <span>岗位方向</span>
                      <strong>{formatRoleList(ability.job_roles)}</strong>
                    </div>
                    <div>
                      <span>方向一致性</span>
                      <strong><em className={`tag ${compatibilityTone(compatibility)}`}>{formatScore(compatibility)}%</em></strong>
                    </div>
                    <div>
                      <span>语义匹配分</span>
                      <strong>{formatScore(item.semantic_score)}</strong>
                    </div>
                    <div>
                      <span>能力覆盖分</span>
                      <strong>{formatScore(item.skill_coverage_score)}</strong>
                    </div>
                    <div>
                      <span>最终匹配分</span>
                      <strong>{formatScore(item.score)}</strong>
                    </div>
                  </div>

                  {directionLimited && (
                    <div className="match-warning">
                      该岗位与目标方向存在偏差，已参与降权；建议优先参考同方向岗位。
                    </div>
                  )}

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
              );
            })}
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
