import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, ArrowRight, CalendarClock, ClipboardList, Target, TrendingUp } from 'lucide-react';
import { getTrainingPlan } from '../api/client';

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-';
}

function scoreColor(score) {
  if (score == null) return 'var(--text-muted)';
  if (score >= 80) return 'var(--success)';
  if (score >= 60) return 'var(--warning)';
  return 'var(--error)';
}

export default function TrainingPlan() {
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getTrainingPlan()
      .then(setPlan)
      .catch(requestError => setError(requestError.message || '训练计划加载失败'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">加载训练计划...</div>;
  if (error) return <div className="alert alert-error">{error}</div>;

  const plans = plan?.plans || [];
  const priorityDimensions = plan?.priority_dimensions || [];
  const topPriority = priorityDimensions[0]?.name || '综合表达';
  const latestScore = plan?.latest_score;
  const nextGoal = typeof latestScore === 'number' ? Math.min(95, latestScore + 8) : 70;

  return (
    <div className="page">
      <div className="page-title-row">
        <h2>训练计划看板</h2>
        <button className="btn btn-primary" onClick={() => navigate('/interview')}>
          开始新面试
          <ArrowRight size={16} />
        </button>
      </div>

      <div className="training-hero">
        <div>
          <span className="tag tag-primary">阶段训练目标</span>
          <h3>优先提升：{topPriority}</h3>
          <p>系统根据已完成面试中的低分维度生成训练重点。建议下一次面试先围绕薄弱维度回答，再补 STAR 结构、项目细节和量化结果。</p>
        </div>
        <div className="training-goal-card">
          <span>下一次目标分</span>
          <strong>{nextGoal}</strong>
          <small>用于展示训练目标，不作为自动评分结果。</small>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon"><ClipboardList size={22} /></div>
          <div className="stat-info">
            <div className="stat-value">{plan?.total_completed || 0}</div>
            <div className="stat-label">有效面试次数</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon"><TrendingUp size={22} /></div>
          <div className="stat-info">
            <div className="stat-value">{plan?.average_score ?? '--'}</div>
            <div className="stat-label">平均得分</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon"><Activity size={22} /></div>
          <div className="stat-info">
            <div className="stat-value" style={{ color: scoreColor(plan?.latest_score) }}>
              {plan?.latest_score ?? '--'}
            </div>
            <div className="stat-label">最近一次得分</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header-row">
          <h3>优先训练维度</h3>
          <span className="text-muted">按低分出现频次排序</span>
        </div>
        {priorityDimensions.length ? (
          <div className="training-priority-list">
            {priorityDimensions.map(item => (
              <div className="training-priority-item" key={item.name}>
                <span className="tag tag-warning">{item.name}</span>
                <span>{item.count} 次出现在低分维度中</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty">暂无足够的已完成面试数据，完成一次面试后会生成训练重点。</div>
        )}
      </div>

      <div className="card">
        <div className="card-header-row">
          <h3>分次练习计划</h3>
          <span className="text-muted">每份报告生成一组可执行动作</span>
        </div>
        {plans.length === 0 ? (
          <div className="empty">
            <p>还没有可用训练计划。</p>
            <button className="btn btn-primary" onClick={() => navigate('/interview')}>开始第一次面试</button>
          </div>
        ) : (
          <div className="training-plan-list">
            {plans.map(item => (
              <section className="training-plan-card" key={item.session_id}>
                <div className="training-plan-header">
                  <div>
                    <h4>{item.job_title || '模拟岗位'} · {item.mode || '面试'}</h4>
                    <p><CalendarClock size={14} /> {formatTime(item.created_at)} · {item.company || '未关联公司'}</p>
                  </div>
                  <div className="training-score" style={{ color: scoreColor(item.score) }}>
                    {item.score ?? '--'}<span>分</span>
                  </div>
                </div>

                {(item.weak_dimensions || []).length > 0 && (
                  <div className="training-section">
                    <strong>薄弱维度</strong>
                    <div className="tag-group">
                      {item.weak_dimensions.map(dimension => (
                        <span className="tag tag-warning" key={dimension.name}>
                          {dimension.name} {dimension.score}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="training-section">
                  <strong>练习动作</strong>
                  <div className="action-checklist">
                    {(item.practice_actions || []).map((action, index) => (
                      <div className="action-checklist-item" key={index}>
                        <span>{index + 1}</span>
                        <p>{action}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {(item.star_suggestions || []).length > 0 && (
                  <div className="training-section">
                    <strong>STAR 改写建议</strong>
                    <div className="training-star-list">
                      {item.star_suggestions.slice(0, 3).map((suggestion, index) => (
                        <div className="training-star-item" key={index}>
                          {suggestion.question && <b>{suggestion.question}</b>}
                          <p>{suggestion.star_rewrite || suggestion.suggestion || JSON.stringify(suggestion)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {item.summary && (
                  <div className="training-summary">
                    <Target size={15} />
                    <span>{item.summary}</span>
                  </div>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
