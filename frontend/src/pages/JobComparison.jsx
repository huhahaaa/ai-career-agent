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
import {
  appendApprovedJobOptions,
  defaultSelection,
  formatScore,
  normalizeHistoryRecord,
  normalizeImmediateMatch,
  normalizeJob,
  scoreColor,
} from '../utils/jobComparison';

const COLORS = [
  'var(--chart-primary)',
  'var(--chart-secondary)',
  'var(--chart-warning)',
  'var(--chart-danger)',
  'var(--chart-success)',
  'var(--chart-violet)',
];

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
          const matchedRows = routeMatches.map((match, index) => normalizeImmediateMatch(match, index, approvedJobs || []));
          const rows = appendApprovedJobOptions(matchedRows, approvedJobs);
          setCompareData(rows);
          setDataSource('当前匹配结果 + 已审核岗位');
          setSelected(defaultSelection(rows, matchedRows.length));
          if (rows.length > matchedRows.length) {
            setMessage('已合并当前匹配结果和已审核岗位；未匹配岗位可手动加入对比，但匹配度会显示为待匹配。');
          }
          return;
        }

        const history = await getMatches();
        if (history?.length) {
          const historyRows = history.map((record, index) => normalizeHistoryRecord(record, approvedJobs || [], index));
          const rows = appendApprovedJobOptions(historyRows, approvedJobs);
          setCompareData(rows);
          setDataSource('真实匹配历史 + 已审核岗位');
          setSelected(defaultSelection(rows, historyRows.length));
          if (rows.length > historyRows.length) {
            setMessage('已合并真实匹配历史和已审核岗位；未匹配岗位可手动加入对比，但匹配度会显示为待匹配。');
          }
          return;
        }

        const rows = (approvedJobs || []).map((job, index) => normalizeJob(job, index));
        setCompareData(rows);
        setDataSource('已审核岗位');
        setSelected(defaultSelection(rows));
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
    hasSalary: job.salary_comparable,
    match: typeof job.match_score === 'number' ? job.match_score : 0,
    hasScore: typeof job.match_score === 'number',
  }));

  const salaryBarData = barData.filter(item => item.hasSalary);
  const matchBarData = barData.filter(item => item.hasScore);
  const hasSalaryData = salaryBarData.length > 0;
  const hasScoreData = matchBarData.length > 0;
  const selectedCount = selectedJobs.length;

  if (loading) return <div className="loading">加载真实岗位对比数据...</div>;

  return (
    <div className="page">
      <h2>多岗位横向对比</h2>

      {message && <div className={`alert ${message.includes('失败') || message.includes('暂无') ? 'alert-error' : 'alert-info'}`}>{message}</div>}

      <div className="card">
        <div className="card-header-row">
          <div>
            <h3>选择对比岗位</h3>
            <span className="text-muted">数据来源：{dataSource || '真实接口'} | 已选 {selectedCount} / {compareData.length}</span>
          </div>
          <button className="btn btn-sm btn-outline" onClick={() => navigate('/jobs/match')}>去岗位匹配</button>
        </div>

        {compareData.length === 0 ? (
          <div className="empty">没有可展示的真实岗位数据</div>
        ) : (
          <div className="compare-job-grid">
            {compareData.map((job, index) => (
              <button
                key={`${job.id}-${index}`}
                className={`compare-job-option ${selected[index] ? 'selected' : ''}`}
                onClick={() => toggleJob(index)}
                type="button"
              >
                <span className="compare-job-status">{selected[index] ? '已选' : '未选'}</span>
                <span className="compare-job-main">
                  <strong>{job.company}</strong>
                  <span>{job.title}</span>
                </span>
                <span className="compare-job-meta">
                  {job.city}
                  <span>{formatScore(job.match_score)}</span>
                </span>
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
                    <td>命中技能</td>
                    {selectedJobs.map(job => (
                      <td key={job.seriesKey}>
                        {job.matched_skills?.length ? job.matched_skills.join('、') : '-'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td>缺失技能</td>
                    {selectedJobs.map(job => (
                      <td key={job.seriesKey}>
                        {job.missing_skills?.length ? job.missing_skills.join('、') : '-'}
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
              <h3>薪资范围对比（月薪K，未换算币种）</h3>
              {hasSalaryData ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={salaryBarData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip formatter={value => `${Number(value).toFixed(1)}K/月`} />
                    <Legend />
                    <Bar dataKey="salary_min" name="最低月薪(K)" fill="var(--chart-primary)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="salary_max" name="最高月薪(K)" fill="var(--chart-secondary)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty">所选岗位没有可按月薪 K 口径比较的公开薪资；时薪和未公开薪资已保留在表格中。</div>
              )}
            </div>

            <div className="chart-card">
              <h3>匹配度对比</h3>
              {hasScoreData ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={matchBarData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 100]} />
                    <Tooltip formatter={value => `${value} 分`} />
                    <Bar dataKey="match" name="匹配分数" radius={[4, 4, 0, 0]}>
                      {matchBarData.map((item, index) => <Cell key={item.name} fill={COLORS[index % COLORS.length]} />)}
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
                  {job.gap_analysis && <p className="info-desc">{job.gap_analysis}</p>}
                  {job.suggestion && <p className="info-desc">{job.suggestion}</p>}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
