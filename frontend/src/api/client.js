const API_BASE = (import.meta.env.VITE_BACKEND_BASE || '/api/v1').replace(/\/$/, '');
const ROOT_BASE = API_BASE.endsWith('/api/v1')
  ? API_BASE.slice(0, -'/api/v1'.length)
  : API_BASE;
const USE_MOCK = String(import.meta.env.VITE_USE_MOCK || 'false').toLowerCase() === 'true';

const delay = (ms = 250) => new Promise(resolve => setTimeout(resolve, ms));

export class ApiError extends Error {
  constructor(message, { status = 0, code = 0, data = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

function buildHeaders(body, extraHeaders = {}) {
  const token = localStorage.getItem('token');
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  };
  if (body && !(body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
}

async function request(path, options = {}) {
  const { root = false, headers, ...fetchOptions } = options;
  const response = await fetch(`${root ? ROOT_BASE : API_BASE}${path}`, {
    ...fetchOptions,
    headers: buildHeaders(fetchOptions.body, headers),
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok || (payload && typeof payload.code === 'number' && payload.code !== 0)) {
    throw new ApiError(
      payload?.message || payload?.detail || `请求失败（HTTP ${response.status}）`,
      { status: response.status, code: payload?.code, data: payload?.data },
    );
  }

  if (payload && Object.prototype.hasOwnProperty.call(payload, 'data')) {
    return payload.data;
  }
  return payload;
}

async function mockFallback(action, factory) {
  try {
    return await action();
  } catch (error) {
    if (!USE_MOCK) throw error;
    await delay();
    return factory(error);
  }
}

function unavailable(feature) {
  return Promise.reject(new ApiError(`${feature}接口待接入`, { status: 501, code: 50100 }));
}

const mockUser = {
  id: 1,
  username: 'demo',
  email: 'demo@example.com',
  role: 'student',
  is_active: true,
  created_at: new Date().toISOString(),
};

let mockJobs = [
  {
    id: 1,
    title: '前端开发工程师',
    company: '示例科技',
    location: '北京',
    publish_time: '2026-07-24',
    skills: ['React', 'TypeScript'],
    source_link: 'https://example.com/jobs/1',
    status: 'approved',
    audit_comment: '示例审核记录',
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    title: 'Python 后端工程师',
    company: '课程项目公司',
    location: '上海',
    publish_time: '2026-07-24',
    skills: ['Python', 'FastAPI', 'SQL'],
    source_link: 'https://example.com/jobs/2',
    status: 'pending',
    audit_comment: '',
    updated_at: new Date().toISOString(),
  },
];

const mockMatches = [
  {
    job_id: 1,
    title: '前端开发工程师',
    company: '示例科技',
    score: 86.4,
    reason: '简历中的 React、TypeScript 经历与岗位要求高度相关。',
    source_link: 'https://example.com/jobs/1',
    matched_skills: ['React', 'TypeScript'],
    missing_skills: ['Node.js'],
    gap_analysis: '已命中 2/3 项技能，缺少：Node.js。',
    suggestion: '建议在项目经历中补充 Node.js 或后端接口协作经验。',
  },
];

const mockDashboard = {
  total_resumes: 1,
  total_jobs: mockJobs.length,
  total_interviews: 0,
  avg_score: 0,
  recent_interviews: [],
  skill_distribution: [{ name: 'Python', level: 80 }, { name: 'React', level: 72 }],
  job_skill_requirements: [{ skill: 'Python', count: 8 }, { skill: 'React', count: 6 }],
  capability_gap: [{ subject: 'Python', personal: 80, required: 75 }],
  multi_job_scores: [{ job: '示例科技(前端)', score: 86.4, color: '#2563eb' }],
  interview_trend: [],
  job_city_distribution: [{ name: '北京', value: 1 }, { name: '上海', value: 1 }],
};

export function getHealth() {
  return mockFallback(() => request('/health', { root: true }), () => ({ status: 'ok', mock: true }));
}

export function login(username, password) {
  return mockFallback(
    () => request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
    () => {
      if (username !== 'demo' || password !== 'demo123') {
        throw new ApiError('用户名或密码错误', { status: 401, code: 40101 });
      }
      return { user: mockUser, access_token: 'mock-token', token_type: 'bearer', expires_in: 7200 };
    },
  );
}

export function register(userData) {
  return mockFallback(
    () => request('/auth/register', { method: 'POST', body: JSON.stringify(userData) }),
    () => ({ ...mockUser, username: userData.username, email: userData.email }),
  );
}

export function getCurrentUser() {
  return mockFallback(() => request('/auth/me'), () => mockUser);
}

export function getDashboard() {
  return mockFallback(() => request('/admin/dashboard'), () => mockDashboard);
}

export function getResumes() {
  return mockFallback(() => request('/resumes'), () => []);
}

export function uploadResume(formData) {
  return mockFallback(
    () => request('/resumes/upload', { method: 'POST', body: formData }),
    () => ({ status: 'pending' }),
  );
}

export function deleteResume(id) {
  return mockFallback(() => request(`/resumes/${id}`, { method: 'DELETE' }), () => null);
}

export function getResumeDetail(id) {
  return mockFallback(() => request(`/resumes/${id}`), () => null);
}

export function auditResume({ resumeId = null, resumeText, targetPosition = '' }) {
  return mockFallback(
    () => request('/resumes/audit', {
      method: 'POST',
      body: JSON.stringify({
        resume_id: resumeId,
        resume_text: resumeText,
        target_position: targetPosition,
      }),
    }),
    () => ({
      score: 76,
      risk_flags: resumeText.length < 80 ? ['简历内容偏短，项目经历支撑不足。'] : [],
      suggestions: ['补充项目背景、个人职责、技术动作和量化结果。'],
      missing_keywords: targetPosition ? ['缓存', '部署', '接口性能优化'] : [],
      risk_level: '中',
    }),
  );
}

export function getJobs(params = {}) {
  return mockFallback(
    () => {
      const query = new URLSearchParams(params).toString();
      return request(`/jobs${query ? `?${query}` : ''}`);
    },
    () => mockJobs.filter(job => !params.status || job.status === params.status),
  );
}

export function getJobDetail(id) {
  return USE_MOCK
    ? Promise.resolve(mockJobs.find(job => String(job.id) === String(id)) || null)
    : unavailable('岗位详情');
}

export function createJob(data) {
  return mockFallback(
    () => request('/jobs/import', { method: 'POST', body: JSON.stringify(data) }),
    () => {
      const job = { ...data, id: Date.now(), status: 'pending', audit_comment: '', updated_at: new Date().toISOString() };
      mockJobs = [...mockJobs, job];
      return job;
    },
  );
}

export function updateJobStatus(id, status, comment = '') {
  return mockFallback(
    () => request(`/jobs/${id}/audit`, {
      method: 'PATCH',
      body: JSON.stringify({ status, comment }),
    }),
    () => {
      mockJobs = mockJobs.map(job => String(job.id) === String(id) ? { ...job, status, audit_comment: comment } : job);
      return mockJobs.find(job => String(job.id) === String(id));
    },
  );
}

export async function batchImportJobs(data) {
  const jobs = Array.isArray(data) ? data : data.jobs || [];
  const imported = [];
  for (const job of jobs) {
    imported.push(await createJob(job));
  }
  return { count: imported.length, jobs: imported };
}

export function getMatches() {
  return mockFallback(() => request('/matching/history'), () => mockMatches);
}

export function runMatching(resumeText, targetPosition = '', topK = 5) {
  return mockFallback(
    () => request('/matching/run', {
      method: 'POST',
      body: JSON.stringify({ resume_text: resumeText, target_position: targetPosition, top_k: topK }),
    }),
    () => ({ matches: mockMatches }),
  );
}

export function rebuildApprovedJobIndex() {
  return request('/matching/index/approved', { method: 'POST' });
}

export function startInterview({ resumeText, targetPosition = '', targetJobId = null }) {
  return mockFallback(
    () => request('/interviews/start', {
      method: 'POST',
      body: JSON.stringify({
        resume_text: resumeText,
        target_position: targetPosition,
        target_job_id: targetJobId,
      }),
    }),
    () => ({
      session_id: `mock-${Date.now()}`,
      question: `请结合项目经历说明你为什么适合${targetPosition || '目标岗位'}？`,
      tools_used: ['resume_analyzer', 'job_matcher', 'question_generator'],
    }),
  );
}

export function sendMessage(interviewId, answer) {
  return mockFallback(
    () => request(`/interviews/${interviewId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),
    () => ({
      score: answer.trim().length >= 40 ? 80 : 65,
      feedback: '建议补充具体场景、行动和量化结果。',
      next_question: '如果项目上线后出现性能问题，你会如何定位并优化？',
    }),
  );
}

export function endInterview(interviewId) {
  return mockFallback(
    () => request(`/interviews/${interviewId}/finish`, { method: 'POST' }),
    () => ({
      session_id: interviewId,
      overall_score: 72,
      dimension_averages: {},
      total_questions_answered: 1,
      details: [],
      star_suggestions: [],
      practice_plan: '继续补充 STAR 案例、技术细节和量化结果。',
      summary: '本次面试已生成模拟报告。',
    }),
  );
}

export function getInterviewHistory() {
  return mockFallback(() => request('/interviews/history'), () => []);
}

export function getInterviewReport(id) {
  return mockFallback(() => request(`/interviews/${id}/report`), () => null);
}

export function getCityDistribution() {
  return USE_MOCK
    ? Promise.resolve(mockDashboard.job_city_distribution)
    : unavailable('城市统计');
}
