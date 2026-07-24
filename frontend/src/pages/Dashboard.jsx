const tasks = [
  { owner: '组长', title: '项目骨架、后端基础、集成管理', branch: 'leader/project-scaffold' },
  { owner: '成员 A', title: '岗位采集、清洗、去重、审核', branch: 'feature/job-data-audit' },
  { owner: '成员 B', title: '知识库、向量检索、岗位匹配', branch: 'feature/vector-matching' },
  { owner: '成员 C', title: '简历审核与面试 Agent', branch: 'feature/resume-interview-agent' },
  { owner: '成员 D', title: '前端页面、可视化、测试材料', branch: 'feature/frontend-testing' }
];

function Dashboard() {
  return (
    <section className="dashboard">
      <div className="panel">
        <h2>开发分工</h2>
        <div className="task-list">
          {tasks.map((task) => (
            <div className="task-row" key={task.branch}>
              <strong>{task.owner}</strong>
              <span>{task.title}</span>
              <code>{task.branch}</code>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>验收重点</h2>
        <ul className="check-list">
          <li>至少 20 条真实岗位数据，包含来源链接和更新时间</li>
          <li>岗位必须经过 pending、approved、rejected 审核流程</li>
          <li>每名成员至少 5 条有效 Git 提交记录</li>
          <li>Agent 至少包含 3 个工具或工作流节点</li>
          <li>保留正常、失败和异常测试记录</li>
        </ul>
      </div>
    </section>
  );
}

export default Dashboard;

