// ===== Mock Data =====
const delay = (ms = 300) => new Promise(r => setTimeout(r, ms));

// 用户相关 Mock
const mockUser = { id: 'u1', username: 'demo', email: 'demo@example.com', role: 'candidate', avatar: null, created_at: '2026-06-01' };

// 简历 Mock 数据（localStorage 持久化）
const RESUME_STORAGE_KEY = 'ai_career_mock_resumes';

const defaultResumes = [
  { id: 'r1', user_id: 'u1', filename: '张三_前端开发_2026.pdf', original_name: '张三_前端开发简历.pdf', version: 1, status: 'approved', parsed_content: { name: '张三', email: 'zhangsan@example.com', phone: '13800001111', education: [{ school: '清华大学', degree: '本科', major: '计算机科学', start: '2020', end: '2024' }], skills: ['React', 'Vue', 'TypeScript', 'Node.js', 'Python', 'CSS3', 'HTML5', 'Git', 'Webpack', 'Docker'], experience: [{ company: '某科技公司', position: '前端开发实习生', start: '2023-06', end: '2024-06', description: '参与公司核心产品前端开发，使用React+TypeScript技术栈' }], projects: [{ name: '电商平台', role: '前端负责人', description: '使用React+Redux搭建大型电商平台前端', tech_stack: ['React', 'Redux', 'TypeScript'] }] }, review_comment: '技能描述清晰，项目经验丰富', created_at: '2026-07-20T10:00:00' },
  { id: 'r2', user_id: 'u1', filename: '张三_全栈开发_v2.pdf', original_name: '全栈开发简历v2.pdf', version: 2, status: 'pending', parsed_content: null, review_comment: null, created_at: '2026-07-22T14:30:00' },
];

function loadResumes() {
  try {
    const raw = localStorage.getItem(RESUME_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return JSON.parse(JSON.stringify(defaultResumes));
}

function saveResumes(resumes) {
  try { localStorage.setItem(RESUME_STORAGE_KEY, JSON.stringify(resumes)); } catch {}
}

let mockResumes = loadResumes();

// 岗位 Mock 数据（localStorage 持久化）
const JOB_STORAGE_KEY = 'ai_career_mock_jobs';

const defaultJobs = [
  { id: 'j1', title: '前端开发工程师', company: '字节跳动', city: '北京', salary_min: 25000, salary_max: 45000, experience: '1-3年', education: '本科', skills_required: ['React', 'TypeScript', 'CSS3', 'HTML5', 'Webpack', 'Node.js', '性能优化', '工程化'], description: '负责抖音电商前端开发工作，参与核心业务迭代', status: 'published', created_at: '2026-07-15' },
  { id: 'j2', title: '前端开发工程师', company: '腾讯', city: '深圳', salary_min: 20000, salary_max: 40000, experience: '1-3年', education: '本科', skills_required: ['Vue', 'JavaScript', 'CSS3', 'HTML5', 'Node.js', '小程序开发', '跨端开发'], description: '参与微信小程序和Web端开发，负责支付模块前端', status: 'published', created_at: '2026-07-16' },
  { id: 'j3', title: '全栈开发工程师', company: '阿里巴巴', city: '杭州', salary_min: 28000, salary_max: 50000, experience: '3-5年', education: '本科', skills_required: ['React', 'Node.js', 'Python', 'MySQL', 'Docker', 'Kubernetes', 'Redis', '微服务'], description: '负责淘宝商家平台全栈开发与架构升级', status: 'published', created_at: '2026-07-17' },
  { id: 'j4', title: '前端架构师', company: '美团', city: '北京', salary_min: 35000, salary_max: 60000, experience: '5-10年', education: '本科', skills_required: ['React', 'Vue', 'TypeScript', 'Node.js', '微前端', '性能优化', '工程化', '团队管理'], description: '负责美团前端架构设计和技术规划，推动技术升级', status: 'published', created_at: '2026-07-18' },
  { id: 'j5', title: 'Web前端开发', company: '小红书', city: '上海', salary_min: 22000, salary_max: 38000, experience: '1-3年', education: '本科', skills_required: ['React', 'Vue', 'TypeScript', 'CSS3', 'HTML5', '小程序', '性能优化'], description: '参与小红书Web端和小程序开发', status: 'pending', created_at: '2026-07-19' },
  { id: 'j6', title: '前端开发实习生', company: '滴滴', city: '北京', salary_min: 8000, salary_max: 12000, experience: '应届', education: '本科', skills_required: ['React', 'JavaScript', 'CSS3', 'HTML5', 'Git'], description: '参与滴滴出行前端开发，有导师一对一指导', status: 'published', created_at: '2026-07-20' },
  { id: 'j7', title: '后端开发工程师', company: '华为', city: '深圳', salary_min: 28000, salary_max: 50000, experience: '3-5年', education: '本科', skills_required: ['Java', 'Spring Boot', '微服务', 'MySQL', 'Redis', 'Kafka', 'Docker', '分布式系统'], description: '负责华为云核心服务后端开发与性能优化', status: 'published', created_at: '2026-07-21' },
  { id: 'j8', title: '算法工程师(NLP)', company: '百度', city: '北京', salary_min: 30000, salary_max: 55000, experience: '1-3年', education: '硕士', skills_required: ['Python', 'PyTorch', 'NLP', 'Transformer', '深度学习', '数据挖掘', '机器学习'], description: '参与百度搜索算法优化，自然语言处理方向', status: 'published', created_at: '2026-07-21' },
  { id: 'j9', title: '数据分析师', company: '京东', city: '北京', salary_min: 20000, salary_max: 35000, experience: '1-3年', education: '本科', skills_required: ['SQL', 'Python', 'Tableau', '数据可视化', 'Hive', 'SPSS', 'Excel'], description: '负责京东物流数据分析和业务决策支持', status: 'pending', created_at: '2026-07-21' },
  { id: 'j10', title: 'UI/UX设计师', company: '网易', city: '杭州', salary_min: 18000, salary_max: 35000, experience: '1-3年', education: '本科', skills_required: ['Figma', 'Sketch', 'Photoshop', '交互设计', '用户研究', '动效设计', '设计系统'], description: '负责网易云音乐产品界面设计与用户体验优化', status: 'published', created_at: '2026-07-22' },
  { id: 'j11', title: '测试开发工程师', company: '快手', city: '北京', salary_min: 22000, salary_max: 40000, experience: '1-3年', education: '本科', skills_required: ['Python', 'Selenium', '自动化测试', '性能测试', 'Jenkins', '接口测试', 'Java'], description: '负责快手短视频业务质量保障和自动化测试平台开发', status: 'published', created_at: '2026-07-22' },
  { id: 'j12', title: 'DevOps工程师', company: '拼多多', city: '上海', salary_min: 25000, salary_max: 45000, experience: '3-5年', education: '本科', skills_required: ['Kubernetes', 'Docker', 'Jenkins', 'Linux', 'Prometheus', 'Ansible', 'Shell', 'Python'], description: '负责拼多多基础架构和CI/CD流水线建设', status: 'published', created_at: '2026-07-22' },
  { id: 'j13', title: '前端开发工程师', company: 'B站', city: '上海', salary_min: 22000, salary_max: 40000, experience: '1-3年', education: '本科', skills_required: ['React', 'TypeScript', 'Next.js', 'Node.js', '性能优化', 'CSS3', 'WebAssembly'], description: '参与B站主站前端开发和直播业务技术升级', status: 'published', created_at: '2026-07-23' },
  { id: 'j14', title: '移动端开发工程师', company: '携程', city: '上海', salary_min: 23000, salary_max: 42000, experience: '3-5年', education: '本科', skills_required: ['Flutter', 'React Native', 'Android', 'iOS', 'Dart', 'Swift', 'Kotlin'], description: '负责携程App跨端开发和用户体验优化', status: 'published', created_at: '2026-07-23' },
  { id: 'j15', title: '安全工程师', company: '360', city: '北京', salary_min: 25000, salary_max: 48000, experience: '3-5年', education: '本科', skills_required: ['渗透测试', '漏洞挖掘', 'Python', '网络安全', '逆向工程', 'WAF', '入侵检测'], description: '负责360安全产品研发和漏洞挖掘分析', status: 'published', created_at: '2026-07-23' },
  { id: 'j16', title: '产品经理(技术方向)', company: '小米', city: '北京', salary_min: 22000, salary_max: 40000, experience: '1-3年', education: '本科', skills_required: ['产品设计', '数据分析', 'Axure', '需求分析', 'SQL', 'PRD', '项目管理'], description: '负责小米IoT平台产品规划和需求设计', status: 'pending', created_at: '2026-07-23' },
  { id: 'j17', title: '数据工程师', company: '蚂蚁集团', city: '杭州', salary_min: 28000, salary_max: 52000, experience: '3-5年', education: '本科', skills_required: ['Spark', 'Flink', 'Hadoop', 'Java', 'Scala', 'Kafka', 'Hive', '数据仓库'], description: '负责蚂蚁金服大数据平台建设和数据治理', status: 'published', created_at: '2026-07-24' },
  { id: 'j18', title: '前端开发工程师', company: '米哈游', city: '上海', salary_min: 25000, salary_max: 48000, experience: '1-3年', education: '本科', skills_required: ['React', 'Three.js', 'Canvas', 'TypeScript', 'WebGL', '动画', '性能优化'], description: '负责米哈游游戏官网和运营活动前端开发', status: 'published', created_at: '2026-07-24' },
  { id: 'j19', title: '全栈工程师', company: '知乎', city: '北京', salary_min: 24000, salary_max: 42000, experience: '3-5年', education: '本科', skills_required: ['React', 'Node.js', 'Go', 'MySQL', 'Redis', '消息队列', '微服务'], description: '参与知乎社区业务全栈开发和系统优化', status: 'published', created_at: '2026-07-24' },
  { id: 'j20', title: 'Python开发工程师', company: '大疆', city: '深圳', salary_min: 25000, salary_max: 45000, experience: '1-3年', education: '本科', skills_required: ['Python', 'Django', 'Flask', 'MySQL', 'Docker', 'RESTful', 'Celery'], description: '负责大疆内部系统开发和无人机管理平台后端', status: 'published', created_at: '2026-07-24' },
  { id: 'j21', title: '前端开发工程师', company: '蔚来', city: '上海', salary_min: 23000, salary_max: 43000, experience: '1-3年', education: '本科', skills_required: ['React', 'TypeScript', 'Node.js', '可视化', 'ECharts', '小程序', 'WebSocket'], description: '负责蔚来能源云平台前端开发和数据可视化', status: 'pending', created_at: '2026-07-24' },
  { id: 'j22', title: 'AI产品经理', company: '商汤科技', city: '北京', salary_min: 25000, salary_max: 50000, experience: '3-5年', education: '硕士', skills_required: ['人工智能', '产品规划', 'CV', 'NLP', '数据分析', '竞品分析', 'PRD'], description: '负责商汤AI开放平台产品规划和商业化落地', status: 'published', created_at: '2026-07-24' },
];

function loadJobs() {
  try {
    const raw = localStorage.getItem(JOB_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return JSON.parse(JSON.stringify(defaultJobs));
}

function saveJobs(jobs) {
  try { localStorage.setItem(JOB_STORAGE_KEY, JSON.stringify(jobs)); } catch {}
}

let mockJobs = loadJobs();

// 匹配结果 Mock 数据
const mockMatches = [
  { job_id: 'j1', job_title: '前端开发工程师', company: '字节跳动', overall_score: 82, skill_match_score: 78, experience_match_score: 85, education_match_score: 90, matched_skills: ['React', 'TypeScript', 'CSS3', 'HTML5', 'Webpack', 'Node.js'], missing_skills: ['性能优化', '工程化'], city: '北京', salary_min: 25000, salary_max: 45000 },
  { job_id: 'j2', job_title: '前端开发工程师', company: '腾讯', overall_score: 70, skill_match_score: 65, experience_match_score: 75, education_match_score: 90, matched_skills: ['Vue', 'CSS3', 'HTML5', 'Node.js'], missing_skills: ['JavaScript', '小程序开发', '跨端开发'], city: '深圳', salary_min: 20000, salary_max: 40000 },
  { job_id: 'j3', job_title: '全栈开发工程师', company: '阿里巴巴', overall_score: 68, skill_match_score: 60, experience_match_score: 70, education_match_score: 90, matched_skills: ['React', 'Node.js', 'Python', 'Docker'], missing_skills: ['MySQL', 'Kubernetes', 'Redis', '微服务'], city: '杭州', salary_min: 28000, salary_max: 50000 },
  { job_id: 'j4', job_title: '前端架构师', company: '美团', overall_score: 55, skill_match_score: 50, experience_match_score: 45, education_match_score: 90, matched_skills: ['React', 'Vue', 'TypeScript', 'Node.js'], missing_skills: ['微前端', '性能优化', '工程化', '团队管理'], city: '北京', salary_min: 35000, salary_max: 60000 },
  { job_id: 'j6', job_title: '前端开发实习生', company: '滴滴', overall_score: 95, skill_match_score: 98, experience_match_score: 90, education_match_score: 90, matched_skills: ['React', 'JavaScript', 'CSS3', 'HTML5', 'Git'], missing_skills: [], city: '北京', salary_min: 8000, salary_max: 12000 },
  { job_id: 'j13', job_title: '前端开发工程师', company: 'B站', overall_score: 78, skill_match_score: 80, experience_match_score: 75, education_match_score: 90, matched_skills: ['React', 'TypeScript', 'Node.js', 'CSS3'], missing_skills: ['Next.js', 'WebAssembly', '性能优化'], city: '上海', salary_min: 22000, salary_max: 40000 },
  { job_id: 'j18', job_title: '前端开发工程师', company: '米哈游', overall_score: 72, skill_match_score: 75, experience_match_score: 70, education_match_score: 90, matched_skills: ['React', 'TypeScript'], missing_skills: ['Three.js', 'Canvas', 'WebGL', '动画'], city: '上海', salary_min: 25000, salary_max: 48000 },
  { job_id: 'j21', job_title: '前端开发工程师', company: '蔚来', overall_score: 76, skill_match_score: 78, experience_match_score: 72, education_match_score: 90, matched_skills: ['React', 'TypeScript', 'Node.js'], missing_skills: ['可视化', 'ECharts', '小程序', 'WebSocket'], city: '上海', salary_min: 23000, salary_max: 43000 },
];

// 面试记录 Mock 数据
const mockInterviews = [
  { id: 'i1', job_title: '前端开发工程师', company: '字节跳动', mode: 'mock', status: 'completed', score: 82, duration_minutes: 25, questions_count: 10, feedback: { overall: '技术基础扎实，但系统设计经验不足', strengths: ['React熟练度高', 'TypeScript基础好'], weaknesses: ['性能优化经验欠缺', '工程化理解不够深入'], dimension_scores: { star_method: 78, technical_accuracy: 85, communication: 80, problem_solving: 70, code_quality: 82, project_experience: 75 } }, created_at: '2026-07-21T09:00:00' },
  { id: 'i2', job_title: '前端开发工程师', company: '腾讯', mode: 'mock', status: 'completed', score: 70, duration_minutes: 20, questions_count: 8, feedback: { overall: '需要加强基础知识学习', strengths: ['Vue使用经验'], weaknesses: ['JS基础', '算法能力'], dimension_scores: { star_method: 65, technical_accuracy: 72, communication: 75, problem_solving: 60, code_quality: 68, project_experience: 70 } }, created_at: '2026-07-22T14:00:00' },
  { id: 'i3', job_title: '前端开发实习生', company: '滴滴', mode: 'mock', status: 'completed', score: 95, duration_minutes: 18, questions_count: 6, feedback: { overall: '优秀，完全满足实习要求', strengths: ['React熟练', '沟通表达清晰'], weaknesses: [], dimension_scores: { star_method: 92, technical_accuracy: 95, communication: 96, problem_solving: 93, code_quality: 94, project_experience: 92 } }, created_at: '2026-07-23T10:00:00' },
  { id: 'i4', job_title: '前端开发工程师', company: 'B站', mode: 'mock', status: 'completed', score: 78, duration_minutes: 22, questions_count: 9, feedback: { overall: '技术基础不错，需要提升项目阐述能力', strengths: ['React掌握好', 'TypeScript使用熟练'], weaknesses: ['项目经验描述不清', 'Next.js不熟悉'], dimension_scores: { star_method: 70, technical_accuracy: 82, communication: 72, problem_solving: 78, code_quality: 80, project_experience: 68 } }, created_at: '2026-07-24T11:00:00' },
  { id: 'i5', job_title: '前端开发工程师', company: '米哈游', mode: 'mock', status: 'completed', score: 72, duration_minutes: 20, questions_count: 8, feedback: { overall: '基础尚可，需要提升可视化相关能力', strengths: ['React基础扎实'], weaknesses: ['Canvas/WebGL不熟', '动画经验不足'], dimension_scores: { star_method: 68, technical_accuracy: 75, communication: 70, problem_solving: 72, code_quality: 74, project_experience: 65 } }, created_at: '2026-07-24T15:00:00' },
];

// 会话 Mock 数据（模拟面试对话）
const mockMessages = [
  { role: 'interviewer', content: '你好！欢迎参加前端开发工程师的模拟面试。我是今天的面试官，请先简单介绍一下自己。', timestamp: '2026-07-24T10:00:00' },
];

// 数据看板 Mock 数据
const mockDashboard = {
  total_resumes: 2,
  total_jobs: 22,
  total_interviews: 5,
  avg_score: 78.4,
  city_distribution: { '北京': 9, '上海': 7, '深圳': 3, '杭州': 3 },
  recently_added: [
    { id: 'j20', title: 'Python开发工程师', company: '大疆', city: '深圳', created_at: '2026-07-24' },
    { id: 'j22', title: 'AI产品经理', company: '商汤科技', city: '北京', created_at: '2026-07-24' },
    { id: 'j17', title: '数据工程师', company: '蚂蚁集团', city: '杭州', created_at: '2026-07-24' },
  ],
  recommended_jobs: [
    { id: 'j6', title: '前端开发实习生', company: '滴滴', city: '北京', reason: '技能匹配度最高 (98%)', score: 95 },
    { id: 'j1', title: '前端开发工程师', company: '字节跳动', city: '北京', reason: '综合匹配度高 (82%)', score: 82 },
    { id: 'j13', title: '前端开发工程师', company: 'B站', city: '上海', reason: '技术栈匹配 (80%)', score: 78 },
    { id: 'j21', title: '前端开发工程师', company: '蔚来', city: '上海', reason: '行业前景好', score: 76 },
    { id: 'j18', title: '前端开发工程师', company: '米哈游', city: '上海', reason: '匹配度较高', score: 72 },
  ],
  recent_interviews: mockInterviews,
  skill_distribution: [
    { name: 'React', level: 90 },
    { name: 'Vue', level: 75 },
    { name: 'TypeScript', level: 80 },
    { name: 'Node.js', level: 70 },
    { name: 'Python', level: 65 },
    { name: 'CSS3', level: 85 },
    { name: 'HTML5', level: 90 },
    { name: 'Git', level: 80 },
    { name: 'Webpack', level: 70 },
    { name: 'Docker', level: 55 },
  ],
  job_skill_requirements: [
    { skill: 'React', count: 18 },
    { skill: 'Vue', count: 12 },
    { skill: 'TypeScript', count: 15 },
    { skill: 'Node.js', count: 14 },
    { skill: 'CSS3', count: 20 },
    { skill: 'HTML5', count: 20 },
    { skill: 'JavaScript', count: 16 },
    { skill: 'Git', count: 14 },
  ],
  capability_gap: [
    { subject: 'React', personal: 90, required: 85 },
    { subject: 'Vue', personal: 75, required: 70 },
    { subject: 'TypeScript', personal: 80, required: 85 },
    { subject: 'Node.js', personal: 70, required: 75 },
    { subject: 'Python', personal: 65, required: 40 },
    { subject: 'Docker', personal: 55, required: 80 },
    { subject: '性能优化', personal: 30, required: 75 },
    { subject: '工程化', personal: 35, required: 70 },
  ],
  multi_job_scores: [
    { job: '字节跳动(前端)', score: 82, color: '#6366f1' },
    { job: '腾讯(前端)', score: 70, color: '#06b6d4' },
    { job: '阿里(全栈)', score: 68, color: '#f59e0b' },
    { job: '美团(架构师)', score: 55, color: '#ef4444' },
    { job: '滴滴(实习)', score: 95, color: '#22c55e' },
    { job: 'B站(前端)', score: 78, color: '#ec4899' },
    { job: '蔚来(前端)', score: 76, color: '#8b5cf6' },
    { job: '米哈游(前端)', score: 72, color: '#14b8a6' },
  ],
  interview_trend: [
    { date: '07-21', score: 82 },
    { date: '07-22', score: 70 },
    { date: '07-23', score: 95 },
    { date: '07-24', score: 78 },
    { date: '07-24', score: 72 },
  ],
  job_city_distribution: [
    { name: '北京', value: 9 },
    { name: '上海', value: 7 },
    { name: '深圳', value: 3 },
    { name: '杭州', value: 3 },
    { name: '广州', value: 5 },
    { name: '成都', value: 3 },
  ],
};

// ===== API Functions =====

const BASE_URL = 'http://localhost:8000/api/v1';

const getHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

async function request(url, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}${url}`, {
      ...options,
      headers: { ...getHeaders(), ...options.headers },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  } catch (e) {
    if (e.message.includes('Failed to fetch') || e.message.includes('NetworkError')) {
      console.warn('Backend not available, using mock data');
      throw e;
    }
    throw e;
  }
}

// ===== 健康检查 =====
export async function getHealth() {
  try { return await request('/health'); }
  catch { return { status: 'ok', mock: true }; }
}

// ===== 用户认证 =====
export async function login(username, password) {
  try {
    const data = await request('/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password }),
    });
    return data;
  } catch {
    await delay();
    if (username === 'demo' && password === 'demo123') {
      return { user: mockUser, access_token: 'mock_token_demo', token_type: 'bearer' };
    }
    throw new Error('用户名或密码错误');
  }
}

export async function register(userData) {
  try {
    return await request('/auth/register', { method: 'POST', body: JSON.stringify(userData) });
  } catch {
    await delay();
    return { user: { ...mockUser, username: userData.username, email: userData.email }, access_token: 'mock_token_new', token_type: 'bearer' };
  }
}

// ===== 数据看板 =====
export async function getDashboard() {
  try { return await request('/dashboard'); }
  catch { await delay(); return mockDashboard; }
}

// ===== 简历管理 =====
export async function getResumes() {
  try { return await request('/resumes'); }
  catch { await delay(); return mockResumes; }
}

export async function uploadResume(formData) {
  try {
    return await request('/resumes/upload', { method: 'POST', body: formData, headers: {} });
  } catch {
    await delay(300);
    const filename = formData.get('file')?.name || '新简历.pdf';
    const nextVersion = mockResumes.length > 0
      ? Math.max(...mockResumes.map(r => r.version || 0)) + 1
      : 1;
    const newResume = {
      id: 'r' + Date.now(),
      filename: filename,
      original_name: filename,
      version: nextVersion,
      status: 'pending',
      parsed_content: null,
      review_comment: null,
      created_at: new Date().toISOString(),
    };
    mockResumes.unshift(newResume);
    saveResumes(mockResumes);
    return newResume;
  }
}

export async function deleteResume(id) {
  try { return await request(`/resumes/${id}`, { method: 'DELETE' }); }
  catch {
    await delay();
    mockResumes = mockResumes.filter(r => r.id !== id);
    saveResumes(mockResumes);
    return { success: true };
  }
}

export async function getResumeDetail(id) {
  try { return await request(`/resumes/${id}`); }
  catch { await delay(); return mockResumes.find(r => r.id === id) || mockResumes[0]; }
}

// ===== 岗位管理 =====
export async function getJobs(params = {}) {
  try {
    const qs = new URLSearchParams(params).toString();
    return await request(`/jobs${qs ? '?' + qs : ''}`);
  } catch {
    await delay();
    let result = [...mockJobs];
    if (params.status) result = result.filter(j => j.status === params.status);
    if (params.keyword) result = result.filter(j => j.title.includes(params.keyword) || j.company.includes(params.keyword));
    if (params.city) result = result.filter(j => j.city === params.city);
    return result;
  }
}

export async function getJobDetail(id) {
  try { return await request(`/jobs/${id}`); }
  catch { await delay(); return mockJobs.find(j => j.id === id); }
}

export async function createJob(data) {
  try { return await request('/jobs', { method: 'POST', body: JSON.stringify(data) }); }
  catch {
    await delay();
    const newJob = {
      id: 'j' + Date.now(),
      ...data,
      salary_min: Number(data.salary_min) || 0,
      salary_max: Number(data.salary_max) || 0,
      status: 'pending',
      created_at: new Date().toISOString().split('T')[0],
    };
    mockJobs.unshift(newJob);
    saveJobs(mockJobs);
    return newJob;
  }
}

export async function updateJobStatus(id, status) {
  try { return await request(`/jobs/${id}/status`, { method: 'PUT', body: JSON.stringify({ status }) }); }
  catch {
    await delay();
    const job = mockJobs.find(j => j.id === id);
    if (job) { job.status = status; saveJobs(mockJobs); }
    return { success: true };
  }
}

export async function batchImportJobs(data) {
  try { return await request('/jobs/batch-import', { method: 'POST', body: JSON.stringify(data) }); }
  catch {
    await delay(300);
    const imported = (data.jobs || []).map((j, i) => ({
      id: 'j' + (Date.now() + i),
      title: j.title || '',
      company: j.company || '',
      city: j.city || '北京',
      salary_min: 0,
      salary_max: 0,
      experience: j.experience || '不限',
      education: '本科',
      skills_required: j.skills_required || [],
      description: j.description || '',
      status: j.status || 'pending',
      created_at: new Date().toISOString().split('T')[0],
    }));
    mockJobs.unshift(...imported);
    saveJobs(mockJobs);
    return { success: true, count: imported.length, message: `成功导入${imported.length}个岗位` };
  }
}

// ===== 岗位匹配 =====
export async function getMatches(resumeId) {
  try { return await request(`/matches?resume_id=${resumeId}`); }
  catch { await delay(500); return mockMatches; }
}

export async function runMatching(resumeId) {
  try { return await request('/matches/run', { method: 'POST', body: JSON.stringify({ resume_id: resumeId }) }); }
  catch { await delay(1000); return { success: true, matches: mockMatches }; }
}

// ===== 模拟面试 =====

// 面试对话轮次追踪（Mock 模式下的状态）
let _interviewTurns = {};
let _interviewStages = {};

// 多阶段面试题库
const interviewStageQuestions = {
  intro: [
    '请简单介绍一下你自己，包括你的技术背景和主要技术栈。',
    '能说说你为什么选择前端开发这个方向吗？你认为一个优秀的前端工程师需要具备哪些能力？',
  ],
  technical_react: [
    '很好！我们来聊聊 React。能详细说说 React 的虚拟 DOM 机制和 Diff 算法吗？它在实际项目中带来了哪些性能优势？另外，你用过 React Hooks 吗，和 Class 组件相比有什么优缺点？',
    '你对 React 的状态管理方案了解多少？比如 Redux、Zustand、Jotai 等，它们各自的适用场景是什么？你项目中主要用哪一种，为什么选它？',
    'React 18 引入了 Concurrent Mode 和 Suspense，你了解这些新特性吗？结合实际场景说说它们解决了什么问题。',
  ],
  technical_ts: [
    '我看到你简历中提到了 TypeScript。能详细说说 TypeScript 的类型系统吗？比如泛型、联合类型、交叉类型、条件类型，你在项目中分别用它们解决过什么问题？',
    'TypeScript 的类型推导和类型守卫你是怎么理解的？能举例说说 `is` 关键字和 `satisfies` 关键字的区别吗？',
  ],
  project: [
    '请详细介绍一个你最有成就感的项目。你在这个项目中担任什么角色？遇到了哪些技术难题，是如何解决的？如果让你重新做一次，你会改进哪些地方？',
    '你简历中的项目看起来很有意思。能从头到尾说说你的开发流程吗？从需求分析、技术选型、到代码实现、测试、部署，每个环节你是如何把控质量的？',
  ],
  architecture: [
    '接下来聊聊系统设计。假设你要设计一个类似 Notion 的在线协作文档系统，富文本编辑器支持多人实时协作，你会怎么设计整体架构？请从数据模型、冲突解决、性能优化几个方面来谈谈。',
    '如果让你设计一个支持千万级用户的即时通讯系统，你会怎么做？请考虑消息可靠性、实时性、水平扩展、数据存储这几个核心问题。',
  ],
  css_perf: [
    '说说你对 CSS 布局的理解。Flexbox 和 Grid 分别适用于什么场景？你在项目中做过哪些复杂的布局？另外，CSS 动画的性能优化你了解多少，`will-change` 和 `transform` 是怎么配合使用的？',
    '前端性能优化是一个老生常谈的话题。你做过哪些性能优化？比如首屏加载优化、打包体积优化、图片懒加载、虚拟列表等，具体是怎么实施的，效果如何？',
  ],
  behavioral: [
    '说说你最近遇到的一个有挑战性的技术问题，你是怎么分析和解决的？在这个过程中你学到了什么？',
    '在团队协作中，当你和同事对技术方案有分歧的时候，你通常怎么处理？能举个具体的例子吗？',
    '你未来的职业规划是怎样的？接下来1-2年你希望在技术深度和广度上分别达到什么水平？',
  ],
  closing: [
    '感谢你的分享，面试到这里基本结束了。最后你有什么想问我的吗？比如关于团队、技术栈、发展方向等方面的。',
  ],
};

const interviewFeedbacks = {
  intro: ['自我介绍很清晰，对技术的热情能感受到。', '你的背景介绍让我对你的经历有了初步了解。'],
  technical_react: ['对 React 的理解比较到位，能结合实践说明。', 'React 基础不错，不过有些细节可以再深入一些。', '技术思路清晰，能理论结合实际。'],
  technical_ts: ['TypeScript 掌握得不错，类型系统理解深入。', '有实际使用经验，能在项目中发挥 TS 的优势。'],
  project: ['项目经验是你的一大亮点，描述的很有条理。', '能看出你在项目中有过深入思考和实践。'],
  architecture: ['架构思维还需要加强，但方向是对的。', '对系统设计有一定理解，继续保持学习。'],
  css_perf: ['性能优化经验不错，有实际落地的成果。', '对这些概念有基本认识，建议深入学习。'],
  behavioral: ['沟通表达很清晰，团队协作意识好。', '职业规划思路比较清楚，有目标感。'],
};

function getInterviewResponse(interviewId, userMessage) {
  if (!_interviewTurns[interviewId]) {
    _interviewTurns[interviewId] = 0;
    _interviewStages[interviewId] = ['intro', 'technical_react', 'technical_ts', 'project', 'architecture', 'css_perf', 'behavioral', 'closing'];
  }

  const turn = _interviewTurns[interviewId];
  const stages = _interviewStages[interviewId];
  const stageIdx = Math.min(turn, stages.length - 1);
  const stage = stages[stageIdx];
  const questions = interviewStageQuestions[stage];

  _interviewTurns[interviewId]++;

  // 选取当前阶段的提问
  const question = questions[turn >= questions.length ? questions.length - 1 : turn % questions.length];
  // 选取对应反馈
  const feedbacks = interviewFeedbacks[stage] || ['谢谢你的回答。'];
  const feedback = feedbacks[turn % feedbacks.length];

  // 组合成完整的面试官回复
  let response = '';

  if (turn === 0) {
    // 第一轮：开场白 + 第一个问题
    response = '你好！欢迎参加本次 AI 模拟面试。我是你今天的面试官。接下来我会从技术基础、项目经验、系统设计、综合素质等几个维度来考察你。准备好了吗？' + '\n\n' + '那么，' + question;
  } else if (stage === 'closing') {
    response = feedback + '\n\n' + question;
  } else {
    response = feedback + '\n\n' + '接下来，' + question;
  }

  return { role: 'interviewer', content: response, timestamp: new Date().toISOString() };
}

export function resetInterviewState(id) {
  delete _interviewTurns[id];
  delete _interviewStages[id];
}

export async function startInterview(jobId, mode = 'mock') {
  try {
    return await request('/interviews/start', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, mode }),
    });
  } catch {
    await delay();
    const id = 'i' + Date.now();
    resetInterviewState(id);
    return { id, status: 'started', messages: mockMessages };
  }
}

export async function sendMessage(interviewId, message) {
  try {
    const result = await request(`/interviews/${interviewId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
    return result;
  } catch {
    await delay(600);
    return getInterviewResponse(interviewId, message);
  }
}

export async function endInterview(interviewId) {
  try { return await request(`/interviews/${interviewId}/end`, { method: 'POST' }); }
  catch { await delay(800); return { success: true, score: 85, feedback: { overall: '整体表现良好', strengths: ['技术基础好', '表达清晰'], weaknesses: ['系统设计需加强'] } }; }
}

export async function getInterviewHistory() {
  try { return await request('/interviews/history'); }
  catch { await delay(); return mockInterviews; }
}

export async function getInterviewReport(id) {
  try { return await request(`/interviews/${id}/report`); }
  catch { await delay(); return mockInterviews.find(i => i.id === id) || mockInterviews[0]; }
}

// ===== 统计分析 =====
export async function getCityDistribution() {
  try { return await request('/stats/city-distribution'); }
  catch { await delay(); return mockDashboard.job_city_distribution; }
}
