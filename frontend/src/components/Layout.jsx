import { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const navItems = [
    { path: '/', label: '📊 数据看板', icon: '📊' },
    { path: '/resume', label: '📄 简历管理', icon: '📄' },
    { path: '/resume/review', label: '✅ 简历审核', icon: '✅' },
    { path: '/jobs', label: '💼 岗位管理', icon: '💼' },
    { path: '/jobs/review', label: '🔍 岗位审核', icon: '🔍' },
    { path: '/jobs/match', label: '🎯 岗位匹配', icon: '🎯' },
    { path: '/jobs/compare', label: '📈 多岗对比', icon: '📈' },
    { path: '/interview', label: '🎤 模拟面试', icon: '🎤' },
    { path: '/interview/history', label: '📋 面试记录', icon: '📋' },
  ];

  return (
    <div className="layout">
      <header className="layout-header">
        <div className="header-left">
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? '◀' : '▶'}
          </button>
          <h1>🤖 AI面试陪练</h1>
        </div>
        <div className="header-right">
          <span className="user-info">👤 {user?.username || '用户'}</span>
          <button
            className="btn btn-sm btn-outline"
            onClick={() => { logout(); navigate('/login'); }}
          >退出</button>
        </div>
      </header>
      <div className="layout-body">
        <aside className={`sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
          <nav className="sidebar-nav">
            {navItems.map(item => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {sidebarOpen && <span className="nav-label">{item.label}</span>}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
