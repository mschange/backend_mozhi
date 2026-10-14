# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
import os

os.environ.setdefault("APP_ENV_FILE", "/dev/null")
# 测试密钥只是占位符，不能用于任何真实环境。
os.environ.setdefault("JWT_SECRET", "<test-jwt-secret-placeholder-at-least-32-bytes>")
os.environ.setdefault("DEEPSEEK_API_KEY", "<test-api-key>")
os.environ.setdefault("DEBUG_MODE", "false")
