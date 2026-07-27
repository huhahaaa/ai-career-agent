import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import {
  CheckCircle2,
  FileText,
  GitCompare,
  Pencil,
  RotateCcw,
  Save,
  Upload,
} from 'lucide-react';
import {
  auditResume,
  compareResumeVersions,
  createResumeVersion,
  getResumeDetail,
  getResumes,
} from '../api/client';
import FlowGuide from '../components/FlowGuide';

function formatTime(value) {
  if (!value) return '-';
  const raw = String(value);
  const normalized = /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw) ? raw : `${raw}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function statusLabel(status) {
  return ({ pending: '待审核', approved: '已审核', rejected: '已驳回' })[status] || status || '-';
}

function statusColor(status) {
  return ({ pending: 'warning', approved: 'success', rejected: 'error' })[status] || 'info';
}

function latestVersion(detail) {
  const versions = detail?.versions || [];
  return versions[versions.length - 1] || null;
}

function contentPreview(text) {
  const normalized = (text || '').replace(/\s+/g, ' ').trim();
  return normalized.length > 80 ? `${normalized.slice(0, 80)}...` : normalized || '暂无正文';
}

function isErrorMessage(message) {
  return /失败|无法|过短|请选择/.test(message);
}

export default function ResumeReview() {
  const location = useLocation();
  const navigate = useNavigate();
  const [resumes, setResumes] = useState([]);
  const [selectedId, setSelectedId] = useState(location.state?.resumeId || '');
  const [detail, setDetail] = useState(null);
  const [selectedVersionNumber, setSelectedVersionNumber] = useState(null);
  const [targetPosition, setTargetPosition] = useState(location.state?.targetPosition || '');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [auditing, setAuditing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [savingVersion, setSavingVersion] = useState(false);
  const [compareFrom, setCompareFrom] = useState(1);
  const [compareTo, setCompareTo] = useState(1);
  const [compareResult, setCompareResult] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [message, setMessage] = useState('');

  const versions = useMemo(() => detail?.versions || [], [detail]);
  const latest = latestVersion(detail);
  const activeVersion = versions.find(item => item.version === Number(selectedVersionNumber)) || latest;
  const report = detail?.latest_report || null;
  const scoreData = report ? [{ name: '综合评分', score: report.score }] : [];
  const versionCount = versions.length;
  const activeContent = editing ? editText : (activeVersion?.content || '');
  const compareTargetPosition = targetPosition.trim() || report?.target_position || '';
  const reportMatchesCurrentContext = report
    ? (!report.resume_version || report.resume_version === activeVersion?.version)
      && ((report.target_position || '') === compareTargetPosition)
    : true;

  const auditButtonText = useMemo(() => {
    if (auditing) return '审核中...';
    return report ? '重新审核当前版本' : '审核当前版本';
  }, [auditing, report]);

  const loadResumes = async () => {
    setLoading(true);
    setMessage('');
    try {
      const data = await getResumes();
      setResumes(data || []);
      if (!selectedId && data?.length) {
        setSelectedId(data[0].id);
      }
    } catch (error) {
      setMessage(error.message || '简历列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async id => {
    if (!id) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setMessage('');
    try {
      const data = await getResumeDetail(id);
      setDetail(data);
    } catch (error) {
      setMessage(error.message || '简历详情加载失败');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadResumes();
  }, []);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId]);

  useEffect(() => {
    if (!versions.length) return;
    const newest = versions[versions.length - 1];
    setSelectedVersionNumber(newest.version);
    setCompareFrom(versions[0].version);
    setCompareTo(newest.version);
    setCompareResult(null);
    setEditing(false);
  }, [detail?.id, versionCount]);

  useEffect(() => {
    setEditText(activeVersion?.content || '');
  }, [activeVersion?.id]);

  const handleSelectVersion = versionNumber => {
    if (editing) {
      setMessage('当前正在编辑，请先保存为新版本或放弃修改后再切换版本。');
      return;
    }
    setSelectedVersionNumber(versionNumber);
    setEditing(false);
    setCompareResult(null);
    setMessage('');
  };

  const handleStartEditing = () => {
    if (!activeVersion) {
      setMessage('请先选择一份有正文的简历。');
      return;
    }
    setEditText(activeVersion.content || '');
    setEditing(true);
    setMessage('');
  };

  const handleAudit = async () => {
    const resumeText = activeContent.trim();
    if (resumeText.length < 10) {
      setMessage('当前版本正文过短，无法审核。请确认文件不是扫描版 PDF，或先编辑保存为新版本。');
      return;
    }

    setAuditing(true);
    setMessage('');
    try {
      await auditResume({
        resumeId: Number(selectedId),
        resumeText,
        targetPosition: targetPosition.trim(),
        resumeVersion: activeVersion?.version || detail?.version,
      });
      await Promise.all([loadDetail(selectedId), loadResumes()]);
      setMessage(`v${activeVersion?.version || detail?.version} 审核已完成。`);
    } catch (error) {
      setMessage(error.message || '简历审核失败');
    } finally {
      setAuditing(false);
    }
  };

  const handleSaveVersion = async () => {
    if (!selectedId || editText.trim().length < 10) {
      setMessage('简历正文至少需要 10 个字符，才能保存为新版本。');
      return;
    }
    setSavingVersion(true);
    setMessage('');
    try {
      const nextVersion = (detail?.version || 1) + 1;
      const data = await createResumeVersion(selectedId, {
        content: editText.trim(),
        fileName: `${detail?.filename || 'resume'}-v${nextVersion}.md`,
      });
      setDetail(data);
      setSelectedVersionNumber(data.version);
      setCompareFrom(activeVersion?.version || 1);
      setCompareTo(data.version);
      await loadResumes();
      setEditing(false);
      setCompareResult(null);
      setMessage(`已保存为 v${data.version}，原版本仍保留，可直接对比修改效果。`);
    } catch (error) {
      setMessage(error.message || '保存新版本失败');
    } finally {
      setSavingVersion(false);
    }
  };

  const handleCompare = async () => {
    if (!selectedId || Number(compareFrom) === Number(compareTo)) {
      setMessage('请选择两个不同版本进行对比。');
      return;
    }
    setComparing(true);
    setMessage('');
    try {
      const data = await compareResumeVersions(
        selectedId,
        compareFrom,
        compareTo,
        compareTargetPosition,
      );
      setCompareResult(data);
    } catch (error) {
      setMessage(error.message || '版本对比失败');
    } finally {
      setComparing(false);
    }
  };

  if (loading) return <div className="loading">加载真实简历...</div>;

  return (
    <div className="page resume-review-page">
      <div className="page-title-row">
        <h2>简历审核与版本优化</h2>
        <button className="btn btn-outline" onClick={() => navigate('/resume')}>
          <Upload size={16} />
          上传新简历
        </button>
      </div>

      {message && <div className={`alert ${isErrorMessage(message) ? 'alert-error' : 'alert-info'}`}>{message}</div>}

      <div className="card">
        <div className="card-header-row">
          <h3>选择审核对象</h3>
          {detail && (
            <div className="tag-group">
              <span className={`tag tag-${statusColor(detail.status)}`}>{statusLabel(detail.status)}</span>
              <span className="tag">共 {versionCount} 个版本</span>
              {detail.is_default && <span className="tag tag-primary">默认简历</span>}
            </div>
          )}
        </div>
        {resumes.length === 0 ? (
          <div className="empty">暂无真实简历，请先上传 PDF、DOC、DOCX、TXT、MD、RTF、HTML 或 ODT 简历。</div>
        ) : (
          <div className="form-grid">
            <div className="form-group">
              <label>简历</label>
              <select value={selectedId} onChange={event => setSelectedId(event.target.value)}>
                {resumes.map(item => (
                  <option key={item.id} value={item.id}>
                    {item.is_default ? '[默认] ' : ''}{item.filename} - {statusLabel(item.status)}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>目标岗位</label>
              <input
                value={targetPosition}
                onChange={event => setTargetPosition(event.target.value)}
                placeholder="不填则只比较简历质量；如：Python 后端工程师"
              />
            </div>
          </div>
        )}
      </div>

      {detailLoading && <div className="loading">加载简历详情...</div>}

      {detail && !detailLoading && (
        <>
          <div className="resume-workspace">
            <aside className="resume-version-panel">
              <div className="resume-version-panel-header">
                <FileText size={18} />
                <div>
                  <strong>版本列表</strong>
                  <span>点击查看历史版本</span>
                </div>
              </div>
              <div className="resume-version-list">
                {versions.map(item => (
                  <button
                    key={item.id}
                    type="button"
                    className={`resume-version-item ${activeVersion?.version === item.version ? 'active' : ''}`}
                    onClick={() => handleSelectVersion(item.version)}
                  >
                    <span className="resume-version-main">
                      <strong>v{item.version}</strong>
                      {item.version === detail.version && <em>当前</em>}
                    </span>
                    <span>{formatTime(item.created_at)}</span>
                    <small>{contentPreview(item.content)}</small>
                  </button>
                ))}
              </div>
            </aside>

            <section className="card resume-editor-card">
              <div className="resume-editor-header">
                <div>
                  <h3>{detail.filename}</h3>
                  <p>
                    正在查看 v{activeVersion?.version || detail.version}
                    {activeVersion?.created_at ? ` · ${formatTime(activeVersion.created_at)}` : ''}
                    {activeVersion?.content_length != null ? ` · ${activeVersion.content_length} 字` : ''}
                  </p>
                </div>
                <div className="toolbar">
                  <button className="btn btn-primary" onClick={handleAudit} disabled={auditing || editing}>
                    <CheckCircle2 size={16} />
                    {auditButtonText}
                  </button>
                  {!editing && (
                    <button className="btn btn-outline" onClick={handleStartEditing}>
                      <Pencil size={16} />
                      修改并生成新版本
                    </button>
                  )}
                </div>
              </div>

              {editing ? (
                <div className="resume-edit-area">
                  <div className="edit-hint">
                    当前编辑内容来自 v{activeVersion?.version}。保存后会生成新版本，不会覆盖原始简历。
                  </div>
                  <textarea
                    value={editText}
                    onChange={event => setEditText(event.target.value)}
                    rows={18}
                    autoFocus
                  />
                  <div className="toolbar">
                    <button className="btn btn-primary" onClick={handleSaveVersion} disabled={savingVersion}>
                      <Save size={16} />
                      {savingVersion ? '保存中...' : `保存为 v${(detail?.version || 1) + 1}`}
                    </button>
                    <button
                      className="btn btn-outline"
                      onClick={() => {
                        setEditing(false);
                        setEditText(activeVersion?.content || '');
                      }}
                    >
                      <RotateCcw size={16} />
                      放弃修改
                    </button>
                  </div>
                </div>
              ) : (
                <pre className="resume-content-preview">{activeVersion?.content || '当前版本没有可用正文。'}</pre>
              )}
            </section>
          </div>

          {versionCount >= 2 && (
            <div className="card">
              <div className="card-header-row">
                <h3>版本效果对比</h3>
                <span className="text-muted">
                  {compareTargetPosition
                    ? `当前目标岗位：${compareTargetPosition}`
                    : '未填写目标岗位：仅比较简历质量和技能变化'}
                </span>
              </div>
              <div className="form-grid version-compare-form">
                <div className="form-group">
                  <label>修改前</label>
                  <select value={compareFrom} onChange={event => setCompareFrom(Number(event.target.value))}>
                    {versions.map(item => (
                      <option key={item.version} value={item.version}>v{item.version} - {item.filename}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>修改后</label>
                  <select value={compareTo} onChange={event => setCompareTo(Number(event.target.value))}>
                    {versions.map(item => (
                      <option key={item.version} value={item.version}>v{item.version} - {item.filename}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group form-actions">
                  <button className="btn btn-primary" onClick={handleCompare} disabled={comparing}>
                    <GitCompare size={16} />
                    {comparing ? '对比中...' : '生成对比'}
                  </button>
                </div>
              </div>
              {compareResult ? (
                <>
                  <div className="stats-grid compact">
                    <div className="stat-card">
                      <div className="stat-value">{compareResult.before?.estimated_match_score ?? '--'}</div>
                      <div className="stat-label">
                        {compareTargetPosition ? '修改前岗位匹配估算' : '修改前简历质量估算'}
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{compareResult.after?.estimated_match_score ?? '--'}</div>
                      <div className="stat-label">
                        {compareTargetPosition ? '修改后岗位匹配估算' : '修改后简历质量估算'}
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">
                        {compareResult.score_delta > 0 ? '+' : ''}{compareResult.score_delta ?? 0}
                      </div>
                      <div className="stat-label">分数变化</div>
                    </div>
                  </div>
                  <div className="compare-grid">
                    <div>
                      <h4>新增技能</h4>
                      <div className="tag-group">
                        {(compareResult.added_skills || []).length
                          ? compareResult.added_skills.map(item => <span key={item} className="tag tag-success">{item}</span>)
                          : <span className="tag">无新增</span>}
                      </div>
                    </div>
                    <div>
                      <h4>已补齐缺口</h4>
                      <div className="tag-group">
                        {(compareResult.resolved_missing_keywords || []).length
                          ? compareResult.resolved_missing_keywords.map(item => <span key={item} className="tag tag-primary">{item}</span>)
                          : <span className="tag">暂无变化</span>}
                      </div>
                    </div>
                    <div>
                      <h4>{compareTargetPosition ? '仍缺岗位关键词' : '未设置岗位缺口'}</h4>
                      <div className="tag-group">
                        {compareTargetPosition && (compareResult.after?.missing_keywords || []).length
                          ? compareResult.after.missing_keywords.map(item => <span key={item} className="tag tag-warning">{item}</span>)
                          : <span className="tag tag-success">
                            {compareTargetPosition ? '无明显缺口' : '填写目标岗位后再分析缺口'}
                          </span>}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="empty compact-empty">选择两个版本后生成对比，适合展示“v1 为什么要修改、v2 改进了什么”。</div>
              )}
            </div>
          )}

          {report ? (
            <>
              <div className="charts-row">
                <div className="chart-card">
                  <h3>最近一次审核评分</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={scoreData} margin={{ top: 20, right: 20, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis domain={[0, 100]} />
                      <Tooltip formatter={value => `${value} 分`} />
                      <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                        <Cell fill={report.score >= 80 ? 'var(--success)' : report.score >= 60 ? 'var(--warning)' : 'var(--error)'} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="card">
                  <h3>审核结论</h3>
                  {!reportMatchesCurrentContext && (
                    <div className="alert alert-warning">
                      当前显示的是最近一次历史审核，不一定对应正在查看的版本或目标岗位。重新审核当前版本后，评分和关键词会按当前上下文刷新。
                    </div>
                  )}
                  <div className="info-block">
                    <div className="info-title">风险等级：{report.risk_level}</div>
                    <div className="info-sub">
                      生成时间：{formatTime(report.created_at)}
                      {report.resume_version ? ` · 审核版本：v${report.resume_version}` : ''}
                      {report.target_position ? ` · 目标岗位：${report.target_position}` : ' · 未设置目标岗位'}
                    </div>
                  </div>
                  <div className="tag-group">
                    {(report.missing_keywords || []).length > 0
                      ? report.missing_keywords.map(item => <span key={item} className="tag tag-warning">{item}</span>)
                      : <span className="tag tag-success">暂无明确缺失关键词</span>}
                  </div>
                </div>
              </div>

              <div className="card">
                <h3>风险问题</h3>
                {(report.risk_flags || []).length === 0 ? (
                  <div className="empty">暂无明显风险问题</div>
                ) : (
                  <ul className="feedback-section">
                    {report.risk_flags.map((item, index) => <li key={index}>{item}</li>)}
                  </ul>
                )}
              </div>

              <div className="card">
                <h3>修改建议</h3>
                <ul className="feedback-section">
                  {(report.suggestions || []).map((item, index) => <li key={index}>{item}</li>)}
                </ul>
              </div>
            </>
          ) : (
            <div className="card">
              <div className="empty">这份简历还没有审核报告，点击“审核当前版本”生成真实结果。</div>
            </div>
          )}

          {(detail.audit_reports || []).length > 1 && (
            <div className="card">
              <h3>历史审核记录</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>评分</th>
                    <th>风险等级</th>
                    <th>审核口径</th>
                    <th>问题数</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.audit_reports.map(item => (
                    <tr key={item.id}>
                      <td>{formatTime(item.created_at)}</td>
                      <td>{item.score}</td>
                      <td>{item.risk_level}</td>
                      <td>
                        {item.resume_version ? `v${item.resume_version}` : '未记录版本'}
                        {' / '}
                        {item.target_position || '未设置岗位'}
                      </td>
                      <td>{item.risk_flags?.length || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <FlowGuide
        steps={[
          { title: '上传简历', desc: '建立个人能力画像', path: '/resume' },
          { title: '简历审核', desc: 'AI 诊断优化建议', path: '/resume/review' },
          { title: '岗位匹配', desc: '锁定高匹配岗位', path: '/jobs/match' },
          { title: '模拟面试', desc: '实战演练与评分', path: '/interview' },
          { title: '训练提升', desc: '按计划定向补强', path: '/interview/training' },
        ]}
        current={1}
        completed={1}
      />
    </div>
  );
}
