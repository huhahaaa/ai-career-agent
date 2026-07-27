import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { login as apiLogin } from '../api/client';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await apiLogin(formData.username, formData.password);
      login(response.user, response.access_token);
      navigate('/dashboard');
    } catch (err) {
      setError(err.data?.detail || err.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <img
            src="/logo.png"
            alt="智职通"
            style={{ width: 64, height: 64, objectFit: 'contain', marginBottom: 16 }}
          />
          <h1>智职通</h1>
          <p>AI 求职助手，智能规划职业未来</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <h2>用户登录</h2>

          {error && <div className="alert alert-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              id="username"
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="请输入用户名"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              id="password"
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={loading}
          >
            {loading ? '登录中...' : '登 录'}
          </button>

          <div className="auth-footer">
            还没有账号？ <Link to="/register">立即注册</Link>
          </div>

          <div className="auth-hint">
            测试账号：reviewer / reviewer123（审核员）
          </div>
        </form>
      </div>
    </div>
  );
}
