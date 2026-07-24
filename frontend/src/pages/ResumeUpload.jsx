import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getResumes, uploadResume, deleteResume } from '../api/client';

export default function ResumeUpload() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });
  const navigate = useNavigate();

  const load = () => {
    getResumes()
      .then(setResumes)
      .catch(() => setMsg({ type: 'error', text: '加载失败' }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // 全局阻止浏览器拖拽文件下载的默认行为
  useEffect(() => {
    const preventDefaults = (e) => { e.preventDefault(); e.stopPropagation(); };
    window.addEventListener('dragover', preventDefaults);
    window.addEventListener('drop', preventDefaults);
    return () => {
      window.removeEventListener('dragover', preventDefaults);
      window.removeEventListener('drop', preventDefaults);
    };
  }, []);

  // 拖拽上传事件：阻止浏览器默认行为
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  const processFile = async (file) => {
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
      setMsg({ type: 'success', text: '上传成功，已加入简历版本列表，可手动发起审核' });
      load();
    } catch {
      setMsg({ type: 'error', text: '上传失败' });
    } finally {
      setUploading(false);
    }
  };

  const handleUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = '';
  };

  const handleDelete = async (id) => {
    if (!confirm('确定要删除该简历吗？')) return;
    try {
      await deleteResume(id);
      setMsg({ type: 'success', text: '删除成功' });
      load();
    } catch {
      setMsg({ type: 'error', text: '删除失败' });
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
        <div
          className={`upload-area ${isDragging ? 'drag-over' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <label className="upload-label">
            <input type="file" accept=".pdf,.doc,.docx" onChange={handleUpload} disabled={uploading} hidden />
            <div className="upload-box">
              <span className="upload-icon">📁</span>
              <p>{isDragging ? '松开以上传简历' : uploading ? '上传中...' : '点击或拖拽上传简历'}</p>
              <span className="upload-hint">支持 PDF / DOC / DOCX 格式</span>
            </div>
          </label>
        </div>
      </div>

      <div className="card">
        <h3>📑 简历版本列表</h3>
        {resumes.length === 0 ? (
          <div className="empty">暂无简历，请上传</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>版本</th>
                <th>状态</th>
                <th>审核意见</th>
                <th>上传时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {resumes.map(r => (
                <tr key={r.id}>
                  <td>{r.filename}</td>
                  <td><span className="tag">v{r.version}</span></td>
                  <td><span className={`tag tag-${statusColor(r.status)}`}>{statusLabel(r.status)}</span></td>
                  <td>{r.review_comment || '-'}</td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td className="actions">
                    {r.status === 'approved' ? (
                      <button className="btn btn-sm btn-outline" onClick={() => navigate('/resume/review', { state: { resumeId: r.id } })}>
                        查看详情
                      </button>
                    ) : (
                      <button className="btn btn-sm btn-primary" onClick={() => navigate('/resume/review', { state: { resumeId: r.id } })}>
                        去审核
                      </button>
                    )}
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(r.id)}>删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
