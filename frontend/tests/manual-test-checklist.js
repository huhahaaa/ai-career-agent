/**
 * 前端功能测试清单
 * 用于验证所有页面和功能是否正常工作
 *
 * 启动方式：
 * 1. 启动后端：cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
 * 2. 启动前端：cd frontend && npm run dev
 * 3. 访问 http://localhost:5173
 *
 * 使用演示账号：demo / demo123 进行测试
 */

const testScenarios = {
  // ===== 正常流程测试 =====
  normalFlow: {
    /** 1. 用户注册和登录 */
    auth: [
      {
        title: '用户注册',
        steps: ['访问 /register', '填写用户名、邮箱、密码', '点击注册按钮', '验证跳转到首页'],
        expected: '注册成功后跳转到数据看板首页，用户名显示在右上角'
      },
      {
        title: '用户登录',
        steps: ['访问 /login', '使用 demo/demo123 登录', '点击登录按钮'],
        expected: '登录成功后显示侧边栏和首页数据看板'
      },
      {
        title: '退出登录',
        steps: ['点击右上角退出按钮'],
        expected: '清除token，跳转到登录页'
      },
    ],

    /** 2. 首页数据看板 */
    dashboard: [
      {
        title: '统计卡片展示',
        steps: ['登录后访问首页 /'],
        expected: '显示4个统计卡片：简历数、岗位数、面试次数、平均分'
      },
      {
        title: '6张可视化图表',
        steps: ['查看首页图表区'],
        expected: [
          '个人技能分布图（横向柱状图）',
          '热门技能需求图（柱状图）',
          '能力差距雷达图（雷达图）',
          '多岗位匹配得分图（彩色柱状图）',
          '面试得分趋势图（折线图）',
          '岗位城市分布图（饼图）'
        ]
      },
      {
        title: '最近面试记录表格',
        steps: ['滚动到页面底部'],
        expected: '显示最近面试记录表格，包含公司、岗位、得分等列'
      },
    ],

    /** 3. 简历管理 */
    resume: [
      {
        title: '简历列表展示',
        steps: ['点击侧边栏"简历管理"或访问 /resume'],
        expected: '显示已上传简历列表，包含文件名、版本、状态等'
      },
      {
        title: '上传简历',
        steps: ['点击上传区域', '选择一个PDF/DOCX文件'],
        expected: '提示上传成功，列表自动刷新'
      },
      {
        title: '文件格式校验',
        steps: ['尝试上传一个 .txt 或 .jpg 文件'],
        expected: '提示"仅支持PDF/DOC/DOCX格式"'
      },
      {
        title: '删除简历',
        steps: ['点击某条简历的删除按钮', '确认删除'],
        expected: '提示删除成功，列表自动刷新'
      },
    ],

    /** 4. 简历审核结果 */
    resumeReview: [
      {
        title: '查看简历审核详情',
        steps: ['在简历列表点击已通过简历的"查看详情"', '或访问 /resume/review'],
        expected: '显示简历解析结果：基本信息、技能评估图、教育/工作/项目经历'
      },
    ],

    /** 5. 岗位管理 */
    jobs: [
      {
        title: '岗位列表展示',
        steps: ['点击"岗位管理"或访问 /jobs'],
        expected: '显示所有岗位列表表格'
      },
      {
        title: '新增岗位',
        steps: ['点击"+新增岗位"', '填写岗位信息表单', '点击保存'],
        expected: '提示创建成功，列表自动刷新'
      },
      {
        title: '批量导入',
        steps: ['点击"批量导入"', '在文本框中输入岗位数据', '点击确认导入'],
        expected: '提示导入成功，显示导入数量'
      },
    ],

    /** 6. 岗位审核 */
    jobReview: [
      {
        title: '待审核岗位列表',
        steps: ['点击"岗位审核"或访问 /jobs/review'],
        expected: '显示待审核岗位卡片列表'
      },
      {
        title: '通过审核',
        steps: ['点击"✅ 通过"按钮'],
        expected: '岗位状态变为已发布'
      },
      {
        title: '驳回',
        steps: ['点击"❌ 驳回"按钮'],
        expected: '岗位状态变为已驳回'
      },
    ],

    /** 7. 岗位匹配 */
    jobMatch: [
      {
        title: '岗位匹配搜索',
        steps: ['点击"岗位匹配"或访问 /jobs/match', '点击"开始匹配"'],
        expected: '显示所有岗位匹配结果卡片'
      },
      {
        title: '匹配结果展示',
        steps: ['查看匹配结果'],
        expected: '每张卡片显示：总体匹配分数、技能/经验/学历匹配度进度条、匹配和缺失技能标签'
      },
      {
        title: '搜索关键词过滤',
        steps: ['在搜索框输入"前端"', '按回车'],
        expected: '仅显示标题包含"前端"的匹配结果'
      },
    ],

    /** 8. 多岗位对比 */
    jobCompare: [
      {
        title: '对比页展示',
        steps: ['点击"多岗对比"或访问 /jobs/compare'],
        expected: '显示可选岗位标签、基本信息对比表、薪资/匹配度图表、技能雷达图'
      },
      {
        title: '切换对比岗位',
        steps: ['点击某个岗位标签切换选中状态'],
        expected: '对比表格和图表实时更新'
      },
    ],

    /** 9. 模拟面试 */
    interview: [
      {
        title: '开始面试',
        steps: ['点击"模拟面试"或访问 /interview'],
        expected: '显示聊天界面，AI面试官发送第一句开场白'
      },
      {
        title: '发送消息',
        steps: ['输入消息', '点击发送或按回车'],
        expected: '消息显示在聊天区，收到AI面试官回复'
      },
      {
        title: '结束面试',
        steps: ['点击"结束面试"按钮'],
        expected: '显示面试结果：得分圆形、总体评价、优势和待改进列表'
      },
    ],

    /** 10. 面试记录 */
    interviewHistory: [
      {
        title: '面试记录列表',
        steps: ['点击"面试记录"或访问 /interview/history'],
        expected: '显示统计卡片、面试趋势折线图、面试记录表格'
      },
      {
        title: '查看面试报告',
        steps: ['点击某条记录的"查看报告"'],
        expected: '弹出模态框展示详细面试报告'
      },
    ],
  },

  // ===== 失败场景测试 =====
  failureScenarios: [
    {
      title: '错误密码登录',
      steps: ['访问 /login', '输入 demo/wrongpassword', '点击登录'],
      expected: '显示红色错误提示"用户名或密码错误"'
    },
    {
      title: '空表单登录',
      steps: ['访问 /login', '不填写任何内容', '点击登录'],
      expected: '显示"请填写完整的用户名和密码"'
    },
    {
      title: '密码不一致注册',
      steps: ['访问 /register', '填写信息但两次密码不同'],
      expected: '显示"两次输入的密码不一致"'
    },
    {
      title: '访问不存在的页面',
      steps: ['访问 /nonexistent'],
      expected: '显示404错误页面'
    },
  ],

  // ===== 异常场景测试 =====
  exceptionScenarios: [
    {
      title: 'Agent异常页面',
      steps: ['访问 /error/agent'],
      expected: '显示Agent运行异常页面，包含可能原因和建议操作'
    },
    {
      title: '服务器错误页面',
      steps: ['访问 /error/500'],
      expected: '显示500服务器错误页面'
    },
    {
      title: '未登录访问受保护页面',
      steps: ['清除localStorage', '直接访问 /'],
      expected: '强制跳转到登录页'
    },
    {
      title: '后端服务不可用',
      steps: ['停止后端服务', '刷新页面'],
      expected: '前端使用Mock数据正常运行（离线模式）'
    },
  ],

  // ===== 兼容性测试 =====
  compatibility: [
    { item: 'Chrome 浏览器' },
    { item: 'Edge 浏览器' },
    { item: '1920x1080 分辨率' },
    { item: '1366x768 分辨率' },
    { item: '移动端响应式布局' },
  ],
};

export default testScenarios;

// 在控制台运行此文件查看测试清单：
// node scripts/run-tests.js
console.log('前端测试清单已就绪，共包含 ' +
  Object.keys(testScenarios).length + ' 个测试分类');
console.log('请参照 testScenarios 对象手动执行测试');
