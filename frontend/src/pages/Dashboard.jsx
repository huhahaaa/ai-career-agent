import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, LineChart, Line, ResponsiveContainer } from 'recharts';
import { Briefcase, FileText, Mic, Star } from 'lucide-react';
import { getDashboard } from '../api/client';

const COLORS = [
  'var(--chart-primary)',
  'var(--chart-secondary)',
  'var(--chart-warning)',
  'var(--chart-danger)',
  'var(--chart-success)',
  'var(--chart-violet)',
  'var(--chart-rose)',
  'var(--chart-cyan)',
];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">加载中...</div>;
  if (error) {
    const type = error.code === 50100 ? 'info' : 'error';
    return <div className={`alert alert-${type}`}>{error.message || '数据看板加载失败'}</div>;
  }
  if (!data) return <div className="empty">暂无数据</div>;

  const skillDistribution = data.skill_distribution || [];
  const jobSkillRequirements = data.job_skill_requirements || [];
  const capabilityGap = data.capability_gap || [];
  const multiJobScores = data.multi_job_scores || [];
  const interviewTrend = data.interview_trend || [];
  const jobCityDistribution = data.job_city_distribution || [];
  const recentInterviews = data.recent_interviews || [];
  const activeResume = data.active_resume || null;

  const stats = [
    { label: '简历数', value: data.total_resumes, icon: FileText, color: 'var(--chart-primary)' },
    { label: '岗位数', value: data.total_jobs, icon: Briefcase, color: 'var(--chart-secondary)' },
    { label: '面试次数', value: data.total_interviews, icon: Mic, color: 'var(--chart-warning)' },
    { label: '平均分', value: data.avg_score ?? '--', icon: Star, color: 'var(--chart-success)', suffix: data.avg_score == null ? '' : '分' },
  ];

  return (
    <div className="page dashboard-page">
      <div className="page-title-row">
        <h2>数据看板</h2>
        <div className="dashboard-source">
          <span>技能画像来源</span>
          <strong>{activeResume ? `${activeResume.filename}（v${activeResume.version}）` : '暂无默认简历'}</strong>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="stats-grid">
        {stats.map((s, i) => (
          <div key={i} className="stat-card" style={{ borderTopColor: s.color }}>
            <div className="stat-icon" style={{ color: s.color }}>
              <s.icon size={22} />
            </div>
            <div className="stat-info">
              <div className="stat-value">{s.value}{s.suffix || ''}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* 图表区 1: 技能分布 */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>个人技能分布</h3>
          {skillDistribution.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={skillDistribution} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => `${v}分`} />
                <Bar dataKey="level" fill="var(--chart-primary)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">暂无可统计的个人技能，请先上传并审核简历。</div>
          )}
        </div>

        {/* 图表区 2: 岗位技能需求 */}
        <div className="chart-card">
          <h3>热门技能需求</h3>
          {jobSkillRequirements.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={jobSkillRequirements}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="skill" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip formatter={(v) => `${v}个岗位`} />
                <Bar dataKey="count" fill="var(--chart-secondary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">暂无岗位技能统计，请先导入并审核岗位。</div>
          )}
        </div>
      </div>

      {/* 图表区 3: 能力差距雷达图 */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>个人能力 vs 岗位要求</h3>
          {capabilityGap.length ? (
            <ResponsiveContainer width="100%" height={350}>
              <RadarChart data={capabilityGap}>
                <PolarGrid />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis domain={[0, 100]} />
                <Radar name="个人水平" dataKey="personal" stroke="var(--chart-primary)" fill="var(--chart-primary)" fillOpacity={0.3} />
                <Radar name="岗位要求" dataKey="required" stroke="var(--chart-danger)" fill="var(--chart-danger)" fillOpacity={0.25} />
                <Legend />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">暂无能力差距数据，请先上传简历并准备岗位技能数据。</div>
          )}
        </div>

        {/* 图表区 4: 多岗位匹配分数 */}
        <div className="chart-card">
          <h3>多岗位匹配得分</h3>
          {multiJobScores.length ? (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={multiJobScores} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="job" type="category" width={130} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => `${v}分`} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {multiJobScores.map((entry, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">暂无岗位匹配得分，请先运行一次岗位匹配。</div>
          )}
        </div>
      </div>

      {/* 图表区 5: 面试趋势 + 图表区 6: 城市分布 */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>面试得分趋势</h3>
          {interviewTrend.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={interviewTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={(v) => `${v}分`} />
                <Legend />
                <Line type="monotone" dataKey="score" name="面试得分" stroke="var(--chart-primary)" strokeWidth={3} dot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">暂无面试得分趋势，请先完成一次模拟面试。</div>
          )}
        </div>

        <div className="chart-card">
          <h3>岗位城市分布</h3>
          {jobCityDistribution.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={jobCityDistribution}
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  dataKey="value"
                  nameKey="name"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {jobCityDistribution.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [`${v}个岗位`, n]} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">暂无岗位城市数据，请先导入岗位。</div>
          )}
        </div>
      </div>

      {/* 最近面试记录 */}
      <div className="card">
        <h3>最近面试记录</h3>
        {recentInterviews.length === 0 ? (
          <div className="empty">暂无面试记录</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>公司</th>
                <th>岗位</th>
                <th>模式</th>
                <th>得分</th>
                <th>时长</th>
                <th>状态</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {recentInterviews.map(item => (
                <tr key={item.id}>
                  <td>{item.company}</td>
                  <td>{item.job_title}</td>
                  <td><span className="tag">{item.mode}</span></td>
                  <td><strong>{item.score == null ? '--' : item.score}</strong></td>
                  <td>{item.duration_minutes == null ? '--' : `${item.duration_minutes}分钟`}</td>
                  <td><span className={`tag tag-${item.status}`}>{item.status === 'completed' ? '已完成' : '进行中'}</span></td>
                  <td>{new Date(item.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
