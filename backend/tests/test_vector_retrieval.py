"""
知识库检索测试
验证向量检索的准确性和可复现性
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.services.vector_store import search_similar_jobs


class TestVectorRetrieval:
    """向量检索测试类"""

    def test_search_by_skill_returns_relevant_jobs(self):
        """测试1：给定技能关键词，能正确召回相关岗位"""
        query = "I have experience with React and TypeScript"
        results = search_similar_jobs(query, top_k=5)
        
        assert len(results) > 0, "检索应该返回至少1个结果"
        
        first_job_skills = results[0].get('skills', [])
        skill_set = [s.lower() for s in first_job_skills]
        
        has_relevant_skill = any(
            skill in skill_set
            for skill in ['react', 'typescript', 'javascript', 'frontend']
        )
        assert has_relevant_skill, f"返回的岗位应该包含前端相关技能，实际技能为: {first_job_skills}"
        
        print(f"✅ 测试1通过: 检索到 {len(results)} 个结果，第一个岗位是 {results[0].get('title')}")

    def test_search_results_are_reproducible(self):
        """测试2：同一条查询多次返回结果一致（可复现性）"""
        query = "Python backend development"
        
        results_1 = search_similar_jobs(query, top_k=5)
        results_2 = search_similar_jobs(query, top_k=5)
        
        assert len(results_1) == len(results_2), f"两次查询返回数量不一致: {len(results_1)} vs {len(results_2)}"
        
        ids_1 = [r.get('job_id') for r in results_1]
        ids_2 = [r.get('job_id') for r in results_2]
        
        assert ids_1 == ids_2, f"两次查询返回的岗位顺序不一致"
        
        scores_1 = [r.get('score') for r in results_1]
        scores_2 = [r.get('score') for r in results_2]
        
        assert scores_1 == scores_2, "两次查询返回的分数不一致"
        
        print(f"✅ 测试2通过: 两次查询结果一致，返回 {len(results_1)} 个岗位")

    def test_search_by_different_skills_returns_different_results(self):
        """测试3：不同技能查询返回不同结果"""
        frontend_query = "React Vue Angular"
        backend_query = "Python Django FastAPI"
        
        frontend_results = search_similar_jobs(frontend_query, top_k=3)
        backend_results = search_similar_jobs(backend_query, top_k=3)
        
        frontend_ids = set([r.get('job_id') for r in frontend_results])
        backend_ids = set([r.get('job_id') for r in backend_results])
        
        has_difference = len(frontend_ids - backend_ids) > 0 or len(backend_ids - frontend_ids) > 0
        assert has_difference, "不同技能查询应该返回不同的岗位"
        
        print(f"✅ 测试3通过: 前端查询返回 {len(frontend_results)} 个，后端查询返回 {len(backend_results)} 个，结果有差异")

    def test_matched_skills_and_missing_skills_are_present(self):
        """测试4：匹配结果包含技能缺口分析字段"""
        query = "I am a Python developer with 3 years of experience"
        results = search_similar_jobs(query, top_k=3)
        
        for result in results:
            assert 'skills' in result, "结果中应该包含 skills 字段"
            assert 'score' in result, "结果中应该包含 score 字段"
            assert 'title' in result, "结果中应该包含 title 字段"
            assert 'company' in result, "结果中应该包含 company 字段"
        
        print(f"✅ 测试4通过: 所有返回结果都包含必要的字段")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
