"""
岗位来源检查脚本
检查所有岗位的 source_link 是否可访问
标记状态：可用 / 待检查 / 来源缺失
"""

import json
import requests
from pathlib import Path
from datetime import datetime

# 项目路径
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


# 从数据库或 JSON 读取岗位数据
# 这里假设岗位数据在 data/jobs_approved.json 或类似位置
# 如果没有，我们直接从你之前导入的 Mock 数据来检查


def load_jobs_from_json():
    """从本地 JSON 文件读取岗位数据"""
    # 尝试多个可能的数据文件位置
    possible_files = [
        DATA_DIR / "jobs_approved.json",
        DATA_DIR / "jobs.json",
        BASE_DIR / "data" / "jobs_approved.json",
    ]

    for file_path in possible_files:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    # 如果找不到 JSON 文件，返回你之前导入的 3 条 Mock 数据
    print("⚠️ 没有找到岗位数据 JSON 文件，使用内置 Mock 数据")
    return [
        {
            "id": "job-001",
            "title": "高级Python开发工程师",
            "company": "字节跳动",
            "source_link": "https://www.liepin.com/job/123456",
            "source": "猎聘",
            "updated_at": "2026-07-24"
        },
        {
            "id": "job-002",
            "title": "前端架构师",
            "company": "腾讯",
            "source_link": "https://www.liepin.com/job/789012",
            "source": "猎聘",
            "updated_at": "2026-07-24"
        },
        {
            "id": "job-004",
            "title": "AI算法工程师",
            "company": "商汤科技",
            "source_link": "https://www.liepin.com/job/345678",
            "source": "猎聘",
            "updated_at": "2026-07-24"
        }
    ]


def check_source(source_link: str, timeout: int = 5):
    """检查单个来源链接是否可用"""
    if not source_link or source_link == "":
        return "来源缺失", "没有来源链接"

    try:
        response = requests.head(source_link, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return "可用", f"HTTP {response.status_code}"
        else:
            return "待检查", f"HTTP {response.status_code}"
    except requests.Timeout:
        return "待检查", "请求超时"
    except requests.ConnectionError:
        return "待检查", "连接失败"
    except Exception as e:
        return "待检查", str(e)[:30]


def main():
    print("=" * 60)
    print("📋 岗位来源检查报告")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    jobs = load_jobs_from_json()

    if not jobs:
        print("❌ 没有找到任何岗位数据")
        return

    print(f"\n共检查 {len(jobs)} 个岗位\n")

    # 统计
    stats = {
        "可用": 0,
        "待检查": 0,
        "来源缺失": 0,
    }

    results = []

    for job in jobs:
        source_link = job.get("source_link", "")
        source_name = job.get("source", "未知")
        title = job.get("title", "未知岗位")
        job_id = job.get("id", "未知ID")
        updated_at = job.get("updated_at", "未知")

        status, detail = check_source(source_link)
        stats[status] = stats.get(status, 0) + 1

        results.append({
            "id": job_id,
            "title": title,
            "source": source_name,
            "source_link": source_link,
            "status": status,
            "detail": detail,
            "updated_at": updated_at
        })

        status_emoji = {
            "可用": "✅",
            "待检查": "⚠️",
            "来源缺失": "❌"
        }.get(status, "❓")

        print(f"{status_emoji} [{status}] {title} ({job_id})")
        print(f"   来源: {source_name} → {source_link[:60]}...")
        print(f"   状态: {detail}")
        print(f"   更新时间: {updated_at}")
        print()

    # 输出汇总
    print("=" * 60)
    print("📊 汇总统计")
    print("=" * 60)
    print(f"✅ 可用: {stats.get('可用', 0)} 个")
    print(f"⚠️ 待检查: {stats.get('待检查', 0)} 个")
    print(f"❌ 来源缺失: {stats.get('来源缺失', 0)} 个")
    print(f"总计: {len(results)} 个")

    # 保存报告
    report_path = BASE_DIR / "outputs" / "source_check_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 岗位来源检查报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 汇总统计\n\n")
        f.write(f"| 状态 | 数量 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| ✅ 可用 | {stats.get('可用', 0)} |\n")
        f.write(f"| ⚠️ 待检查 | {stats.get('待检查', 0)} |\n")
        f.write(f"| ❌ 来源缺失 | {stats.get('来源缺失', 0)} |\n")
        f.write(f"| **总计** | **{len(results)}** |\n\n")
        f.write("## 详细结果\n\n")
        f.write("| 岗位ID | 标题 | 来源 | 状态 | 详情 |\n")
        f.write("|--------|------|------|------|------|\n")
        for r in results:
            f.write(f"| {r['id']} | {r['title']} | {r['source']} | {r['status']} | {r['detail']} |\n")

    print(f"\n📄 报告已保存: {report_path}")


if __name__ == "__main__":
    main()