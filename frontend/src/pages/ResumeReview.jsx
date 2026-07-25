import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { auditResume, getResumeDetail } from '../api/client';

const POSITIONS = ["前端", "后端", "产品", "运营", "算法", "数媒"];

const DIMENSION_CN = {
  completeness: '内容完整度',
  position_match: '岗位匹配度',
  quantification: '量化程度',
  clarity: '表达清晰度',
  project_quality: '项目完整度',
};

const FIELD_CN = {
  email: '邮箱',
  phone: '手机号',
  education: '教育背景',
  experience: '工作经历',
  projects: '项目经历',
  skills: '技能清单',
  portfolio: '作品集/主页',
};

const RISK_TAG = { 低: 'tag-success', 中: 'tag-warning', 高: 'tag-error' };

const mockParsed = {
  name: '张三',
  email: 'zhangsan@example.com',
  phone: '13800001111',
  education: [
    { school: '清华大学', degree: '本科', major: '计算机科学', start: '2020', end: '2024' },
  ],
  skills: [
    { name: 'React', level: 90 },
    { name: 'Vue', level: 75 },
    { name: 'TypeScript', level: 80 },
    { name: 'Node.js', level: 70 },
    { name: 'Python', level: 65 },
    { name: 'CSS3', level: 85 },
    { name: 'HTML5', level: 90 },
    { name: 'Git', level: 80 },
    { name: 'Webpack', level: 70 },
    { name: 'Docker', level: 55 },
  ],
  experience: [
    { company: '某科技公司', position: '前端开发实习生', start: '2023-06', end: '2024-06', description: '参与公司核心产品前端开发，使用React+TypeScript技术栈' },
  ],
  projects: [
    { name: '电商平台', role: '前端负责人', description: '使用React+Redux搭建大型电商平台前端', tech_stack: ['React', 'Redux', 'TypeScript'] },
  ],
  review_comment: '技能描述清晰，项目经验丰富，推荐通过',
  review_score: 85,
};

export default function ResumeReview() {
  const location = useLocation();
  const resumeId = location.state?.resumeId || null;
  const [resumeText, setResumeText] = useState('');
  const [targetPosition, setTargetPosition] = useState(POSITIONS[0]);
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [parsed] = useState(location.state?.resumeData || mockParsed);

  useEffect(() => {
    let active = true;
    if (resumeId) {
      getResumeDetail(resumeId)
        .then(detail => {
          if (active && detail && typeof detail.content === 'string' && !detail.content.startsWith('已上传')) {
            setResumeText(detail.content);
          }
        })
        .catch(() => {});
    }
    return () => { active = false; };
  }, [resumeId]);

  const dimensionData = useMemo(() => {
    if (!audit?.dimension_scores) return [];
    return Object.entries(audit.dimension_scores).map(([key, value]) => ({
      name: DIMENSION_CN[key] || key,
      得分: Number(value),
    }));
  }, [audit]);

  const handleAudit = async () => {
    if (!resumeText.trim()) {
      setError('请粘贴或输入简历文本后再运行审核');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await auditResume({
        resumeText: resumeText.trim(),
        targetPosition: targetPosition.trim(),
        resumeId,
      });
      setAudit(result);
    } catch (requestError) {
      setError(requestError.message || '简历审核失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <h2>✅ 简历审核 Agent</h2>

      <div className="card">
        <div className="form-grid">
          <div className="form-group">
            <label>目标岗位（用于岗位化审核）</label>
            <select value={targetPosition} onChange={event => setTargetPosition(event.target.value)}>
              {POSITIONS.map(pos => (
                <option key={pos} value={pos}>{pos}</option>
              ))}
            </select>
          </div>
          <div className="form-group form-group-full">
            <label>简历文本 *</label>
            <textarea
              value={resumeText}
              onChange={event => setResumeText(event.target.value)}
              rows={8}
              placeholder="粘贴简历文本，或上传后自动带入内容"
            />
          </div>
          <div className="form-group form-group-full form-actions">
            <button className="btn btn-primary" onClick={handleAudit} disabled={loading}>
              {loading ? '审核中...' : '运行简历审核 Agent'}
            </button>
            {audit && (
              <button className="btn" onClick={() => setAudit(null)}>收起报告</button>
            )}
          </div>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
      </div>

      {audit ? (
        <div className="audit-report">
          <div className="card audit-summary">
            <div className="resume-header">
              <div className="review-badge">
                <span className={`tag ${RISK_TAG[audit.risk_level] || 'tag-warning'}`}>风险等级：{audit.risk_level}</span>
                <div className="review-score">综合评分：{audit.score} 分</div>
              </div>
              <div className="audit-meta">
                <span className="tag">岗位：{audit.position_bucket || '综合'}</span>
                {typeof audit.rule_score === 'number' && <span className="tag">规则基线：{audit.rule_score}</span>}
                {typeof audit.llm_score === 'number' && <span className="tag">Agent 评分：{audit.llm_score}</span>}
              </div>
            </div>
          </div>

          <div className="charts-row">
            <div className="chart-card">
              <h3>📊 五维评分</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={dimensionData} layout="vertical" margin={{ left: 70 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 25]} />
                  <YAxis dataKey="name" type="category" width={90} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={v => `${v} 分`} />
                  <Bar dataKey="得分" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card audit-fields">
              <h3>📋 字段检测</h3>
              {Object.entries(audit.detected_fields || {}).map(([field, ok]) => (
                <div key={field} className={`field-row ${ok ? 'field-ok' : 'field-missing'}`}>
                  <span>{FIELD_CN[field] || field}</span>
                  <span>{ok ? '✓ 已包含' : '✗ 缺失'}</span>
                </div>
              ))}
            </div>
          </div>

          {audit.risk_flags?.length > 0 && (
            <div className="card">
              <h3>⚠ 风险标记</h3>
              <ul className="risk-list">
                {audit.risk_flags.map((flag, i) => <li key={i}>{flag}</li>)}
              </ul>
            </div>
          )}

          {audit.missing_keywords?.length > 0 && (
            <div className="card">
              <h3>🔑 建议补充关键词</h3>
              <div className="tag-group">
                {audit.missing_keywords.map(k => <span key={k} className="tag tag-warning">{k}</span>)}
              </div>
            </div>
          )}

          {audit.suggestions?.length > 0 && (
            <div className="card">
              <h3>💡 改进建议</h3>
              <ul className="suggestion-list">
                {audit.suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="resume-header">
            <div className="resume-avatar">👤</div>
            <div className="resume-basic">
              <h3>{parsed.name}</h3>
              <p>📧 {parsed.email} | 📞 {parsed.phone}</p>
            </div>
            <div className="review-badge">
              <span className="tag tag-success">参考样例</span>
              <div className="review-score">综合评分：{parsed.review_score}分</div>
            </div>
          </div>
          <div className="review-comment-box">
            <h4>📝 审核意见</h4>
            <p>{parsed.review_comment}</p>
          </div>
          <p className="text-muted">在上方粘贴你的简历并选择岗位，点击「运行简历审核 Agent」生成结构化评估报告。</p>
        </div>
      )}
    </div>
  );
}
