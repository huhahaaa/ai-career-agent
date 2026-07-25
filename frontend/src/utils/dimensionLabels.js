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

export function getDimensionLabel(key) {
  return DIMENSION_LABELS[key] || key;
}

export function mapDimensionScores(dimensionScores = {}) {
  return Object.entries(dimensionScores).map(([name, score]) => ({
    name: getDimensionLabel(name),
    originalName: name,
    score: typeof score === 'number' ? score : 0,
    maxScore: 100,
  }));
}
