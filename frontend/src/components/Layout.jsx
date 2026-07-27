import { useEffect, useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  Briefcase,
  CheckSquare,
  ClipboardList,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  Mic,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sun,
  Target,
  User,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const userRole = user?.role || 'student';
  const roleLabel = userRole === 'reviewer' ? '审核员' : '学生';
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  const navGroups = [
    {
      title: '工作台',
      items: [
        { path: '/', label: '主页', icon: Home },
        { path: '/dashboard', label: '数据看板', icon: LayoutDashboard },
      ],
    },
    {
      title: '简历',
      items: [
        { path: '/resume', label: '简历管理', icon: FileText },
        { path: '/resume/review', label: '简历审核', icon: CheckSquare },
      ],
    },
    {
      title: '岗位',
      items: [
        { path: '/jobs', label: '岗位管理', icon: Briefcase },
        { path: '/jobs/review', label: '岗位审核', icon: Search, roles: ['reviewer'] },
        { path: '/jobs/match', label: '岗位匹配', icon: Target },
        { path: '/jobs/compare', label: '多岗对比', icon: BarChart3 },
      ],
    },
    {
      title: '面试',
      items: [
        { path: '/interview', label: '模拟面试', icon: Mic },
        { path: '/interview/history', label: '面试记录', icon: ClipboardList },
        { path: '/interview/training', label: '训练计划', icon: Target },
      ],
    },
  ];

  return (
    <div className="layout">
      <header className="layout-header">
        <div className="header-left">
          <button
            className="sidebar-toggle icon-button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? '收起导航' : '展开导航'}
            title={sidebarOpen ? '收起导航' : '展开导航'}
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
          </button>
          <div className="brand-mark">
            <img src="/logo.png" alt="智职通" style={{ width: 28, height: 28, objectFit: 'contain' }} />
          </div>
          <h1>智职通</h1>
        </div>
        <div className="header-right">
          <button
            className="theme-toggle icon-button"
            type="button"
            onClick={() => setTheme(current => (current === 'dark' ? 'light' : 'dark'))}
            aria-label={theme === 'dark' ? '切换到明色模式' : '切换到暗色模式'}
            title={theme === 'dark' ? '明色模式' : '暗色模式'}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
          <span className="user-info"><User size={16} /> {user?.username || '用户'}</span>
          <span className={`role-badge role-${userRole}`}>{roleLabel}</span>
          <button
            className="btn btn-sm btn-outline"
            onClick={() => { logout(); navigate('/login'); }}
          >
            <LogOut size={15} />
            退出
          </button>
        </div>
      </header>
      <div className="layout-body">
        <aside className={`sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
          <nav className="sidebar-nav">
            {navGroups.map(group => {
              const visibleItems = group.items.filter(item => !item.roles || item.roles.includes(userRole));
              if (visibleItems.length === 0) return null;
              return (
                <div className="nav-group" key={group.title}>
                  {sidebarOpen && <div className="nav-group-title">{group.title}</div>}
                  {visibleItems.map(item => {
                    const Icon = item.icon;
                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        end
                        title={sidebarOpen ? undefined : item.label}
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                      >
                        <span className="nav-icon"><Icon size={18} /></span>
                        {sidebarOpen && <span className="nav-label">{item.label}</span>}
                      </NavLink>
                    );
                  })}
                </div>
              );
            })}
          </nav>
        </aside>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
