import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.vector_store import upsert_job_embedding

jobs = [
    {
        "id": "job-001",
        "title": "高级Python开发工程师",
        "company": "字节跳动",
        "description": "负责抖音电商后台业务系统的设计与开发，优化系统性能",
        "requirements": "精通Python/Django，5年以上后端开发经验，熟悉Redis和MySQL",
        "source_link": "https://www.liepin.com/job/123456",
        "skills": ["Python", "Django", "Redis", "MySQL"]
    },
    {
        "id": "job-002",
        "title": "前端架构师",
        "company": "腾讯",
        "description": "负责微信小程序核心框架设计与性能优化",
        "requirements": "精通Vue3/React，有大型项目架构经验",
        "source_link": "https://www.liepin.com/job/789012",
        "skills": ["Vue3", "React", "TypeScript", "小程序"]
    },
    {
        "id": "job-004",
        "title": "AI算法工程师",
        "company": "商汤科技",
        "description": "负责计算机视觉模型训练与部署",
        "requirements": "熟悉PyTorch，有Transformer模型调优经验",
        "source_link": "https://www.liepin.com/job/345678",
        "skills": ["PyTorch", "Transformer", "计算机视觉"]
    }
]

for job in jobs:
    try:
        result = upsert_job_embedding(job)
        print(f"✅ {result}")
    except Exception as e:
        print(f"❌ 导入失败: {e}")