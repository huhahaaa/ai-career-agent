import { ArrowRight, CheckCircle2, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const CAREER_FLOW_STEPS = [
  { title: '上传简历', desc: '建立个人能力画像', path: '/resume' },
  { title: '简历审核', desc: 'AI 诊断优化建议', path: '/resume/review' },
  { title: '岗位匹配', desc: '锁定高匹配岗位', path: '/jobs/match' },
  { title: '模拟面试', desc: '实战演练与评分', path: '/interview' },
  { title: '训练提升', desc: '按计划定向补强', path: '/interview/training' },
];

/**
 * 流程引导组件：把求职主流程做成可点击的下一步入口。
 *
 * props:
 *   steps     { title, desc, path, icon? }[]
 *   current   当前所在步骤索引（0-based），默认 -1 表示从头开始
 *   completed 已完成步骤索引（0-based）
 *   message   自定义引导文案
 */
export default function FlowGuide({
  steps = [],
  current = -1,
  completed = -1,
  message,
}) {
  const navigate = useNavigate();
  if (!steps.length) return null;

  const nextStep = steps[current + 1] || null;
  const defaultMsg = current >= 0
    ? `✅ 已完成「${steps[current].title}」，接下来推荐您`
    : '🚀 开始您的求职准备之旅';

  return (
    <div className="flow-guide">
      <div className="flow-guide-progress" role="progressbar">
        {steps.map((step, index) => {
          const isDone = index <= completed;
          const isActive = index === current;
          return (
            <div
              key={step.title}
              className={`flow-guide-dot ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
              title={step.title}
            >
              {isDone ? (
                <CheckCircle2 size={16} />
              ) : (
                <span className="dot-num">{index + 1}</span>
              )}
              <span className="dot-label">{step.title}</span>
            </div>
          );
        })}
      </div>

      <div className="flow-guide-action">
        <div className="flow-guide-text">
          <Sparkles size={16} />
          <span>{message || defaultMsg}</span>
        </div>
        {nextStep ? (
          <button
            className="btn btn-primary flow-guide-btn"
            type="button"
            onClick={() => navigate(nextStep.path)}
          >
            <span className="flow-guide-btn-label">
              {nextStep.title}
              <span className="flow-guide-btn-desc">{nextStep.desc || ''}</span>
            </span>
            <ArrowRight size={18} />
          </button>
        ) : current >= steps.length - 1 ? (
          <span className="flow-guide-done">
            <CheckCircle2 size={18} /> 全部流程已完成，太棒了！
          </span>
        ) : (
          <button
            className="btn btn-primary flow-guide-btn"
            type="button"
            onClick={() => navigate(steps[0].path)}
          >
            开始第一步 <ArrowRight size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
