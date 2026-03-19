import sqlite3
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import os

# --- 配置部分 ---
DB_PATH = "data_runtime/investments.db"
os.makedirs("data_runtime", exist_ok=True)


# --- 1. 数据库初始化 (保持不变，但可以增加一些字段以防万一) ---
def init_db():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT,
            date TEXT NOT NULL,
            open_price REAL,
            close_price REAL,
            high_price REAL,
            low_price REAL,
            volume REAL,
            turnover REAL, -- 成交额
            change_percent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, date)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_code_date ON daily_prices(code, date)')
    conn.commit()
    conn.close()
    print(f"✅ 数据库初始化完成: {DB_PATH}")


# --- 2. 数据获取技能 (使用 AkShare) ---
def fetch_etf_history(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    使用 AkShare 获取 ETF 历史日终数据
    参数:
        code: 基金代码 (如 '513050')
        start_date: 开始日期 '20230101' (默认取最近1年)
        end_date: 结束日期 '20260315' (默认取今天)
    返回:
        Pandas DataFrame 包含日期, 开盘, 收盘, 最高, 最低, 成交量等
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")
    if not start_date:
        # 默认获取过去365天的数据，保证有足够数据计算回撤
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    try:
        # 调用东方财富 ETF 历史行情接口
        # period: "daily" 表示日线
        # adjust: "" 表示不复权 (ETF通常看不复权，或者根据需求选 'qfq' 前复权)
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="")

        if df is None or df.empty:
            print(f"⚠️ 未获取到 {code} 的数据，可能是非交易日或代码错误")
            return pd.DataFrame()

        # 数据列名标准化 (AkShare 返回的列名可能是中文，我们需要映射一下)
        # 典型列名: ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open_price',
            '收盘': 'close_price',
            '最高': 'high_price',
            '最低': 'low_price',
            '成交量': 'volume',
            '成交额': 'turnover',
            '涨跌幅': 'change_percent'
        })

        # 确保日期格式为 YYYY-MM-DD (存入SQLite需要)
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df['code'] = code

        return df

    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        return pd.DataFrame()


def save_df_to_db(df: pd.DataFrame):
    """将 DataFrame 批量保存到 SQLite"""
    if df.empty:
        return

    conn = sqlite3.connect(DB_PATH)

    # 筛选需要的列
    cols_to_save = ['code', 'name', 'date', 'open_price', 'close_price', 'high_price', 'low_price', 'volume',
                    'turnover', 'change_percent']

    # 注意：AkShare 返回的数据里可能没有 'name' 列，我们需要单独处理或留空
    # 这里简单处理：如果没名字，就留空，或者您可以单独调一个接口获取名字
    # 为了演示，我们假设名字可以从代码映射，或者暂时存为 None
    # 实际使用中，可以在第一次获取时记录名字

    # 过滤出存在的列
    available_cols = [c for c in cols_to_save if c in df.columns]
    # 强制加上 code (如果不在里面)
    if 'code' not in available_cols:
        available_cols.insert(0, 'code')

    data_to_save = df[available_cols]

    # 如果 'name' 不在 df 中，我们可以手动加一个空列或者通过字典映射
    if 'name' not in data_to_save.columns:
        data_to_save['name'] = None
        # 进阶：这里可以加一个简单的字典映射常见ETF名字，或者调用另一个接口获取
        # 例如：if code == '513050': data_to_save['name'] = '中概互联网ETF'

    # 使用 to_sql 插入，if_exists='append' 配合主键冲突忽略需要在 SQLite 层面处理
    # 这里我们采用遍历插入以处理 UNIQUE 约束 (INSERT OR IGNORE)
    cursor = conn.cursor()
    for _, row in data_to_save.iterrows():
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO daily_prices 
                (code, name, date, open_price, close_price, high_price, low_price, volume, turnover, change_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['code'],
                row.get('name'),
                row['date'],
                row['open_price'],
                row['close_price'],
                row['high_price'],
                row['low_price'],
                row['volume'],
                row.get('turnover', 0),
                row['change_percent']
            ))
        except Exception as e:
            print(f"插入行失败: {e}")

    conn.commit()
    conn.close()
    print(f"💾 成功保存 {len(data_to_save)} 条记录到数据库")


def get_latest_close_data(code: str) -> dict:
    """获取数据库中该基金最新的收盘数据"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM daily_prices 
        WHERE code = ? 
        ORDER BY date DESC 
        LIMIT 1
    ''', (code,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return {}


# --- 测试入口 ---
if __name__ == "__main__":
    # 1. 初始化
    init_db()

    test_codes = ["513050", "512880"]

    print("\n🚀 开始使用 AkShare 获取日终历史数据...")

    for code in test_codes:
        print(f"\n--- 处理基金: {code} ---")

        # 2. 获取过去半年的数据 (确保有数据)
        df = fetch_etf_history(code, start_date=(datetime.now() - timedelta(days=180)).strftime("%Y%m%d"))

        if not df.empty:
            # 打印最新一条数据预览
            latest = df.iloc[0]  # 按日期倒序，第一条是最新
            print(f"✅ 最新交易日: {latest['date']}")
            print(f"✅ 收盘价: {latest['close_price']} ({latest['change_percent']}%)")

            # 3. 保存入库
            save_df_to_db(df)

            # 4. 验证读取
            db_data = get_latest_close_data(code)
            if db_data:
                print(f"📜 数据库验证成功: 最新收盘价 {db_data['close_price']}")
            else:
                print("❌ 数据库读取失败")
        else:
            print(f"⚠️ {code} 未获取到数据")