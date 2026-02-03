import json
import argparse
from pathlib import Path
from collections import Counter, defaultdict
import statistics

def load_jsonl(path):
    with open(path, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f]

def main():
    parser = argparse.ArgumentParser(description="Calculate KG Statistics for Thesis")
    parser.add_argument("--triples", type=str, default="datasets/domain_main_kg/processed/merged/triples.jsonl")
    parser.add_argument("--output_dir", type=str, default="datasets/domain_main_kg/stats")
    args = parser.parse_args()

    triples_path = Path(args.triples)
    if not triples_path.exists():
        print(f"Error: {triples_path} not found.")
        return

    print(f"Loading triples from {triples_path}...")
    triples = load_jsonl(triples_path)
    
    # 1. 基础计数
    num_triples = len(triples)
    entities = set()
    relations = set()
    
    # 2. 度分布统计
    ent_degree = Counter()
    relation_count = Counter()

    valid_triples_count = 0

    for t in triples:
        # 兼容性处理：只取前三个元素 (s, p, o)
        if isinstance(t, list) and len(t) >= 3:
            s, p, o = t[0], t[1], t[2]
        elif isinstance(t, dict):
             # 适配常见字典键名
            s = t.get("head") or t.get("subject")
            p = t.get("relation") or t.get("predicate")
            o = t.get("tail") or t.get("object")
            if not (s and p and o): continue
        else:
            continue

        valid_triples_count += 1
        entities.add(s)
        entities.add(o)
        relations.add(p)
        
        ent_degree[s] += 1
        ent_degree[o] += 1
        relation_count[p] += 1

    num_entities = len(entities)
    num_relations = len(relations)
    
    # 3. 计算度统计量
    degrees = list(ent_degree.values())
    avg_degree = statistics.mean(degrees) if degrees else 0
    median_degree = statistics.median(degrees) if degrees else 0
    max_degree = max(degrees) if degrees else 0

    # 4. Top Relations
    top_relations = relation_count.most_common(10)

    # 5. 组装结果
    stats = {
        "overview": {
            "num_triples": valid_triples_count,
            "num_entities": num_entities,
            "num_relations": num_relations,
            "density": valid_triples_count / (num_entities * num_entities) if num_entities > 0 else 0
        },
        "degree_stats": {
            "avg_degree": avg_degree,
            "median_degree": median_degree,
            "max_degree": max_degree
        },
        "top_relations": top_relations
    }

    # 6. 落盘
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "kg_stats_overview.json"
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print("-" * 30)
    print("KG STATISTICS REPORT")
    print("-" * 30)
    print(f"Triples (Valid): {valid_triples_count}")
    print(f"Entities:        {num_entities}")
    print(f"Relations:       {num_relations}")
    print(f"Avg Degree:      {avg_degree:.2f}")
    print("-" * 30)
    print("Top 5 Relations:")
    for r, c in top_relations[:5]:
        print(f"  {r}: {c}")
    print("-" * 30)
    print(f"Saved detailed stats to: {out_path}")

if __name__ == "__main__":
    main()