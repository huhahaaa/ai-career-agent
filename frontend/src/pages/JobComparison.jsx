import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} from 'recharts';
import { getJobs, getMatches } from '../api/client';

const COLORS = ['#2563eb', '#06b6d4', '#f59e0b', '#ef4444', '#22c55e', '#8b5cf6'];

function parseSalaryRange(value) {
  const raw = String(value || '').trim();
  if (!raw) return { min: 0, max: 0, label: '未填写' };

  const numbers = Array.from(raw.matchAll(/\d+(?:\.\d+)?/g)).map(match => Number(match[0]));
  if (!numbers.length) return { min: 0, max: 0, label: raw };

  const normalized = numbers.map(item => (item > 1000 ? item / 1000 : item));
  const min = Math.min(...normalized);
  const max = Math.max(...normalized);
  return { min, max, label: raw };
}

function formatScore(score) {
  return typeof score === 'number' ? `${Math.round(score)} 分` : '待匹配';
}

function scoreColor(score) {
  if (typeof score !== 'number') return '#64748b';
  return score >= 80 ? '#16a34a' : score >= 60 ? '#d97706' : '#dc2626';
}

function normalizeJob(job, index, match = null) {
  const salary = parseSalaryRange(job.salary_range);
  const score = typeof match?.total_score === 'number'
    ? match.total_score
    : typeof match?.score === 'number'
      ? match.score
      : null;

  return {
    id: job.id ?? match?.job_id ?? `job-${index}`,
    seriesKey: `job_${job.id ?? match?.job_id ?? index}`,
    title: job.title || match?.job_title || '未命名岗位',
    company: job.company || match?.company || '未知公司',
    city: job.location || job.city || '未填写',
    salary_min: salary.min,
    salary_max: salary.max,
    salary_label: salary.label,
    experience: job.experience || '未填写',
    education: job.education || '未填写',
    skills_required: job.skills || job.skills_required || [],
    source_link: job.source_link || match?.details?.source_link || '',
    match_score: score,
    reason: match?.details?.reason || match?.reason || '',
    created_at: match?.created_at || '',
    from_history: Boolean(match),
  };
}

function normalizeHistoryRecord(record, jobs, index) {
  const job = jobs.find(item => String(item.id) === String(record.job_id)) || {};
  return normalizeJob(
    {
      ...job,
      id: record.job_id,
      title: job.title || record.job_title,
      company: job.company || record.company,
    },
    index,
    record,
  );
}

function normalizeImmediateMatch(match, index) {
  return normalizeJob(
    {
      id: match.job_id,
      title: match.title,
      company: match.company,
      source_link: match.source_link,
      skills: match.skills || [],
    },
    index,
    { ...match, total_score: Math.round(match.score || 0), details: { reason: match.reason, source_link: match.source_link } },
  );
}

export default function JobComparison() {
  const location = useLocation();
  const navigate = useNavigate();
  const [compareData, setCompareData] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [dataSource, setDataSource] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setMessage('');
      try {
        const approvedJobs = await getJobs({ status: 'approved' });
        const routeMatches = location.state?.matches || [];

        if (routeMatches.length) {
          const rows = routeMatches.map(normalizeImmediateMatch);
          setCompareData(rows);
          setDataSource('当前匹配结果');
          setSelected(rows.map((_, index) => index < 3));
          return;
        }

        const history = await getMatches();
        if (history?.length) {
          const rows = history.slice(0, 8).map((record, index) => normalizeHistoryRecord(record, approvedJobs || [], index));
          setCompareData(rows);
          setDataSource('真实匹配历史');
          setSelected(rows.map((_, index) => index < 3));
          return;
        }

        const rows = (approvedJobs || []).slice(0, 8).map((job, index) => normalizeJob(job, index));
        setCompareData(rows);
        setDataSource('已审核岗位');
        setSelected(rows.map((_, index) => index < 3));
        if (!rows.length) {
          setMessage('暂无可对比岗位。请先完成岗位导入、审核和索引。');
        } else {
          setMessage('还没有真实匹配历史，当前展示已审核岗位基础对比；跑一次岗位匹配后会显示真实匹配分数。');
        }
      } catch (error) {
        setMessage(error.message || '多岗对比数据加载失败');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [location.state]);

  const toggleJob = idx => {
    const next = [...selected];
    next[idx] = !next[idx];
    setSelected(next);
  };

  const selectedJobs = compareData.filter((_, index) => selected[index]);
  const allSkills = useMemo(
    () => [...new Set(selectedJobs.flatMap(job => job.skills_required || []))],
    [selectedJobs],
  );

  const radarData = allSkills.map(skill => {
    const entry = { subject: skill };
    selectedJobs.forEach(job => {
      entry[job.seriesKey] = job.skills_required.includes(skill) ? 90 : 10;
    });
    return entry;
  });

  const barData = selectedJobs.map(job => ({
    name: `${job.company.slice(0, 4)}(${job.title.slice(0, 4)})`,
    salary_min: job.salary_min,
    salary_max: job.salary_max,
    match: typeof job.match_score === 'number' ? job.match_score : 0,
    hasScore: typeof job.match_score === 'number',
  }));

  const hasSalaryData = barData.some(item => item.salary_min > 0 || item.salary_max > 0);
  const hasScoreData = selectedJobs.some(job => typeof job.match_score === 'number');

  if (loading) return <div className="loading">加载真实岗位对比数据...</div>;

  return (
    <div className="page">
      <h2>多岗位横向对比</h2>

      {message && <div className={`alert ${message.includes('失败') || message.includes('暂无') ? 'alert-error' : 'alert-info'}`}>{message}</div>}

      <div className="card">
        <div className="card-header-row">
          <div>
            <h3>选择对比岗位</h3>
            <span className="text-muted">数据来源：{dataSource || '真实接口'}</span>
          </div>
          <button className="btn btn-sm btn-outline" onClick={() => navigate('/jobs/match')}>去岗位匹配</button>
        </div>

        {compareData.length === 0 ? (
          <div className="empty">没有可展示的真实岗位数据</div>
        ) : (
          <div className="tag-group">
            {compareData.map((job, index) => (
              <button
                key={`${job.id}-${index}`}
                className={`tag ${selected[index] ? 'tag-primary' : ''}`}
                onClick={() => toggleJob(index)}
                style={{ cursor: 'pointer' }}
              >
                {selected[index] ? '已选' : '未选'} {job.company} - {job.title}
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedJobs.length > 0 && (
        <>
          <div className="card">
            <h3>基本信息对比</h3>
            <div className="compare-table-wrapper">
              <table className="table compare-table">
                <thead>
                  <tr>
                    <th>维度</th>
                    {selectedJobs.map((job, index) => (
                      <th key={job.seriesKey} style={{ color: COLORS[index % COLORS.length] }}>
                        {job.company}<br />{job.title}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr><td>城市</td>{selectedJobs.map(job => <td key={job.seriesKey}>{job.city}</td>)}</tr>
                  <tr><td>薪资</td>{selectedJobs.map(job => <td key={job.seriesKey}>{job.salary_label}</td>)}</tr>
                  <tr><td>经验要求</td>{selectedJobs.map(job => <td key={job.seriesKey}>{job.experience}</td>)}</tr>
                  <tr><td>学历要求</td>{selectedJobs.map(job => <td key={job.seriesKey}>{job.education}</td>)}</tr>
                  <tr>
                    <td>匹配度</td>
                    {selectedJobs.map(job => (
                      <td key={job.seriesKey}>
                        <strong style={{ color: scoreColor(job.match_score) }}>{formatScore(job.match_score)}</strong>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td>来源</td>
                    {selectedJobs.map(job => (
                      <td key={job.seriesKey}>
                        {job.source_link ? <a href={job.source_link} target="_blank" rel="noreferrer">查看</a> : '-'}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="charts-row">
            <div className="chart-card">
              <h3>薪资范围对比</h3>
              {hasSalaryData ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip formatter={value => `${value}K`} />
                    <Legend />
                    <Bar dataKey="salary_min" name="最低薪资(K)" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="salary_max" name="最高薪资(K)" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty">当前岗位数据暂未填写薪资范围</div>
              )}
            </div>

            <div className="chart-card">
              <h3>匹配度对比</h3>
              {hasScoreData ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 100]} />
                    <Tooltip formatter={value => `${value} 分`} />
                    <Bar dataKey="match" name="匹配分数" radius={[4, 4, 0, 0]}>
                      {barData.map((item, index) => <Cell key={item.name} fill={COLORS[index % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty">暂无匹配分数，请先在岗位匹配页运行一次匹配</div>
              )}
            </div>
          </div>

          <div className="chart-card">
            <h3>技能要求雷达</h3>
            {radarData.length ? (
              <ResponsiveContainer width="100%" height={400}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                  <PolarRadiusAxis domain={[0, 100]} />
                  {selectedJobs.map((job, index) => (
                    <Radar
                      key={job.seriesKey}
                      name={job.company}
                      dataKey={job.seriesKey}
                      stroke={COLORS[index % COLORS.length]}
                      fill={COLORS[index % COLORS.length]}
                      fillOpacity={0.1}
                    />
                  ))}
                  <Legend />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">当前岗位数据暂未填写技能要求</div>
            )}
          </div>

          <div className="card">
            <h3>技能要求详细对比</h3>
            {allSkills.length ? (
              <div className="compare-table-wrapper">
                <table className="table compare-table">
                  <thead>
                    <tr>
                      <th>技能</th>
                      {selectedJobs.map(job => <th key={job.seriesKey}>{job.company}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {allSkills.map(skill => (
                      <tr key={skill}>
                        <td><strong>{skill}</strong></td>
                        {selectedJobs.map(job => (
                          <td key={job.seriesKey}>{job.skills_required.includes(skill) ? '需要' : '-'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty">没有可对比的技能字段</div>
            )}
          </div>

          {selectedJobs.some(job => job.reason) && (
            <div className="card">
              <h3>匹配理由</h3>
              {selectedJobs.filter(job => job.reason).map(job => (
                <div className="info-block" key={job.seriesKey}>
                  <div className="info-title">{job.company} - {job.title}</div>
                  <p className="info-desc">{job.reason}</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
