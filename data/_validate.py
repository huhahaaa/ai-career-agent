import json
from collections import Counter

with open(r'C:\Users\28017\Desktop\ai-career-agent-main\data\interview_question_bank.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

questions = data['questions']
print(f'总题数: {len(questions)}')

modes = Counter(q['mode'] for q in questions)
print(f'模式分布: {dict(modes)}')

diffs = Counter(q['difficulty'] for q in questions)
print(f'难度分布: {dict(diffs)}')

for q in questions:
    pts = q.get('evaluation_points', [])
    if len(pts) < 3:
        print(f'WARNING: {q["id"]} 评分要点不足 ({len(pts)}个)')

has_pos = sum(1 for q in questions if '{% position %}' in q['question'])
print(f'含position占位符: {has_pos}题')

print('JSON校验: OK')
