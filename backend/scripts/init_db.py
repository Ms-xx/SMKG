"""
数据库初始化脚本
创建数据库表并插入初始数据
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

from sqlalchemy import create_engine, text

import app.models  # noqa: F401  # 导入以注册全部模型到 Base.metadata（供 create_all 建表）
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.base import Base


def init_database():
    """初始化数据库"""
    print("正在初始化数据库...")

    # 创建同步引擎
    sync_url = settings.DATABASE_URL.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url, echo=True)

    # 创建所有表
    print("创建数据库表...")
    Base.metadata.create_all(bind=engine)

    # 插入初始数据
    with engine.connect() as conn:
        # 创建默认角色（忽略已存在的）
        print("创建默认角色...")
        roles_data = [
            ("admin", "系统管理员", json.dumps(["all"])),
            (
                "reviewer",
                "审核员",
                json.dumps(
                    [
                        "document:read",
                        "document:write",
                        "annotation:read",
                        "annotation:review",
                        "task:read",
                        "task:write",
                    ]
                ),
            ),
            (
                "annotator",
                "标注员",
                json.dumps(["document:read", "annotation:read", "annotation:write", "task:read"]),
            ),
            ("user", "普通用户", json.dumps(["document:read", "task:read"])),
        ]

        for name, description, permissions in roles_data:
            conn.execute(
                text(
                    "INSERT IGNORE INTO roles (name, description, permissions) "
                    "VALUES (:name, :description, :permissions)"
                ),
                {"name": name, "description": description, "permissions": permissions},
            )

        # 创建管理员用户（忽略已存在的）
        print("创建管理员用户...")
        admin_user = {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": get_password_hash("admin123"),
            "full_name": "系统管理员",
            "role": "admin",
            "is_active": 1,
        }

        conn.execute(
            text(
                "INSERT IGNORE INTO users (username, email, password_hash, full_name, role, is_active) "
                "VALUES (:username, :email, :password_hash, :full_name, :role, :is_active)"
            ),
            admin_user,
        )

        # 创建系统配置（忽略已存在的）
        print("创建系统配置...")
        configs = [
            ("max_upload_size", json.dumps({"value": 100, "unit": "MB"}), "最大上传文件大小"),
            ("supported_formats", json.dumps({"value": ["pdf"]}), "支持的文件格式"),
            ("active_learning_threshold", json.dumps({"value": 0.7}), "主动学习置信度阈值"),
        ]

        for key, value, description in configs:
            conn.execute(
                text(
                    "INSERT IGNORE INTO system_configs (`key`, value, description) "
                    "VALUES (:key, :value, :description)"
                ),
                {"key": key, "value": value, "description": description},
            )

        conn.commit()

    print("数据库初始化完成!")
    print("\n默认管理员账号:")
    print("用户名: admin")
    print("密码: admin123")
    print("\n请及时修改管理员密码!")


def drop_all_tables():
    """删除所有表(谨慎使用)"""
    print("警告: 正在删除所有数据库表...")
    sync_url = settings.DATABASE_URL.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url, echo=True)
    Base.metadata.drop_all(bind=engine)
    print("所有表已删除")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除所有表后再创建",
    )

    args = parser.parse_args()

    if args.drop:
        drop_all_tables()

    init_database()
