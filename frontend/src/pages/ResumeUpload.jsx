import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Star, Trash2 } from 'lucide-react';
import { getResumes, uploadResume, deleteResume, setDefaultResume } from '../api/client';
import FlowGuide from '../components/FlowGuide';

export default function ResumeUpload() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });
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
    if (!file.name.match(/\.(pdf|docx?|txt|md|rtf|html?|odt)$/i)) {
      setMsg({ type: 'error', text: '仅支持 PDF / DOC / DOCX / TXT / MD / RTF / HTML / ODT 格式' });
      return;
    }
    setUploading(true);
    setMsg({ type: '', text: '' });
    try {
      const fd = new FormData();
      fd.append('file', file);
      const result = await uploadResume(fd);
      const parsedLength = result?.parsed_text_length;
      setMsg({
        type: 'success',
        text: parsedLength != null
          ? `上传成功，已解析出 ${parsedLength} 字正文，可在简历审核页生成真实审核结果。`
          : '上传成功，可在简历审核页生成真实审核结果。',
      });
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

  const handleSetDefault = async (id) => {
    try {
      await setDefaultResume(id);
      setMsg({ type: 'success', text: '默认简历已更新，数据看板将优先统计这份简历。' });
      load();
    } catch (error) {
      setMsg({
        type: error.code === 50100 ? 'info' : 'error',
        text: error.message || '默认简历设置失败',
      });
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
              <input type="file" accept=".pdf,.doc,.docx,.txt,.md,.rtf,.html,.htm,.odt" onChange={handleUpload} disabled={uploading} hidden />
            <div className="upload-box">
              <span className="upload-icon">📁</span>
              <p>{uploading ? '上传中...' : '点击或拖拽上传简历'}</p>
              <span className="upload-hint">支持 PDF / DOC / DOCX / TXT / MD / RTF / HTML / ODT，上传后自动解析正文，均可直接审核</span>
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
                <th>默认</th>
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
                  <td>
                    {r.is_default ? (
                      <span className="tag tag-primary">当前主简历</span>
                    ) : (
                      <button className="btn btn-sm btn-outline" onClick={() => handleSetDefault(r.id)}>
                        <Star size={14} />
                        设为默认
                      </button>
                    )}
                  </td>
                  <td><span className={`tag tag-${statusColor(r.status)}`}>{statusLabel(r.status)}</span></td>
                  <td>{r.review_comment || '-'}</td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td className="actions">
                    {r.status === 'approved' && (
                      <button className="btn btn-sm btn-outline" onClick={() => navigate('/resume/review', { state: { resumeId: r.id } })}>
                        <Eye size={14} />
                        查看详情
                      </button>
                    )}
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(r.id)}>
                      <Trash2 size={14} />
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <FlowGuide
        steps={[
          { title: '上传简历', desc: '建立个人能力画像', path: '/resume' },
          { title: '简历审核', desc: 'AI 诊断优化建议', path: '/resume/review' },
          { title: '岗位匹配', desc: '锁定高匹配岗位', path: '/jobs/match' },
          { title: '模拟面试', desc: '实战演练与评分', path: '/interview' },
          { title: '训练提升', desc: '按计划定向补强', path: '/interview/training' },
        ]}
        current={0}
        completed={resumes.length > 0 ? 0 : -1}
      />
    </div>
  );
}
