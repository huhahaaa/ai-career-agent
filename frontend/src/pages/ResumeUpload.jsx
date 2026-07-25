import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getResumes, getResumeDetail, uploadResume, deleteResume } from '../api/client';

export default function ResumeUpload() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [compareMode, setCompareMode] = useState(false);
  const [compareSelections, setCompareSelections] = useState([]);
  const [compareVersions, setCompareVersions] = useState([]);
  const [comparing, setComparing] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    getResumes()
      .then(setResumes)
      .catch(error => setMsg({
        type: error.code === 50100 ? 'info' : 'error',
        text: error.message || '简历列表加载失败',
      }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'].includes(file.type) && !file.name.match(/\.(pdf|doc|docx)$/i)) {
      setMsg({ type: 'error', text: '仅支持PDF/DOC/DOCX格式' });
      return;
    }
    setUploading(true);
    setMsg({ type: '', text: '' });
    try {
      const fd = new FormData();
      fd.append('file', file);
      await uploadResume(fd);
      setMsg({ type: 'success', text: '上传成功，正在解析中...' });
      load();
    } catch (error) {
      setMsg({
        type: error.code === 50100 ? 'info' : 'error',
        text: error.message || '简历上传失败',
      });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('确定要删除该简历吗？')) return;
    try {
      await deleteResume(id);
      setMsg({ type: 'success', text: '删除成功' });
      load();
    } catch (error) {
      setMsg({
        type: error.code === 50100 ? 'info' : 'error',
        text: error.message || '简历删除失败',
      });
    }
  };

  const toggleCompareMode = () => {
    if (compareMode) {
      setCompareMode(false);
      setCompareSelections([]);
    } else {
      setCompareMode(true);
      setCompareSelections([]);
    }
  };

  const toggleCompareSelection = (id) => {
    setCompareSelections(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  const handleCompare = async () => {
    if (compareSelections.length < 2) {
      setMsg({ type: 'error', text: '请选择2个版本进行对比' });
      return;
    }
    setComparing(true);
    try {
      const [v1, v2] = await Promise.all(compareSelections.map(id => getResumeDetail(id)));
      setCompareVersions([v1, v2]);
      setShowCompareModal(true);
      setCompareMode(false);
      setCompareSelections([]);
    } catch (error) {
      setMsg({ type: 'error', text: error.message || '版本详情加载失败' });
    } finally {
      setComparing(false);
    }
  };

  const statusLabel = (s) => {
    const map = { pending: '待审核', processing: '解析中', approved: '已通过', rejected: '已驳回' };
    return map[s] || s;
  };
  const statusColor = (s) => ({ pending: 'warning', processing: 'info', approved: 'success', rejected: 'error' })[s] || '';

  if (loading) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <h2>📄 简历管理</h2>

      {msg.text && <div className={`alert alert-${msg.type}`}>{msg.text}</div>}

      <div className="card">
        <div className="upload-area">
          <label className="upload-label">
            <input type="file" accept=".pdf,.doc,.docx" onChange={handleUpload} disabled={uploading} hidden />
            <div className="upload-box">
              <span className="upload-icon">📁</span>
              <p>{uploading ? '上传中...' : '点击或拖拽上传简历'}</p>
              <span className="upload-hint">支持 PDF / DOC / DOCX 格式</span>
            </div>
          </label>
        </div>
      </div>

      <div className="card">
        <div className="card-header-row">
          <h3>📑 简历版本列表</h3>
          <div className="header-actions">
            {resumes.length >= 2 && (
              <button
                className={`btn btn-sm ${compareMode ? 'btn-danger' : 'btn-outline'}`}
                onClick={toggleCompareMode}
              >
                {compareMode ? '取消对比' : '版本对比'}
              </button>
            )}
            {compareMode && compareSelections.length >= 2 && (
              <button className="btn btn-sm btn-primary" onClick={handleCompare} disabled={comparing}>
                {comparing ? '加载中...' : `开始对比 (${compareSelections.length}/2)`}
              </button>
            )}
          </div>
        </div>
        {resumes.length === 0 ? (
          <div className="empty">暂无简历，请上传</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                {compareMode && <th>选择</th>}
                <th>文件名</th>
                <th>版本</th>
                <th>状态</th>
                <th>内容摘要</th>
                <th>上传时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {resumes.map(r => (
                <tr
                  key={r.id}
                  className={compareSelections.includes(r.id) ? 'row-selected' : ''}
                  onClick={() => compareMode && toggleCompareSelection(r.id)}
                  style={compareMode ? { cursor: 'pointer' } : {}}
                >
                  {compareMode && (
                    <td>
                      <span className={`compare-checkbox ${compareSelections.includes(r.id) ? 'checked' : ''}`}>
                        {compareSelections.includes(r.id) ? '✓' : '○'}
                      </span>
                    </td>
                  )}
                  <td>
                    <span className="filename-text">{r.filename}</span>
                  </td>
                  <td><span className="tag">v{r.version || 1}</span></td>
                  <td><span className={`tag tag-${statusColor(r.status)}`}>{statusLabel(r.status)}</span></td>
                  <td className="text-muted" style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.raw_text ? r.raw_text.substring(0, 50) + '...' : r.review_comment || '-'}
                  </td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td className="actions">
                    {r.status === 'approved' && (
                      <button className="btn btn-sm btn-outline" onClick={(e) => { e.stopPropagation(); navigate('/resume/review', { state: { resumeId: r.id } }); }}>
                        查看详情
                      </button>
                    )}
                    {!compareMode && (
                      <button className="btn btn-sm btn-danger" onClick={(e) => { e.stopPropagation(); handleDelete(r.id); }}>删除</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {compareMode && (
          <div className="compare-hint">
            点击行选择2个版本进行对比，已选 {compareSelections.length}/2
          </div>
        )}
      </div>

      {/* 版本对比弹窗 */}
      {showCompareModal && compareVersions.length === 2 && (
        <div className="modal-overlay" onClick={() => setShowCompareModal(false)}>
          <div className="modal modal-compare" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📊 简历版本对比</h3>
              <button className="btn btn-sm btn-outline" onClick={() => setShowCompareModal(false)}>✕</button>
            </div>
            <div className="modal-body compare-body">
              <div className="compare-container">
                <div className="compare-panel">
                  <div className="compare-panel-header">
                    <span className="tag tag-success">v{compareVersions[0].version || 1}</span>
                    <span>{compareVersions[0].filename}</span>
                    <span className="text-muted">{new Date(compareVersions[0].created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="compare-content">
                    <h4>技能标签</h4>
                    {compareVersions[0].skills_parsed?.length > 0 ? (
                      <div className="skill-tags">
                        {compareVersions[0].skills_parsed.map((s, i) => (
                          <span key={i} className="tag">{typeof s === 'object' ? s.name : s}</span>
                        ))}
                      </div>
                    ) : <p className="text-muted">暂无技能数据</p>}

                    <h4>简历原文</h4>
                    <pre className="compare-text">{compareVersions[0].raw_text || '暂无内容'}</pre>
                  </div>
                </div>

                <div className="compare-divider">
                  <span>VS</span>
                </div>

                <div className="compare-panel">
                  <div className="compare-panel-header">
                    <span className="tag tag-info">v{compareVersions[1].version || 1}</span>
                    <span>{compareVersions[1].filename}</span>
                    <span className="text-muted">{new Date(compareVersions[1].created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="compare-content">
                    <h4>技能标签</h4>
                    {compareVersions[1].skills_parsed?.length > 0 ? (
                      <div className="skill-tags">
                        {compareVersions[1].skills_parsed.map((s, i) => (
                          <span key={i} className="tag">{typeof s === 'object' ? s.name : s}</span>
                        ))}
                      </div>
                    ) : <p className="text-muted">暂无技能数据</p>}

                    <h4>简历原文</h4>
                    <pre className="compare-text">{compareVersions[1].raw_text || '暂无内容'}</pre>
                  </div>
                </div>
              </div>

              {/* 差异总结 */}
              <div className="compare-diff-summary">
                <h4>版本变化摘要</h4>
                <ul>
                  {compareVersions[0].filename !== compareVersions[1].filename && (
                    <li>文件名变更：{compareVersions[0].filename} → {compareVersions[1].filename}</li>
                  )}
                  {(() => {
                    const sk1 = compareVersions[0].skills_parsed?.map(s => typeof s === 'object' ? s.name : s) || [];
                    const sk2 = compareVersions[1].skills_parsed?.map(s => typeof s === 'object' ? s.name : s) || [];
                    const added = sk2.filter(s => !sk1.includes(s));
                    const removed = sk1.filter(s => !sk2.includes(s));
                    return (
                      <>
                        {added.length > 0 && <li>新增技能：<strong>{added.join(', ')}</strong></li>}
                        {removed.length > 0 && <li>移除技能：<span className="text-muted">{removed.join(', ')}</span></li>}
                        {!added.length && !removed.length && sk1.length > 0 && <li>技能标签无变化</li>}
                      </>
                    );
                  })()}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
