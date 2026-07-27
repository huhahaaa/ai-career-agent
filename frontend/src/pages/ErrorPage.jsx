import { useRouteError, Link } from 'react-router-dom';

export default function ErrorPage() {
  const error = useRouteError();

  return (
    <div className="error-page">
      <div className="error-card">
        <div className="error-icon">⚠️</div>
        <h1>出错了</h1>
        <p>{error?.message || error?.statusText || '页面发生了未知错误'}</p>
        {error?.status && <span className="tag tag-error">HTTP {error.status}</span>}
        <div className="error-actions">
          <Link to="/" className="btn btn-primary">返回首页</Link>
          <button className="btn btn-outline" onClick={() => window.location.reload()}>刷新页面</button>
        </div>
      </div>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="error-page">
      <div className="error-card">
        <div className="error-icon">🔍</div>
        <h1>404</h1>
        <p>抱歉，您访问的页面不存在</p>
        <div className="error-actions">
          <Link to="/" className="btn btn-primary">返回首页</Link>
        </div>
      </div>
    </div>
  );
}

export function ServerErrorPage() {
  return (
    <div className="error-page">
      <div className="error-card">
        <div className="error-icon">🔧</div>
        <h1>500</h1>
        <p>服务器内部错误，请稍后重试</p>
        <div className="error-actions">
          <Link to="/" className="btn btn-primary">返回首页</Link>
          <button className="btn btn-outline" onClick={() => window.location.reload()}>刷新页面</button>
        </div>
      </div>
    </div>
  );
}

export function AgentErrorPage() {
  return (
    <div className="page">
      <h2>⚠️ Agent运行异常</h2>
      <div className="card">
        <div className="error-detail">
          <div className="error-detail-icon">
            <img className="error-logo" src="/logo.png" alt="智职通" />
          </div>
          <h3>服务运行异常</h3>
          <p>模拟面试Agent（run_dev.sh）在执行过程中遇到异常，目前面试流程暂时中断。</p>
          <div className="error-info-box">
            <h4>可能原因</h4>
            <ul>
              <li>Agent进程未能正常启动</li>
              <li>向量数据库连接失败</li>
              <li>大语言模型 API 调用超时</li>
              <li>依赖服务未正确配置</li>
              <li>Prompt模板加载失败</li>
              <li>内存溢出导致进程崩溃</li>
            </ul>
          </div>
          <div className="error-info-box">
            <h4>建议操作</h4>
            <ul>
              <li>检查 chromadb 服务是否正常运行（端口8001）</li>
              <li>确认 LLM API Key 配置正确（.env文件）</li>
              <li>查看后台日志排查具体错误</li>
              <li>重启后端服务（uvicorn main:app --reload）</li>
              <li>检查 Python 依赖是否安装完整（pip install -r requirements.txt）</li>
            </ul>
          </div>
          <div className="error-actions">
            <Link to="/interview" className="btn btn-primary">🔄 重新开始面试</Link>
            <Link to="/" className="btn btn-outline">返回首页</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
