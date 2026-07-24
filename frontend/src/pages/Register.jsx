import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { register as apiRegister } from '../api/client';

export default function Register() {
  const [form, setForm] = useState({ username: '', email: '', password: '', confirmPassword: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.username.trim() || !form.email.trim() || !form.password) {
      setError('请填写所有必填字段');
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    if (form.password.length < 6) {
      setError('密码长度不能少于6位');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRegister({ username: form.username, email: form.email, password: form.password });
      login(data.user || { username: form.username }, data.access_token);
      navigate('/');
    } catch (err) {
      setError(err.message || '注册失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>🤖 AI面试陪练</h1>
          <p>注册账号，开启智能面试之旅</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <h2>用户注册</h2>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-group">
            <label>用户名 *</label>
            <input type="text" value={form.username} onChange={update('username')} placeholder="请输入用户名" autoFocus />
          </div>
          <div className="form-group">
            <label>邮箱 *</label>
            <input type="email" value={form.email} onChange={update('email')} placeholder="请输入邮箱" />
          </div>
          <div className="form-group">
            <label>密码 *</label>
            <input type="password" value={form.password} onChange={update('password')} placeholder="至少6位密码" />
          </div>
          <div className="form-group">
            <label>确认密码 *</label>
            <input type="password" value={form.confirmPassword} onChange={update('confirmPassword')} placeholder="再次输入密码" />
          </div>
          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? '注册中...' : '注册'}
          </button>
          <p className="auth-footer">
            已有账号？<Link to="/login">立即登录</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
