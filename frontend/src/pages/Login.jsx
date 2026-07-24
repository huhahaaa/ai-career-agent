import { useState } from 'react';
import { useNavigate, Link, Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { login as apiLogin } from '../api/client';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();

  // 已登录用户直接跳转到首页
  if (isAuthenticated) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('请填写完整的用户名和密码');
      return;
    }
    setLoading(true);
    try {
      const data = await apiLogin(username, password);
      login(data.user || { username }, data.access_token);
      navigate('/');
    } catch (err) {
      setError(err.message || '登录失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>🤖 AI面试陪练</h1>
          <p>智能面试模拟，助力职业发展</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <h2>用户登录</h2>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-group">
            <label>用户名</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="请输入用户名"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="请输入密码"
            />
          </div>
          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? '登录中...' : '登录'}
          </button>
          <p className="auth-footer">
            还没有账号？<Link to="/register">立即注册</Link>
          </p>
          <p className="auth-hint">演示账号: demo / demo123</p>
        </form>
      </div>
    </div>
  );
}
