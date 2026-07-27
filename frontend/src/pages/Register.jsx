import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { register } from '../api/client';

export default function Register() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    setLoading(true);

    try {
      await register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });
      navigate('/login');
    } catch (err) {
      setError(err.data?.detail || err.message || '注册失败');
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
          <h2>用户注册</h2>

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
            <label htmlFor="email">邮箱</label>
            <input
              id="email"
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="请输入邮箱"
              required
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
              placeholder="请输入密码（至少 6 位）"
              required
              minLength={6}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">确认密码</label>
            <input
              id="confirmPassword"
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="请再次输入密码"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={loading}
          >
            {loading ? '注册中...' : '注 册'}
          </button>

          <div className="auth-footer">
            已有账号？ <Link to="/login">立即登录</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
