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
};

export default function ResumeReview() {
  const location = useLocation();
  const [resume] = useState(location.state?.resumeData || mockParsed);

  return (
    <div className="page">
      <h2>✅ 简历审核结果</h2>

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
