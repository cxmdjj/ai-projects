"""数据库初始化脚本:建表 + 可选种子规则。

用法:
  python -m scripts.init_db           # 仅建表
  python -m scripts.init_db --seed    # 建表 + 灌入 12 条种子规则
"""
import argparse

from app import models  # noqa: F401  确保模型注册到 Base.metadata
from app.db import Base, engine


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化合同审批审查系统数据库")
    parser.add_argument("--seed", action="store_true", help="同时灌入种子规则")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    print("数据表创建完成:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")

    if args.seed:
        from scripts.seed_rules import seed_rules

        created, updated = seed_rules()
        print(f"种子规则灌入完成:新建 {created} 条,更新 {updated} 条")


if __name__ == "__main__":
    main()
