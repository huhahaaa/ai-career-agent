import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.vector_store import collection, model

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def index_skill_dictionary():
    data = load_json(DATA_DIR / "skill_dictionary.json")
    rules = data.get("normalization_rules", {})
    count = 0
    for skill, synonyms in rules.items():
        text = f"技能: {skill}\n同义词: {', '.join(synonyms)}"
        embedding = model.encode(text).tolist()
        collection.upsert(
            ids=[f"skill_{skill}"],
            embeddings=[embedding],
            metadatas=[{
                "type": "skill_definition",
                "skill": skill,
                "synonyms": ", ".join(synonyms),
                "source": "skill_dictionary.json"
            }],
            documents=[text]
        )
        count += 1
        print(f"  ✅ 技能: {skill} ({len(synonyms)} 个同义词)")
    return count


def index_role_profiles():
    profiles = load_json(DATA_DIR / "role_profiles.json")
    count = 0
    for profile in profiles:
        role = profile.get("role", "未知岗位")
        must_have = ", ".join(profile.get("must_have", []))
        preferred = ", ".join(profile.get("preferred", []))
        signals = ", ".join(profile.get("evidence_signals", []))
        text = f"岗位角色: {role}\n必备技能: {must_have}\n加分技能: {preferred}\n评估信号: {signals}"
        embedding = model.encode(text).tolist()
        collection.upsert(
            ids=[f"role_{role}"],
            embeddings=[embedding],
            metadatas=[{
                "type": "role_profile",
                "role": role,
                "must_have": must_have,
                "preferred": preferred,
                "source": "role_profiles.json"
            }],
            documents=[text]
        )
        count += 1
        print(f"  ✅ 岗位画像: {role}")
    return count


def verify_index():
    print("\n3. 验证知识库检索")
    test_queries = ["Python", "后端开发", "机器学习"]
    for query in test_queries:
        results = collection.query(
            query_embeddings=[model.encode(query).tolist()],
            n_results=3,
            include=["metadatas", "documents", "distances"]
        )
        if results['ids'] and len(results['ids'][0]) > 0:
            print(f"\n   查询: '{query}'")
            for i in range(len(results['ids'][0])):
                meta = results['metadatas'][0][i]
                score = round(1 - results['distances'][0][i], 3)
                print(f"     [{score}] {meta.get('type')}: {meta.get('skill', meta.get('role'))}")
        else:
            print(f"\n   查询: '{query}' - 未找到结果")


def main():
    print("📚 开始导入知识库素材...")
    print("\n1. 导入技能词典 (skill_dictionary.json)")
    skill_count = index_skill_dictionary()
    print(f"   ✅ 共导入 {skill_count} 个技能")

    print("\n2. 导入岗位画像 (role_profiles.json)")
    role_count = index_role_profiles()
    print(f"   ✅ 共导入 {role_count} 个岗位画像")

    verify_index()

    print(f"\n📊 总计导入 {skill_count + role_count} 条知识库记录")


if __name__ == "__main__":
    main()
