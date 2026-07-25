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

export function getDashboard(days = 30) {
  return mockFallback(() => request(`/dashboard?days=${days}`), () => mockDashboard);
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
  return mockFallback(() => request(`/jobs/${id}`), () => {
    const found = mockJobs.find(job => String(job.id) === String(id));
    return found || null;
  });
}

export function getApprovedJobs() {
  return mockFallback(
    () => request('/jobs/approved'),
    () => mockJobs.filter(job => job.status === 'approved'),
  );
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
  return USE_MOCK ? Promise.resolve(mockMatches) : unavailable('匹配结果历史');
}

export function runMatching(resumeText, targetPosition = '', topK = 5) {
  const body = typeof resumeText === 'object' && resumeText !== null
    ? { resume_text: '', target_position: '', top_k: 5, ...resumeText }
    : { resume_text: resumeText, target_position: targetPosition, top_k: topK };
  return mockFallback(
    () => request('/matching/run', { method: 'POST', body: JSON.stringify(body) }),
    () => ({ matches: mockMatches }),
  );
}

export function rebuildApprovedJobIndex() {
  return request('/matching/index/approved', { method: 'POST' });
}

const START_INTERVIEW_MOCK = {
  session_id: `ses_${Date.now()}`,
  question: '请结合项目经历说明你为什么适合目标岗位？',
  tools_used: ['resume_analyzer', 'job_matcher', 'question_generator'],
  mode: 'comprehensive',
};

const INTERVIEW_KNOWLEDGE_MOCK = {
  category: 'system_design',
  content:
    '系统设计面试建议从需求澄清开始，逐步深入到架构设计、组件拆分、数据流。回答时先给出高层方案再讨论细节。',
};

const INTERVIEW_HISTORY_MOCK = [];

export function startInterview({ resumeText, targetPosition = '', targetJobId = null } = {}) {
  return mockFallback(
    () =>
      request('/interviews/start', {
        method: 'POST',
        body: JSON.stringify({
          resume_text: resumeText,
          target_position: targetPosition,
          target_job_id: targetJobId,
        }),
      }),
    () => START_INTERVIEW_MOCK,
  );
}

export function sendMessage(interviewId, message) {
  return mockFallback(
    async () => {
      const data = await request(`/interviews/${interviewId}/answer`, {
        method: 'POST',
        body: JSON.stringify({ answer: message }),
      });
      if (data && typeof data.role === 'string' && typeof data.content === 'string') {
        return data;
      }
      const content = data?.followup_question || data?.next_question || '请继续。';
      return {
        role: 'interviewer',
        content,
        score: data?.score ?? null,
        feedback: data?.feedback ?? '',
        timestamp: new Date().toISOString(),
      };
    },
    () => ({
      role: 'interviewer',
      content:
        '感谢你的回答。综合来看你的经历与岗位有一定匹配度，但在项目深度和具体指标方面还可以更突出。' +
        '下面是基于你的回答生成的追问：你能再详细说明一个你在项目中遇到的技术难题以及你是如何解决的？',
      timestamp: new Date().toISOString(),
    }),
  );
}

export function endInterview(interviewId) {
  return mockFallback(
    () =>
      request(`/interviews/${interviewId}/finish`, { method: 'POST' }).then((data) => ({
        score: Math.round(data.overall_score || 0),
        feedback: {
          overall: data.summary || '',
          strengths: data.strengths || [],
          weaknesses: data.weaknesses || [],
        },
        dimension_scores: data.dimension_averages || {},
        jobTitle: '',
        timestamp: new Date().toISOString(),
      })),
    () => ({
      score: 78,
      feedback: {
        overall:
          '整体表现良好，技术基础扎实，沟通表达清晰。' +
          '建议在回答中更多使用 STAR 方法论来结构化表达经历。' +
          '技术人员面试中，除了技术能力还会考察团队协作、问题解决和学习能力。',
        strengths: [
          '技术基础扎实，对主流框架和工具有实际使用经验',
          '表达能力清晰，能逻辑清楚地描述项目背景和个人职责',
          '有实际的工程化思维，关注代码质量和开发流程',
        ],
        weaknesses: [
          '回答缺少具体的数据指标和量化结果',
          '对复杂业务场景的抽象能力还可以继续提升',
          '部分深度追问回答不够具体，需要更多系统性思考',
        ],
      },
      timestamp: new Date().toISOString(),
      jobTitle: '前端工程师',
    }),
  );
}

export function getInterviewHistory() {
  return mockFallback(() => request('/interviews/history'), () => INTERVIEW_HISTORY_MOCK);
}

export function getInterviewReport(id) {
  return mockFallback(
    () =>
      request(`/interviews/${id}/report`).then((data) => ({
        id,
        score: data?.score ?? 0,
        feedback: data?.feedback ?? {
          overall: '',
          strengths: [],
          weaknesses: [],
        },
        dimension_scores: data?.dimension_scores ?? {},
        jobTitle: data?.jobTitle ?? '',
        timestamp: data?.created_at || new Date().toISOString(),
      })),
    () => ({
      id,
      score: 78,
      feedback: {
        overall:
          '整体表现良好，技术基础扎实，沟通表达清晰。' +
          '建议在回答中更多使用 STAR 方法论来结构化表达经历。',
        strengths: [
          '技术基础扎实，对主流框架和工具有实际使用经验',
          '表达能力清晰，能逻辑清楚地描述项目背景和个人职责',
        ],
        weaknesses: [
          '回答缺少具体的数据指标和量化结果',
          '部分深度追问回答不够具体',
        ],
      },
      timestamp: new Date().toISOString(),
      jobTitle: '前端工程师',
    }),
  );
}

export function getKnowledgeBase(params) {
  return mockFallback(
    () =>
      request('/interviews/knowledge', {
        method: 'POST',
        body: JSON.stringify(params || {}),
      }),
    () => INTERVIEW_KNOWLEDGE_MOCK,
  );
}

export function resetInterviewState() {
  return Promise.resolve();
}

export function getCityDistribution() {
  return USE_MOCK
    ? Promise.resolve(mockDashboard.job_city_distribution)
    : unavailable('城市统计');
}
