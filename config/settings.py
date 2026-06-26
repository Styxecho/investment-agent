import os
from pathlib import Path
from dotenv import load_dotenv

# 1. 加载 .env 文件
# BASE_DIR 是当前文件的上两级目录 (即项目根目录)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self):
        # --- 基础信息 ---
        self.PROJECT_NAME = os.getenv("PROJECT_NAME", "investment_agent")
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

        # --- 路径定义 (核心逻辑) ---
        # 数据根目录
        self.DATA_EXTERNAL_DIR = BASE_DIR / "data_external"
        self.DATA_RUNTIME_DIR = BASE_DIR / "data_runtime"

        # 外部数据子目录
        self.MARKET_DATA_DIR = self.DATA_EXTERNAL_DIR / "market"
        self.REFERENCE_DATA_DIR = self.DATA_EXTERNAL_DIR / "reference"

        # 运行时数据子目录
        self.DB_DIR = self.DATA_RUNTIME_DIR / "db"
        self.CACHE_DIR = self.DATA_RUNTIME_DIR / "cache"
        self.REPORTS_DIR = self.DATA_RUNTIME_DIR / "reports"
        self.LOGS_DIR = self.DATA_RUNTIME_DIR / "logs"

        # 数据库文件路径
        self.DB_NAME = os.getenv("DB_NAME", "portfolio.db")
        self.DB_PATH = self.DB_DIR / self.DB_NAME

        # 用户持仓文件 (模板与实际文件)
        self.HOLDINGS_TEMPLATE = BASE_DIR / "holdings_template.csv"
        self.HOLDINGS_ACTIVE = BASE_DIR / "holdings.csv"  # 用户实际使用的文件

        # 同花顺数据接口登录用户名与密码
        self.IFIND_USERNAME = os.getenv("IFIND_USERNAME")
        self.IFIND_PIN = os.getenv("IFIND_PIN")
        # 增加一个检查，如果没配置则报错或警告
        if not self.IFIND_USERNAME or not self.IFIND_PIN:
            print("⚠️  警告：未在 .env 中找到 IFIND_USERNAME 或 IFIND_PIN，iFinD 数据源将不可用。")

        # Tushare 数据接口配置
        self.TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")
        self.MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "tushare").lower()
        if not self.TUSHARE_TOKEN and self.MARKET_DATA_PROVIDER == "tushare":
            print("⚠️  警告：未在 .env 中找到 TUSHARE_TOKEN，Tushare 数据源将不可用。")

        # --- LLM 配置 ---
        # Ollama（本地）
        self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"

        # Qwen（云端 API）
        self.QWEN_API_KEY = os.getenv("QWEN_API_KEY")
        self.QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")
        self.USE_QWEN = os.getenv("USE_QWEN", "false").lower() == "true"

        # 检查配置
        if self.USE_QWEN and not self.QWEN_API_KEY:
            print("⚠️  警告：USE_QWEN=true 但未配置 QWEN_API_KEY，请检查 .env 文件")


    def ensure_directories(self):
        """
        自动创建所有必要的目录。
        这是阶段 1 最重要的功能：让项目启动即就绪。
        """
        dirs_to_create = [
            self.DATA_EXTERNAL_DIR,
            self.MARKET_DATA_DIR,
            self.REFERENCE_DATA_DIR,
            self.DATA_RUNTIME_DIR,
            self.DB_DIR,
            self.CACHE_DIR,
            self.REPORTS_DIR,
            self.LOGS_DIR,
        ]

        for dir_path in dirs_to_create:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"[DIR] Created: {dir_path}")

        # 特别处理：如果 data_external 下没有 .gitkeep，创建一个以防被 git 忽略掉整个文件夹
        gitkeep = self.DATA_EXTERNAL_DIR / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


# 实例化单例
settings = Settings()

# 立即执行目录检查 (导入时自动运行)
settings.ensure_directories()
