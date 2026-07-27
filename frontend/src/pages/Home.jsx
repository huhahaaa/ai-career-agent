import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  Briefcase,
  CheckSquare,
  ClipboardList,
  FileText,
  GraduationCap,
  LayoutDashboard,
  Mic,
  Search,
  Sparkles,
  Target,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const BASE_FEATURES = [
  { path: '/resume', icon: FileText, title: '简历管理', desc: '上传并管理多版本简历，PDF / Word 均可解析。' },
  { path: '/resume/review', icon: CheckSquare, title: '简历审核', desc: 'AI 多维度诊断简历，给出结构化修改建议。' },
  { path: '/jobs', icon: Briefcase, title: '岗位管理', desc: '浏览真实岗位库，收藏心仪岗位并跟进状态。' },
  { path: '/jobs/match', icon: Target, title: '岗位匹配', desc: '向量检索智能推荐岗位，附匹配分数与理由。' },
  { path: '/jobs/compare', icon: BarChart3, title: '多岗对比', desc: '横向对比岗位能力要求，看清差距明确方向。' },
  { path: '/interview', icon: Mic, title: '模拟面试', desc: 'AI 面试官全真演练，实时追问与结构化评分。' },
  { path: '/interview/history', icon: ClipboardList, title: '面试记录', desc: '回看历次面试报告，追踪每一次进步。' },
  { path: '/interview/training', icon: GraduationCap, title: '训练计划', desc: '依据面试表现生成个性化练习计划。' },
  { path: '/dashboard', icon: LayoutDashboard, title: '数据看板', desc: '技能画像、匹配得分与面试趋势一屏掌握。' },
];

const REVIEWER_FEATURE = { path: '/jobs/review', icon: Search, title: '岗位审核', desc: '审核岗位数据质量，维护岗位库内容。' };

const STEPS = [
  { icon: FileText, title: '上传简历', desc: '建立个人能力画像', path: '/resume' },
  { icon: CheckSquare, title: '简历审核', desc: 'AI 诊断优化建议', path: '/resume/review' },
  { icon: Target, title: '岗位匹配', desc: '锁定高匹配岗位', path: '/jobs/match' },
  { icon: Mic, title: '模拟面试', desc: '实战演练与评分', path: '/interview' },
  { icon: GraduationCap, title: '训练提升', desc: '按计划定向补强', path: '/interview/training' },
];

export default function Home() {
  const { user } = useAuth();
  const features = user?.role === 'reviewer' ? [REVIEWER_FEATURE, ...BASE_FEATURES] : BASE_FEATURES;
  const hour = new Date().getHours();
  const greeting = hour < 6 ? '夜深了' : hour < 12 ? '早上好' : hour < 18 ? '下午好' : '晚上好';

  return (
    <div className="page home-page">
      <section className="hero">
        <div className="hero-content">
          <span className="hero-badge"><Sparkles size={14} /> AI 驱动的求职训练平台</span>
          <h2>{greeting}，{user?.username || '同学'}<br />欢迎使用 智职通</h2>
          <p>
            从简历诊断、岗位匹配到模拟面试，一站式提升求职竞争力。
            每一次练习，都让你离心仪的 Offer 更近一步。
          </p>
          <div className="hero-actions">
            <Link to="/interview" className="btn btn-primary hero-btn-primary">
              开始模拟面试 <ArrowRight size={16} />
            </Link>
            <Link to="/resume" className="btn btn-outline hero-btn-outline">上传我的简历</Link>
          </div>
        </div>
      </section>

      <h3 className="home-section-title"><Sparkles size={18} /> 功能导航</h3>
      <div className="feature-grid">
        {features.map(f => (
          <Link key={f.path} to={f.path} className="feature-card">
            <span className="feature-icon"><f.icon size={20} /></span>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
            <span className="feature-link">立即体验 <ArrowRight size={14} /></span>
          </Link>
        ))}
      </div>

      <h3 className="home-section-title"><Target size={18} /> 推荐流程</h3>
      <div className="steps-flow">
        {STEPS.map((s, i) => (
          <Link key={s.title} to={s.path} className="step-item" style={{ cursor: 'pointer' }}>
            <span className="step-index">STEP {i + 1}</span>
            <span className="step-icon"><s.icon size={20} /></span>
            <h4>{s.title}</h4>
            <p>{s.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
