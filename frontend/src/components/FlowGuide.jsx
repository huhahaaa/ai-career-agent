import { ArrowRight, CheckCircle2, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

/**
 * 流程引导组件 —— 在每步完成后显示醒目的“下一步”按钮，降低手动翻侧栏的成本。
 *
 * props:
 *   steps     { title, desc, path, icon? }[]  整个流程
 *   current   当前所在步骤索引（0‑based），默认 -1 会渲染起步引导
 *   completed 已达到的步骤索引（0‑based），已完成步骤打勾
 *   message   自定义引导文案，为空时自动拼接「已完成 xxx，接下来推荐您…」
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
      {/* ---- 进度条 ---- */}
      <div className="flow-guide-progress" role="progressbar">
        {steps.map((s, i) => {
          const isDone = i <= completed;
          const isActive = i === current;
          return (
            <div
              key={s.title}
              className={`flow-guide-dot ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
              title={s.title}
            >
              {isDone ? (
                <CheckCircle2 size={16} />
              ) : (
                <span className="dot-num">{i + 1}</span>
              )}
              <span className="dot-label">{s.title}</span>
            </div>
          );
        })}
      </div>

      {/* ---- 引导文案 + 按钮 ---- */}
      <div className="flow-guide-action">
        <div className="flow-guide-text">
          <Sparkles size={16} />
          <span>{message || defaultMsg}</span>
        </div>

        {nextStep ? (
          <button
            className="btn btn-primary flow-guide-btn"
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
            onClick={() => navigate(steps[0].path)}
          >
            开始第一步 <ArrowRight size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
