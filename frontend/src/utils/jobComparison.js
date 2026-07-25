const SOURCE_MISSING_VALUES = new Set(['未标注', '页面未标注']);

export function formatDisclosure(value) {
  const raw = String(value || '').trim();
  if (!raw) return '未填写';
  return SOURCE_MISSING_VALUES.has(raw) ? '原页面未公开' : raw;
}

function parseSalaryRange(value) {
  const raw = String(value || '').trim();
  const normalizedRaw = raw.toLowerCase();
  const label = formatDisclosure(raw);
  if (!raw || SOURCE_MISSING_VALUES.has(raw)) {
    return { min: 0, max: 0, label, comparable: false };
  }
  if (/\/?\s*(hour|hr)|小时|时薪/.test(normalizedRaw)) {
    return { min: 0, max: 0, label, comparable: false };
  }

  const numbers = Array.from(raw.matchAll(/\d+(?:\.\d+)?/g)).map(match => Number(match[0]));
  if (!numbers.length) return { min: 0, max: 0, label, comparable: false };

  const hasK = /k/i.test(raw);
  const hasMonth = /month|月/.test(normalizedRaw);
  const hasYear = /year|yr|年/.test(normalizedRaw);
  const hasWanYear = /万/.test(raw) && hasYear;
  let monthlyKValues = [];

  if (hasWanYear) {
    monthlyKValues = numbers.map(item => item * 10 / 12);
  } else if (hasK && hasYear && !hasMonth) {
    monthlyKValues = numbers.map(item => item / 12);
  } else if (hasK) {
    monthlyKValues = numbers;
  } else if (hasMonth) {
    monthlyKValues = numbers.map(item => item / 1000);
  } else if (hasYear) {
    monthlyKValues = numbers.map(item => item / 12 / 1000);
  } else {
    return { min: 0, max: 0, label, comparable: false };
  }

  const min = Number(Math.min(...monthlyKValues).toFixed(2));
  const max = Number(Math.max(...monthlyKValues).toFixed(2));
  return { min, max, label: raw, comparable: true };
}

export function formatScore(score) {
  return typeof score === 'number' ? `${Math.round(score)} 分` : '未运行匹配';
}

export function scoreColor(score) {
  if (typeof score !== 'number') return 'var(--text-muted)';
  return score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--error)';
}

function normalizeMatchDetails(match = {}) {
  const details = match.details || {};
  return {
    reason: details.reason || match.reason || '',
    source_link: details.source_link || match.source_link || '',
    matched_skills: details.matched_skills || match.matched_skills || [],
    missing_skills: details.missing_skills || match.missing_skills || [],
    gap_analysis: details.gap_analysis || match.gap_analysis || '',
    suggestion: details.suggestion || match.suggestion || '',
  };
}

export function normalizeJob(job, index, match = null) {
  const salary = parseSalaryRange(job.salary_range);
  const score = typeof match?.total_score === 'number'
    ? match.total_score
    : typeof match?.score === 'number'
      ? match.score
      : null;
  const details = normalizeMatchDetails(match || {});

  return {
    id: job.id ?? match?.job_id ?? `job-${index}`,
    seriesKey: `job_${job.id ?? match?.job_id ?? index}`,
    title: job.title || match?.job_title || '未命名岗位',
    company: job.company || match?.company || '未知公司',
    city: job.location || job.city || '未填写',
    salary_min: salary.min,
    salary_max: salary.max,
    salary_label: salary.label,
    salary_comparable: salary.comparable,
    experience: formatDisclosure(job.experience),
    education: formatDisclosure(job.education),
    skills_required: job.skills || job.skills_required || [],
    source_link: job.source_link || details.source_link || '',
    match_score: score,
    reason: details.reason,
    matched_skills: details.matched_skills,
    missing_skills: details.missing_skills,
    gap_analysis: details.gap_analysis,
    suggestion: details.suggestion,
    created_at: match?.created_at || '',
    from_history: Boolean(match),
  };
}

export function normalizeHistoryRecord(record, jobs, index) {
  const job = jobs.find(item => String(item.id) === String(record.job_id)) || {};
  return normalizeJob(
    {
      ...job,
      id: record.job_id,
      title: job.title || record.job_title,
      company: job.company || record.company,
    },
    index,
    record,
  );
}

export function normalizeImmediateMatch(match, index, jobs = []) {
  const job = jobs.find(item => String(item.id) === String(match.job_id)) || {};
  return normalizeJob(
    {
      ...job,
      id: match.job_id,
      title: job.title || match.title,
      company: job.company || match.company,
      source_link: job.source_link || match.source_link,
      skills: job.skills || match.skills || [],
    },
    index,
    {
      ...match,
      total_score: typeof match.score === 'number' ? Math.round(match.score) : null,
      details: normalizeMatchDetails(match),
    },
  );
}

export function appendApprovedJobOptions(rows, approvedJobs) {
  const existingIds = new Set(rows.map(row => String(row.id)));
  const options = [...rows];

  (approvedJobs || []).forEach(job => {
    if (existingIds.has(String(job.id))) return;
    existingIds.add(String(job.id));
    options.push(normalizeJob(job, options.length));
  });

  return options;
}

export function defaultSelection(rows, preferredSelectedCount = 0) {
  if (preferredSelectedCount > 0) {
    return rows.map((_, index) => index < Math.min(preferredSelectedCount, 3));
  }
  return rows.map((_, index) => index < 3);
}
