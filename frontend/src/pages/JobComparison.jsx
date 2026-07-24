import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';

const COLORS = ['#6366f1', '#06b6d4', '#f59e0b', '#ef4444', '#22c55e', '#8b5cf6'];

// Mock 多岗位对比数据
const mockCompareData = [
  { id: 'j1', title: '前端开发工程师', company: '字节跳动', city: '北京', salary_min: 25000, salary_max: 45000, experience: '1-3年', education: '本科', skills_required: ['React', 'TypeScript', 'CSS3', 'HTML5', 'Webpack', 'Node.js', '性能优化', '工程化'], match_score: 82, match_detail: { skill: 78, experience: 85, education: 90 } },
  { id: 'j2', title: '前端开发工程师', company: '腾讯', city: '深圳', salary_min: 20000, salary_max: 40000, experience: '1-3年', education: '本科', skills_required: ['Vue', 'JavaScript', 'CSS3', 'HTML5', 'Node.js', '小程序开发', '跨端开发'], match_score: 70, match_detail: { skill: 65, experience: 75, education: 90 } },
  { id: 'j3', title: '全栈开发工程师', company: '阿里巴巴', city: '杭州', salary_min: 28000, salary_max: 50000, experience: '3-5年', education: '本科', skills_required: ['React', 'Node.js', 'Python', 'MySQL', 'Docker', 'Kubernetes', 'Redis', '微服务'], match_score: 68, match_detail: { skill: 60, experience: 70, education: 90 } },
  { id: 'j4', title: '前端架构师', company: '美团', city: '北京', salary_min: 35000, salary_max: 60000, experience: '5-10年', education: '本科', skills_required: ['React', 'Vue', 'TypeScript', 'Node.js', '微前端', '性能优化', '工程化', '团队管理'], match_score: 55, match_detail: { skill: 50, experience: 45, education: 90 } },
  { id: 'j6', title: '前端开发实习生', company: '滴滴', city: '北京', salary_min: 8000, salary_max: 12000, experience: '应届', education: '本科', skills_required: ['React', 'JavaScript', 'CSS3', 'HTML5', 'Git'], match_score: 95, match_detail: { skill: 98, experience: 90, education: 90 } },
];

const userSkills = ['React', 'Vue', 'TypeScript', 'Node.js', 'Python', 'CSS3', 'HTML5', 'Git', 'Webpack', 'Docker'];

export default function JobComparison() {
  const location = useLocation();
  const [compareData] = useState(location.state?.matches ? location.state.matches.map((m, i) => ({
    ...mockCompareData.find(d => d.id === m.job_id),
    match_score: m.overall_score,
  })).filter(Boolean) : mockCompareData);
  const [selected, setSelected] = useState(compareData.map((_, i) => i < 3));

  const toggleJob = (idx) => {
    const next = [...selected];
    next[idx] = !next[idx];
    setSelected(next);
  };

  const selectedJobs = compareData.filter((_, i) => selected[i]);
  const allSkills = [...new Set(selectedJobs.flatMap(j => j.skills_required))];

  const radarData = allSkills.map(skill => {
    const entry = { subject: skill };
    selectedJobs.forEach(j => {
      entry[j.company] = j.skills_required.includes(skill) ? 90 : 10;
    });
    return entry;
  });

  const barData = selectedJobs.map(j => ({
    name: `${j.company.slice(0, 4)}(${j.title.slice(0, 4)})`,
    salary_min: j.salary_min / 1000,
    salary_max: j.salary_max / 1000,
    match: j.match_score,
  }));

  return (
    <div className="page">
      <h2>📈 多岗位横向对比</h2>

      <div className="card">
        <h3>选择对比岗位</h3>
        <div className="tag-group">
          {compareData.map((j, i) => (
            <button
              key={j.id}
              className={`tag ${selected[i] ? 'tag-primary' : ''}`}
              onClick={() => toggleJob(i)}
              style={{ cursor: 'pointer' }}
            >
              {selected[i] ? '✅' : '⬜'} {j.company} - {j.title}
            </button>
          ))}
        </div>
      </div>

      {selectedJobs.length > 0 && (
        <>
          {/* 基础信息对比 */}
          <div className="card">
            <h3>📋 基本信息对比</h3>
            <div className="compare-table-wrapper">
              <table className="table compare-table">
                <thead>
                  <tr>
                    <th>维度</th>
                    {selectedJobs.map(j => <th key={j.id} style={{ color: COLORS[compareData.indexOf(j) % COLORS.length] }}>{j.company}<br/>{j.title}</th>)}
                  </tr>
                </thead>
                <tbody>
                  <tr><td>城市</td>{selectedJobs.map(j => <td key={j.id}>{j.city}</td>)}</tr>
                  <tr><td>薪资</td>{selectedJobs.map(j => <td key={j.id}>{j.salary_min / 1000}k - {j.salary_max / 1000}k</td>)}</tr>
                  <tr><td>经验要求</td>{selectedJobs.map(j => <td key={j.id}>{j.experience}</td>)}</tr>
                  <tr><td>学历要求</td>{selectedJobs.map(j => <td key={j.id}>{j.education}</td>)}</tr>
                  <tr><td>匹配度</td>{selectedJobs.map(j => <td key={j.id}><strong style={{ color: j.match_score >= 80 ? '#22c55e' : j.match_score >= 60 ? '#f59e0b' : '#ef4444' }}>{j.match_score}分</strong></td>)}</tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* 薪资与匹配度柱状图 */}
          <div className="charts-row">
            <div className="chart-card">
              <h3>💰 薪资范围对比 (K)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="salary_min" name="最低薪资" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="salary_max" name="最高薪资" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-card">
              <h3>🎯 匹配度对比</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} />
                  <Tooltip formatter={v => `${v}分`} />
                  <Bar dataKey="match" name="匹配分数" radius={[4, 4, 0, 0]}>
                    {barData.map((_, idx) => <rect key={idx} fill={COLORS[idx % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 技能要求雷达图 */}
          <div className="chart-card">
            <h3>🔄 技能要求对比雷达</h3>
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                <PolarRadiusAxis domain={[0, 100]} />
                {selectedJobs.map((j, i) => (
                  <Radar key={j.id} name={j.company} dataKey={j.company} stroke={COLORS[i % COLORS.length]} fill={COLORS[i % COLORS.length]} fillOpacity={0.1} />
                ))}
                <Legend />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* 详细技能对比 */}
          <div className="card">
            <h3>🔍 技能要求详细对比</h3>
            <div className="compare-table-wrapper">
              <table className="table compare-table">
                <thead>
                  <tr>
                    <th>技能</th>
                    {selectedJobs.map(j => <th key={j.id}>{j.company}</th>)}
                    <th>是否掌握</th>
                  </tr>
                </thead>
                <tbody>
                  {allSkills.map(skill => (
                    <tr key={skill}>
                      <td><strong>{skill}</strong></td>
                      {selectedJobs.map(j => (
                        <td key={j.id}>{j.skills_required.includes(skill) ? '✅' : '—'}</td>
                      ))}
                      <td>{userSkills.includes(skill) ? '✅ 已掌握' : '❌ 待学习'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
