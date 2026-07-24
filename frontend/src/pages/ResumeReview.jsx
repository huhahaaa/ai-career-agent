import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

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
  // 风险检测结果
  risk_analysis: {
    overall_risk: 'low',
    items: [
      { type: 'warning', title: '量化成果不足', description: '项目描述中缺少具体的量化指标（如"提升性能30%"、"用户增长50%"等），建议用数据说明成果', severity: 'medium' },
      { type: 'warning', title: '技能细节缺失', description: 'Docker、Webpack 等技能只列了名称，缺少使用场景和深度说明', severity: 'low' },
      { type: 'warning', title: '实习经历描述过简', description: '某科技公司的实习经历只有一句话描述，建议展开说明具体负责模块和技术挑战', severity: 'medium' },
      { type: 'info', title: '缺少个人作品链接', description: '建议附上 GitHub / 技术博客 / 作品集链接，增加可信度', severity: 'low' },
      { type: 'tip', title: '教育经历可优化', description: '可补充 GPA 排名（如果在前30%）、相关课程或获奖经历', severity: 'info' },
    ],
  },
  // 关键词提取
  keyword_analysis: {
    strong_keywords: ['React', 'TypeScript', 'Redux', '前端开发', '核心产品'],
    weak_keywords: ['使用', '参与', '负责'], // 过于宽泛的词汇
    suggested_keywords: ['性能优化', '团队协作', '敏捷开发', 'CI/CD', '单元测试'],
  },
};

export default function ResumeReview() {
  const location = useLocation();
  const [resume] = useState(location.state?.resumeData || mockParsed);
  const [showRiskDetail, setShowRiskDetail] = useState(true);

  const riskAnalysis = resume.risk_analysis || mockParsed.risk_analysis;
  const keywordAnalysis = resume.keyword_analysis || mockParsed.keyword_analysis;

  const getRiskColor = (severity) => {
    switch (severity) {
      case 'high': return '#ef4444';
      case 'medium': return '#f59e0b';
      case 'low': return '#06b6d4';
      default: return '#8b5cf6';
    }
  };

  const getRiskLabel = (severity) => {
    switch (severity) {
      case 'high': return '高';
      case 'medium': return '中';
      case 'low': return '低';
      default: return '提示';
    }
  };

  return (
    <div className="page">
      <h2>✅ 简历审核结果</h2>

      {/* 风险检测概览卡片 */}
      <div className={`risk-overview-card ${riskAnalysis.overall_risk === 'low' ? 'risk-low' : riskAnalysis.overall_risk === 'medium' ? 'risk-medium' : 'risk-high'}`}>
        <div className="risk-header">
          <div className="risk-icon">
            {riskAnalysis.overall_risk === 'low' ? '✅' : riskAnalysis.overall_risk === 'medium' ? '⚠️' : '🚨'}
          </div>
          <div className="risk-summary">
            <h4>简历风险检测</h4>
            <p>
              综合风险等级：
              <span className={`risk-badge risk-badge-${riskAnalysis.overall_risk}`}>
                {riskAnalysis.overall_risk === 'low' ? '低风险' : riskAnalysis.overall_risk === 'medium' ? '中风险' : '高风险'}
              </span>
              {riskAnalysis.items.filter(i => i.type === 'warning').length > 0 && (
                <span className="text-muted"> — 发现 {riskAnalysis.items.filter(i => i.type === 'warning').length} 个优化建议</span>
              )}
            </p>
          </div>
          <button className="btn btn-sm btn-outline" onClick={() => setShowRiskDetail(!showRiskDetail)}>
            {showRiskDetail ? '收起' : '展开'}
          </button>
        </div>

        {showRiskDetail && (
          <div className="risk-items-list">
            {riskAnalysis.items.map((item, i) => (
              <div key={i} className={`risk-item risk-item-${item.severity}`}>
                <div className="risk-item-icon">
                  {item.type === 'warning' ? '⚠️' : item.type === 'info' ? 'ℹ️' : '💡'}
                </div>
                <div className="risk-item-content">
                  <div className="risk-item-header">
                    <strong>{item.title}</strong>
                    <span className="risk-severity-tag" style={{ background: getRiskColor(item.severity) }}>
                      {getRiskLabel(item.severity)}风险
                    </span>
                  </div>
                  <p>{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="resume-header">
          <div className="resume-avatar">👤</div>
          <div className="resume-basic">
            <h3>{resume.name}</h3>
            <p>📧 {resume.email} | 📞 {resume.phone}</p>
          </div>
          <div className="review-badge">
            <span className="tag tag-success">审核通过</span>
            <div className="review-score">综合评分: {resume.review_score}分</div>
          </div>
        </div>
        <div className="review-comment-box">
          <h4>📝 审核意见</h4>
          <p>{resume.review_comment}</p>
        </div>
      </div>

      <div className="charts-row">
        {/* 技能评估图表 */}
        <div className="chart-card">
          <h3>📊 技能评估分布</h3>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={resume.skills} layout="vertical" margin={{ left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 12 }} />
              <Tooltip formatter={v => `${v}分`} />
              <Bar dataKey="level" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 教育经历 */}
        <div className="card" style={{ flex: 1 }}>
          <h3>🎓 教育经历</h3>
          {resume.education.map((ed, i) => (
            <div key={i} className="info-block">
              <div className="info-title">{ed.school} - {ed.degree}</div>
              <div className="info-sub">{ed.major} | {ed.start} - {ed.end}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 关键词分析 */}
      {keywordAnalysis && (
        <div className="keyword-analysis-card">
          <h3>🔑 关键词分析</h3>
          <div className="keyword-sections">
            <div className="keyword-section">
              <h5>✅ 优势关键词</h5>
              <div className="tag-group">
                {keywordAnalysis.strong_keywords.map(k => <span key={k} className="tag tag-success">{k}</span>)}
              </div>
            </div>
            <div className="keyword-section">
              <h5>⚠️ 弱关键词（过于宽泛）</h5>
              <div className="tag-group">
                {keywordAnalysis.weak_keywords.map(k => <span key={k} className="tag tag-warning">{k}</span>)}
              </div>
              <p className="text-muted" style={{ fontSize: '12px', marginTop: '6px' }}>
                这些词汇过于通用，建议替换为更具体的技术术语或行业关键词
              </p>
            </div>
            <div className="keyword-section">
              <h5>💡 建议添加的关键词</h5>
              <div className="tag-group">
                {keywordAnalysis.suggested_keywords.map(k => <span key={k} className="tag">{k}</span>)}
              </div>
              <p className="text-muted" style={{ fontSize: '12px', marginTop: '6px' }}>
                这些是目标岗位常见要求但简历中缺失的关键词，建议适当补充
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 工作经历 */}
      <div className="card">
        <h3>💼 工作经历</h3>
        {resume.experience.map((exp, i) => (
          <div key={i} className="info-block">
            <div className="info-title">{exp.company} | {exp.position}</div>
            <div className="info-sub">{exp.start} - {exp.end}</div>
            <p className="info-desc">{exp.description}</p>
          </div>
        ))}
      </div>

      {/* 项目经历 */}
      <div className="card">
        <h3>🚀 项目经历</h3>
        {resume.projects.map((proj, i) => (
          <div key={i} className="info-block">
            <div className="info-title">{proj.name} | {proj.role}</div>
            <p className="info-desc">{proj.description}</p>
            <div className="tag-group">
              {proj.tech_stack.map(t => <span key={t} className="tag">{t}</span>)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
