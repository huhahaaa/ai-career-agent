export const DIMENSION_LABELS = {
  content_relevance: '内容相关性',
  professional_accuracy: '专业准确度',
  clarity: '表达清晰度',
  star_completeness: 'STAR完整性',
  position_match: '岗位匹配度',
  depth: '回答深度',
  relevance: '内容相关性',
  structure: '结构组织',
  specificity: '具体程度',
  technical_depth: '技术深度',
  communication: '沟通表达',
  problem_solving: '问题解决',
  system_design: '系统设计',
  industry_knowledge: '行业理解',
};

const DIMENSION_MAX_SCORES = {
  content_relevance: 25,
  professional_accuracy: 25,
  clarity: 20,
  star_completeness: 20,
  position_match: 10,
};

export function getDimensionLabel(key) {
  return DIMENSION_LABELS[key] || key;
}

export function mapDimensionScores(dimensionScores = {}) {
  return Object.entries(dimensionScores).map(([name, score]) => ({
    name: getDimensionLabel(name),
    originalName: name,
    rawScore: typeof score === 'number' ? score : 0,
    score: normalizeDimensionScore(name, score),
    maxScore: 100,
  }));
}

function normalizeDimensionScore(name, score) {
  if (typeof score !== 'number') return 0;
  const maxScore = DIMENSION_MAX_SCORES[name] || 100;
  return Math.round(Math.min(100, Math.max(0, (score / maxScore) * 100)));
}
