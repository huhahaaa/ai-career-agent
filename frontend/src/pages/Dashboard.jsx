import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, LineChart, Line, ResponsiveContainer } from 'recharts';
import { getDashboard } from '../api/client';

const COLORS = ['#6366f1', '#06b6d4', '#f59e0b', '#ef4444', '#22c55e', '#8b5cf6', '#ec4899', '#14b8a6'];

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

  const stats = [
    { label: '简历数', value: data.total_resumes, icon: '📄', color: '#6366f1' },
    { label: '岗位数', value: data.total_jobs, icon: '💼', color: '#06b6d4' },
    { label: '面试次数', value: data.total_interviews, icon: '🎤', color: '#f59e0b' },
    { label: '平均分', value: data.avg_score, icon: '⭐', color: '#22c55e', suffix: '分' },
  ];

  return (
    <div className="page dashboard-page">
      <h2>📊 数据看板</h2>

      {/* 统计卡片 */}
      <div className="stats-grid">
        {stats.map((s, i) => (
          <div key={i} className="stat-card" style={{ borderTopColor: s.color }}>
            <div className="stat-icon">{s.icon}</div>
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
          <h3>📊 个人技能分布</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.skill_distribution} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => `${v}分`} />
              <Bar dataKey="level" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 图表区 2: 岗位技能需求 */}
        <div className="chart-card">
          <h3>🔥 热门技能需求</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.job_skill_requirements}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="skill" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip formatter={(v) => `${v}个岗位`} />
              <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 图表区 3: 能力差距雷达图 */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>🎯 个人能力 vs 岗位要求</h3>
          <ResponsiveContainer width="100%" height={350}>
            <RadarChart data={data.capability_gap}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis domain={[0, 100]} />
              <Radar name="个人水平" dataKey="personal" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
              <Radar name="岗位要求" dataKey="required" stroke="#ef4444" fill="#ef4444" fillOpacity={0.3} />
              <Legend />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* 图表区 4: 多岗位匹配分数 */}
        <div className="chart-card">
          <h3>🏆 多岗位匹配得分</h3>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={data.multi_job_scores} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis dataKey="job" type="category" width={130} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => `${v}分`} />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {data.multi_job_scores.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color || COLORS[idx % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 图表区 5: 面试趋势 + 图表区 6: 城市分布 */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>📈 面试得分趋势</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.interview_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis domain={[0, 100]} />
              <Tooltip formatter={(v) => `${v}分`} />
              <Legend />
              <Line type="monotone" dataKey="score" name="面试得分" stroke="#6366f1" strokeWidth={3} dot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>🏙️ 岗位城市分布</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data.job_city_distribution}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="value"
                nameKey="name"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {data.job_city_distribution.map((_, idx) => (
                  <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v, n) => [`${v}个岗位`, n]} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 最近面试记录 */}
      <div className="card">
        <h3>📋 最近面试记录</h3>
        {data.recent_interviews.length === 0 ? (
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
              {data.recent_interviews.map(item => (
                <tr key={item.id}>
                  <td>{item.company}</td>
                  <td>{item.job_title}</td>
                  <td><span className="tag">{item.mode}</span></td>
                  <td><strong>{item.score}</strong></td>
                  <td>{item.duration_minutes}分钟</td>
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
