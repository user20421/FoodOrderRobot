import os
import sys
import redis
import pymongo
import pymysql
from pathlib import Path

# 修复Windows控制台中文输出乱码问题
if sys.platform == "win32":
    os.system("chcp 65001 >nul")

# 尝试加载 backend/.env 配置
env_path = Path(__file__).parent / "backend" / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _parse_mysql_url(url: str) -> dict:
    """解析 mysql+aiomysql://user:pass@host:port/db 格式的 URL"""
    try:
        url = url.replace("mysql+aiomysql://", "").replace("mysql+pymysql://", "")
        creds, rest = url.split("@", 1)
        user, password = creds.split(":", 1)
        host_port, db = rest.split("/", 1)
        if ":" in host_port:
            host, port = host_port.split(":", 1)
            port = int(port)
        else:
            host, port = host_port, 3306
        return {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": db,
        }
    except Exception:
        return {}


# 优先从 DATABASE_URL / MONGODB_URL / REDIS_URL 读取，否则使用默认值
db_url = os.getenv("DATABASE_URL", "mysql+aiomysql://root:123456@localhost:3306/shuxiangge_bot")
_parsed = _parse_mysql_url(db_url)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_DB = os.getenv("MONGODB_URL", "mongodb://localhost:27017/shuxiangge_bot").rsplit("/", 1)[-1] or "shuxiangge_bot"

MYSQL_HOST = os.getenv("MYSQL_HOST", _parsed.get("host", "localhost"))
MYSQL_PORT = int(os.getenv("MYSQL_PORT", str(_parsed.get("port", 3306))))
MYSQL_USER = os.getenv("MYSQL_USER", _parsed.get("user", "root"))
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", _parsed.get("password", "123456"))
MYSQL_DB = os.getenv("MYSQL_DB", _parsed.get("database", "shuxiangge_bot"))


def test_redis():
    """测试 Redis 连接与基本操作"""
    print("\n[Redis 测试开始]")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

        if r.ping():
            print("[OK] Redis 连接成功")
        else:
            print("[FAIL] Redis ping 失败")
            return

        r.set("test_key", "hello redis")
        value = r.get("test_key")
        print(f"[OK] 字符串读写: GET test_key = {value}")

        r.set("temp_key", "expires in 10s", ex=10)
        ttl = r.ttl("temp_key")
        print(f"[OK] 过期键: TTL temp_key = {ttl} 秒")

        r.lpush("test_list", "item1", "item2", "item3")
        list_items = r.lrange("test_list", 0, -1)
        print(f"[OK] 列表操作: LRANGE test_list = {list_items}")

        r.delete("test_key", "temp_key", "test_list")
        print("[OK] Redis 测试数据已清理")

    except redis.ConnectionError as e:
        print(f"[FAIL] Redis 连接异常: {e}")
    except Exception as e:
        print(f"[FAIL] Redis 发生错误: {e}")


def test_mongodb():
    """测试 MongoDB 连接与基本操作"""
    print("\n[MongoDB 测试开始]")
    try:
        client = pymongo.MongoClient(host=MONGO_HOST, port=MONGO_PORT, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        print("[OK] MongoDB 连接成功")

        db = client[MONGO_DB]
        collection = db["test_collection"]

        # 先清理可能存在的测试数据
        collection.delete_many({"source": "test-db"})

        # 插入测试文档
        doc = {"source": "test-db", "message": "hello mongodb", "count": 1}
        insert_result = collection.insert_one(doc)
        print(f"[OK] 插入文档: _id = {insert_result.inserted_id}")

        # 查询文档
        found = collection.find_one({"source": "test-db"})
        print(f"[OK] 查询文档: {found}")

        # 删除测试数据
        collection.delete_many({"source": "test-db"})
        print("[OK] MongoDB 测试数据已清理")

        client.close()

    except pymongo.errors.ServerSelectionTimeoutError as e:
        print(f"[FAIL] MongoDB 连接异常: {e}")
    except Exception as e:
        print(f"[FAIL] MongoDB 发生错误: {e}")


def test_mysql():
    """测试 MySQL 连接与基本操作"""
    print("\n[MySQL 测试开始]")
    connection = None
    try:
        # 第一步：先连上 MySQL 服务器（不指定数据库）
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
        print("[OK] MySQL 服务器连接成功")

        with connection.cursor() as cursor:
            # 如果数据库不存在就创建它
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
            connection.commit()
            print(f"[OK] 数据库 {MYSQL_DB} 已就绪")

        connection.close()

        # 第二步：连接指定数据库，做增删改查测试
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )

        with connection.cursor() as cursor:
            # 创建测试表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    message VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()
            print("[OK] 测试表已创建")

            # 插入数据
            cursor.execute("INSERT INTO test_table (message) VALUES (%s)", ("hello mysql",))
            connection.commit()
            inserted_id = cursor.lastrowid
            print(f"[OK] 插入数据: id = {inserted_id}")

            # 查询数据
            cursor.execute("SELECT * FROM test_table WHERE id = %s", (inserted_id,))
            row = cursor.fetchone()
            print(f"[OK] 查询数据: {row}")

            # 删除测试表
            cursor.execute("DROP TABLE IF EXISTS test_table")
            connection.commit()
            print("[OK] MySQL 测试数据已清理")

    except pymysql.err.OperationalError as e:
        print(f"[FAIL] MySQL 连接异常: {e}")
    except Exception as e:
        print(f"[FAIL] MySQL 发生错误: {e}")
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    print("=" * 50)
    print("数据库服务连通性测试")
    print("=" * 50)

    test_redis()
    test_mongodb()
    test_mysql()

    print("\n" + "=" * 50)
    print("全部测试执行完毕")
    print("=" * 50)
