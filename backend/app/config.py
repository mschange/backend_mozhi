"""从 backend/.env 读取配置并提供规范化后的运行时值。

当前项目刻意使用 override=True：受控配置文件覆盖宿主进程中的同名变量，
避免 LangChain 误用机器上残留的 OPENAI_API_KEY。apply_runtime_env() 则在
应用 lifespan 启动阶段把最终 DeepSeek 配置写回第三方库约定的环境变量。
"""

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# 由本文件的绝对路径定位 backend/，上传、日志和 Milvus Lite 不受 cwd 影响。
BACKEND_DIR = Path(__file__).resolve().parent.parent
# APP_ENV_FILE 要在 dotenv 加载前从宿主环境读取；相对值仍按当前 cwd 解释。
ENV_FILE = Path(os.getenv("APP_ENV_FILE", BACKEND_DIR / ".env"))
# 文件内同名配置覆盖宿主变量，确保本应用和直接读环境变量的依赖看到同一套 key。
load_dotenv(ENV_FILE, override=True)


def _str(key: str, default: str = "") -> str:
    """读取去除首尾空白的字符串；未设置或纯空白时使用默认值。"""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _int(key: str, default: int) -> int:
    """读取整数；非法字符串让导入失败，避免端口、容量等错误延迟到运行期。"""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _bool(key: str, default: bool = False) -> bool:
    """只把常见肯定值识别为 True，其余非空字符串均为 False。"""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# MySQL 是业务事实库；这些常量在模块导入时冻结，运行中修改 .env 不会热更新。
MYSQL_HOST = _str("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _int("MYSQL_PORT", 3306)
MYSQL_USER = _str("MYSQL_USER", "root")
MYSQL_PASSWORD = _str("MYSQL_PASSWORD", "root")
MYSQL_DATABASE = _str("MYSQL_DATABASE", "mo_zhi")

# PostgreSQL 只承载 LangGraph checkpoint，pool 大小由 psycopg_pool 使用。
POSTGRES_HOST = _str("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = _int("POSTGRES_PORT", 5432)
POSTGRES_USER = _str("POSTGRES_USER", "mozhi")
POSTGRES_PASSWORD = _str("POSTGRES_PASSWORD", "mozhi_pass")
POSTGRES_DATABASE = _str("POSTGRES_DATABASE", "mo_zhi_checkpoint")
POSTGRES_POOL_MIN_SIZE = _int("POSTGRES_POOL_MIN_SIZE", 1)
POSTGRES_POOL_MAX_SIZE = _int("POSTGRES_POOL_MAX_SIZE", 10)

# JWT secret 没有可用默认值；真实部署必须显式配置。
JWT_SECRET = _str("JWT_SECRET")
JWT_ALGORITHM = _str("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
REFRESH_TOKEN_EXPIRE_DAYS = _int("REFRESH_TOKEN_EXPIRE_DAYS", 7)

# 同一个维度用于知识切片与长期记忆 collection，不能与既有 schema 不一致。
MILVUS_DB_PATH = _str("MILVUS_DB_PATH", "./milvus.db")
EMBEDDING_DIM = _int("EMBEDDING_DIM", 1024)

# 兼容 OpenAI 命名，便于 LangChain/OpenAI-compatible 客户端读取。
OPENAI_API_KEY = _str("OPENAI_API_KEY")
OPENAI_BASE_URL = _str("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
CHAT_MODEL = _str("CHAT_MODEL", "deepseek-v4-flash")

# DeepSeek 专用值为空时回退到通用配置，而不是维护两套必填项。
DEEPSEEK_API_KEY = _str("DEEPSEEK_API_KEY") or OPENAI_API_KEY
DEEPSEEK_BASE_URL = _str("DEEPSEEK_BASE_URL") or OPENAI_BASE_URL
DEEPSEEK_MODEL = _str("DEEPSEEK_MODEL") or CHAT_MODEL

DASHSCOPE_API_KEY = _str("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = _str("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
EMBEDDING_MODEL = _str("EMBEDDING_MODEL", "text-embedding-v3")

# LangSmith 默认关闭；是否写入兼容环境变量由 core/logging.py 决定。
LANGSMITH_TRACING = _bool("LANGSMITH_TRACING", False)
LANGSMITH_ENDPOINT = _str("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = _str("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = _str("LANGSMITH_PROJECT", "mo-zhi")

TAVILY_API_KEY = _str("TAVILY_API_KEY")
MINERU_API_TOKEN = _str("MINERU_API_TOKEN")

UPLOAD_DIR = _str("UPLOAD_DIR", "./uploads")
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 250)
SHORT_TERM_MEMORY_N = _int("SHORT_TERM_MEMORY_N", 20)
DEBUG_MODE = _bool("DEBUG_MODE", True)

LOG_FILE = _str("LOG_FILE", "./logs/app.log")
LOG_LEVEL = _str("LOG_LEVEL", "ERROR")
LOG_MAX_BYTES = _int("LOG_MAX_BYTES", 10 * 1024 * 1024)
LOG_BACKUP_COUNT = _int("LOG_BACKUP_COUNT", 5)


def mysql_async_dsn() -> str:
    """构造 SQLAlchemy aiomysql DSN，并编码账号中具有 URL 语义的字符。"""
    user = quote_plus(MYSQL_USER)
    password = quote_plus(MYSQL_PASSWORD)
    return (
        f"mysql+aiomysql://{user}:{password}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )


def postgres_dsn() -> str:
    """构造 psycopg 使用的 PostgreSQL DSN；用户名和密码同样执行 URL 编码。"""
    user = quote_plus(POSTGRES_USER)
    password = quote_plus(POSTGRES_PASSWORD)
    return f"postgresql://{user}:{password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"


def deepseek_openai_base_url() -> str:
    """OpenAI SDK 要求 URL 以 /v1 结尾；同时消除配置末尾重复斜杠。"""
    url = DEEPSEEK_BASE_URL.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def upload_path() -> Path:
    """绝对路径原样返回；相对上传目录固定落在 backend/ 下。"""
    path = Path(UPLOAD_DIR)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path


def log_path() -> Path:
    """日志相对路径同样以 backend/ 为基准，避免从不同 cwd 启动时漂移。"""
    path = Path(LOG_FILE)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path


def milvus_path() -> str:
    """HTTP/HTTPS URI 保持网络地址；其他值作为 Lite 文件路径归一化。"""
    uri = MILVUS_DB_PATH
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    path = Path(uri)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return str(path)


def apply_runtime_env() -> None:
    """在应用启动时同步第三方库读取的环境变量并消除 Milvus 环境干扰。"""
    # LangChain/OpenAI-compatible 组件直接读取 OPENAI_*，这里统一映射最终 DeepSeek 值。
    os.environ["OPENAI_API_KEY"] = DEEPSEEK_API_KEY
    os.environ["OPENAI_BASE_URL"] = deepseek_openai_base_url()
    os.environ["DEEPSEEK_API_KEY"] = DEEPSEEK_API_KEY
    # 当前进程使用异步服务，不启用 gRPC fork 支持。
    os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
    # MilvusClient 必须使用显式 uri，不能被宿主机遗留的 MILVUS_URI 改写。
    os.environ.pop("MILVUS_URI", None)
