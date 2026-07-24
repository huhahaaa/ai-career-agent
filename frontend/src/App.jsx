import { useEffect, useState } from 'react';
import { Activity, BriefcaseBusiness, ClipboardCheck, FileSearch, MessagesSquare } from 'lucide-react';

import { getHealth } from './api/client';
import Dashboard from './pages/Dashboard';

const modules = [
  { name: '岗位数据审核', icon: ClipboardCheck },
  { name: '知识库与匹配', icon: FileSearch },
  { name: '简历优化', icon: BriefcaseBusiness },
  { name: '模拟面试 Agent', icon: MessagesSquare }
];

function App() {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    getHealth()
      .then((data) => setStatus(data.status || 'ok'))
      .catch(() => setStatus('offline'));
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>AI Career Agent</h1>
          <p>岗位采集审核、简历优化、岗位匹配与模拟面试工作台</p>
        </div>
        <div className={`status-pill status-${status}`}>
          <Activity size={16} />
          <span>{status}</span>
        </div>
      </header>

      <section className="module-grid">
        {modules.map((item) => {
          const Icon = item.icon;
          return (
            <article className="module-card" key={item.name}>
              <Icon size={22} />
              <span>{item.name}</span>
            </article>
          );
        })}
      </section>

      <Dashboard />
    </main>
  );
}

export default App;

