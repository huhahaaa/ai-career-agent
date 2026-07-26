import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import ResumeUpload from './pages/ResumeUpload';
import ResumeReview from './pages/ResumeReview';
import JobCollection from './pages/JobCollection';
import JobReview from './pages/JobReview';
import JobSearchMatch from './pages/JobSearchMatch';
import JobComparison from './pages/JobComparison';
import MockInterview from './pages/MockInterview';
import InterviewHistory from './pages/InterviewHistory';
import TrainingPlan from './pages/TrainingPlan';
import ErrorPage, { NotFoundPage, ServerErrorPage, AgentErrorPage } from './pages/ErrorPage';

function RoleRoute({ roles, children }) {
  const { user } = useAuth();
  if (!roles.includes(user?.role)) {
    return <Navigate to="/" replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* 公开路由 - 不需要登录 */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/error/agent" element={<AgentErrorPage />} />
          <Route path="/error/500" element={<ServerErrorPage />} />
          <Route path="/error" element={<ErrorPage />} />
          <Route path="/404" element={<NotFoundPage />} />

          {/* 受保护路由 - 需要登录才能访问 */}
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            {/* 主页欢迎页 */}
            <Route path="/" element={<Home />} />
            {/* 数据看板 */}
            <Route path="/dashboard" element={<Dashboard />} />

            {/* 简历管理 */}
            <Route path="/resume" element={<ResumeUpload />} />
            <Route path="/resume/review" element={<ResumeReview />} />

            {/* 岗位管理 */}
            <Route path="/jobs" element={<JobCollection />} />
            <Route path="/jobs/review" element={<RoleRoute roles={['reviewer']}><JobReview /></RoleRoute>} />
            <Route path="/jobs/match" element={<JobSearchMatch />} />
            <Route path="/jobs/compare" element={<JobComparison />} />

            {/* 模拟面试 */}
            <Route path="/interview" element={<MockInterview />} />
            <Route path="/interview/history" element={<InterviewHistory />} />
            <Route path="/interview/training" element={<TrainingPlan />} />
          </Route>

          {/* 兜底 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
