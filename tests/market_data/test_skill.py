import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# 导入被测对象
from skills.market_data.skill import GetMarketDataSkill, get_market_data_skill
from skills.base import SkillContext, SkillResult, SkillMeta
from skills import get_skill_by_name, AVAILABLE_SKILLS
from config.enums import AssetType


class TestGetMarketDataSkill:

    @pytest.fixture
    def skill(self):
        """每次测试前实例化 Skill"""
        return GetMarketDataSkill()

    @pytest.fixture
    def mock_context(self):
        """创建一个标准的 Mock Context"""
        ctx = MagicMock(spec=SkillContext)
        ctx.target_date = "20231001"
        ctx.extra_params = {}
        return ctx

    @pytest.fixture
    def mock_service_result_success(self):
        """构造一个成功的 Service 返回结果"""
        return SkillResult(
            data={'close': 100.5, 'pre_close': 100.0, 'trade_date': '20231001'},
            meta=SkillMeta(
                source="api",
                status="success",
                target_date="20231001",
                message="数据来自 iFinD API"
            ),
            summary_hint="600519.SH 在 20231001 收盘价 100.5, 昨收 100.0, 涨跌幅 0.50%"
        )

    @pytest.fixture
    def mock_service_result_failed(self):
        """构造一个失败的 Service 返回结果"""
        return SkillResult(
            data={},
            meta=SkillMeta(
                source="none",
                status="failed",
                target_date="20231001",
                message="获取数据失败：连接超时"
            ),
            summary_hint=None
        )

    def test_execute_success_full_params(self, skill, mock_context, mock_service_result_success, mocker):
        """
        场景：参数完整，Service 返回成功
        预期：正常返回 Service 的结果
        """
        # 1. 准备输入
        mock_context.extra_params = {
            "symbol": "600519.SH",
            "asset_type": "stock"
        }

        # 2. Mock Service
        # 关键：patch skill 实例中的 service 属性
        with patch.object(skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = mock_service_result_success

            # 3. 执行
            result = skill.execute(mock_context)

            # 4. 断言
            # A. 验证 Service 被正确调用
            mock_service.get_daily_data.assert_called_once_with(
                context=mock_context,
                symbol="600519.SH",
                asset_type=AssetType.STOCK
            )

            # B. 验证返回结果透传
            assert result.meta.status == "success"
            assert result.data.get('close') == 100.5
            assert "涨跌幅" in result.summary_hint

    def test_execute_missing_symbol(self, skill, mock_context):
        """
        场景：用户未提供 symbol 参数
        预期：直接返回 failed 状态，提示缺少参数，不调用 Service
        """
        # 1. 准备输入 (extra_params 为空或缺少 symbol)
        mock_context.extra_params = {"asset_type": "stock"}  # 故意缺少 symbol

        # 2. Mock Service (确保即使被调用也能发现，但理论上不该被调用)
        with patch.object(skill, 'service') as mock_service:
            # 3. 执行
            result = skill.execute(mock_context)

            # 4. 断言
            # A. Service 绝不应该被调用
            mock_service.get_daily_data.assert_not_called()

            # B. 返回特定的错误信息
            assert result.meta.status == "failed"
            assert "缺少必要参数" in result.meta.message
            assert "symbol" in result.meta.message
            assert result.summary_hint is not None
            assert "代码" in result.summary_hint

    def test_execute_invalid_asset_type(self, skill, mock_context, mock_service_result_success, mocker):
        """
        场景：资产类型参数非法 (如 'unknown')
        预期：日志警告，默认降级为 STOCK，继续执行
        """
        # 1. 准备输入
        mock_context.extra_params = {
            "symbol": "000001.SZ",
            "asset_type": "unknown_type"  # 非法值
        }

        # 2. Mock Service
        with patch.object(skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = mock_service_result_success

            # Mock logger 以避免控制台输出太多 warning
            mocker.patch("skills.market_data.skill.logger")

            # 3. 执行
            result = skill.execute(mock_context)

            # 4. 断言
            # A. 验证调用时 asset_type 被修正为 STOCK
            call_args = mock_service.get_daily_data.call_args
            assert call_args[1]['asset_type'] == AssetType.STOCK

            # B. 业务逻辑继续执行成功
            assert result.meta.status == "success"

    def test_execute_service_failure_propagation(self, skill, mock_context, mock_service_result_failed, mocker):
        """
        场景：Service 执行失败 (如 API 报错)
        预期：Skill 层透传失败状态，不吞掉错误
        """
        # 1. 准备输入
        mock_context.extra_params = {"symbol": "600519.SH"}

        # 2. Mock Service -> 返回失败结果
        with patch.object(skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = mock_service_result_failed

            # 3. 执行
            result = skill.execute(mock_context)

            # 4. 断言
            assert result.meta.status == "failed"
            assert "获取数据失败" in result.meta.message
            # 确保错误信息透传给了上层
            assert result.data == {}

    def test_execute_post_process_no_pre_close(self, skill, mock_context, mocker):
        """
        场景：Service 成功返回，但数据中缺少 pre_close (如新股)
        预期：Skill 层自动补充提示信息
        """
        # 1. 构造特殊成功结果 (缺少 pre_close)
        partial_result = SkillResult(
            data={'close': 50.0, 'trade_date': '20231001'},  # 没有 pre_close
            meta=SkillMeta(
                source="api",
                status="success",
                target_date="20231001",
                message="OK"
            ),
            summary_hint="新股上市首日收盘价 50.0"
        )

        mock_context.extra_params = {"symbol": "688981.SH"}

        # 2. Mock Service
        with patch.object(skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = partial_result

            # 3. 执行
            result = skill.execute(mock_context)

            # 4. 断言
            assert result.meta.status == "success"
            # 验证 hint 被追加了提示
            assert "注：该日可能为上市首日" in result.summary_hint
            assert "无昨收数据" in result.summary_hint

    def test_execute_default_asset_type(self, skill, mock_context, mock_service_result_success, mocker):
        """
        场景：用户未提供 asset_type
        预期：默认为 STOCK
        """
        mock_context.extra_params = {"symbol": "000001"}  # 没传 asset_type

        with patch.object(skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = mock_service_result_success

            skill.execute(mock_context)

            # 验证默认值
            call_args = mock_service.get_daily_data.call_args
            assert call_args[1]['asset_type'] == AssetType.STOCK


class TestMarketDataE2ESimulation:

    @pytest.fixture
    def registered_skill(self):
        """
        从注册表中获取真实的技能实例
        验证技能是否已正确注册
        """
        skill = get_skill_by_name("get_market_data")
        assert skill is not None
        return skill

    @pytest.fixture
    def mock_context_factory(self):
        """
        工厂函数：用于快速构建模拟的 SkillContext
        模拟 LLM 解析后的状态
        """

        def _create_context(user_query: str, symbol: str, target_date: str = "20231020", asset_type: str = "stock"):
            ctx = MagicMock(spec=SkillContext)
            ctx.user_query = user_query
            ctx.target_date = target_date
            ctx.extra_params = {
                "symbol": symbol,
                "asset_type": asset_type
            }
            # 模拟 LLM 已经识别出要调用这个技能
            ctx.intent = "get_market_data"
            return ctx

        return _create_context

    def test_e2e_happy_path_maotai(self, registered_skill, mock_context_factory, mocker):
        """
        【场景】用户查询贵州茅台 (600519) 的行情
        【流程】
. 构造上下文 (模拟 LLM 提取了 '600519.SH')
. Mock Service 返回成功的真实数据
. 执行技能
. 验证最终返回给用户的自然语言提示
        """
        # 1. 准备输入
        context = mock_context_factory(
            user_query="茅台昨天多少钱？",
            symbol="600519.SH",
            target_date="20231020"
        )

        # 构造一个逼真的 Service 成功返回
        mock_service_result = SkillResult(
            data={
                'symbol': '600519.SH',
                'trade_date': '20231020',
                'close': 1750.50,
                'pre_close': 1730.00,
                'change_pct': 1.18
            },
            meta=SkillMeta(
                source="api",
                status="success",
                target_date="20231020",
                message="Data fetched from iFinD"
            ),
            summary_hint="600519.SH (贵州茅台) 在 2023-10-20 收盘价为 1750.50 元，较昨收上涨 1.18%。"
        )

        # 2. Mock Service (拦截底层 API 调用)
        with patch.object(registered_skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = mock_service_result

            # 3. 执行 (模拟 Agent 调用技能)
            result: SkillResult = registered_skill.execute(context)

            # 4. 断言 (验证端到端结果)
            # A. 状态必须成功
            assert result.meta.status == "success"

            # B. 核心数据必须存在
            assert result.data['close'] == 1750.50
            assert result.data['change_pct'] == 1.18

            # C. 【关键】最终给用户的自然语言回复必须通顺且包含关键信息
            assert result.summary_hint is not None
            assert "贵州茅台" in result.summary_hint or "600519" in result.summary_hint
            assert "1750.50" in result.summary_hint
            assert "上涨" in result.summary_hint

            # D. 验证 Service 被以正确的参数调用
            mock_service.get_daily_data.assert_called_once_with(
                context=context,
                symbol="600519.SH",
                asset_type=AssetType.STOCK
            )

    def test_e2e_missing_symbol_handling(self, registered_skill, mock_context_factory):
        """
        【场景】用户问“昨天股票跌了吗”，但没说是哪只股票
        【流程】
. 构造上下文 (symbol 缺失)
. 执行技能 (不应调用 Service)
. 验证返回的错误提示是否友好
        """
        # 1. 准备输入 (故意缺少 symbol)
        context = mock_context_factory(
            user_query="昨天股票跌了吗？",
            symbol=None,  # LLM 没能提取出股票代码
            target_date="20231020"
        )
        # 确保 extra_params 里也没有
        if context.extra_params and 'symbol' in context.extra_params:
            del context.extra_params['symbol']

        # 2. Mock Service (理论上不该被调用)
        with patch.object(registered_skill, 'service') as mock_service:
            # 3. 执行
            result: SkillResult = registered_skill.execute(context)

            # 4. 断言
            # A. Service 绝未被调用
            mock_service.get_daily_data.assert_not_called()

            # B. 状态失败
            assert result.meta.status == "failed"

            # C. 【关键】返回给用户的提示必须引导用户补充信息
            assert result.summary_hint is not None
            assert "代码" in result.summary_hint or "哪只" in result.summary_hint
            assert "请告诉我" in result.summary_hint or "提供" in result.summary_hint

    def test_e2e_service_error_propagation(self, registered_skill, mock_context_factory, mocker):
        """
        【场景】用户输入正确，但 iFinD 接口挂了/超时
        【流程】
. 构造正常上下文
. Mock Service 返回失败结果
. 验证错误信息是否透传给用户，而不是报系统异常
        """
        # 1. 准备输入
        context = mock_context_factory(
            user_query="查一下平安银行",
            symbol="000001.SZ",
            target_date="20231020"
        )

        # 构造服务层错误
        mock_service_error = SkillResult(
            data={},
            meta=SkillMeta(
                source="api",
                status="failed",
                target_date="20231020",
                message="iFinD API Timeout: Connection refused after 3 retries."
            ),
            summary_hint=None
        )

        # 2. Mock Service -> 返回错误
        with patch.object(registered_skill, 'service') as mock_service:
            mock_service.get_daily_data.return_value = mock_service_error

            # 3. 执行
            result: SkillResult = registered_skill.execute(context)

            # 4. 断言
            # A. 状态失败
            assert result.meta.status == "failed"

            # B. 错误信息透传
            assert "Timeout" in result.meta.message or "Connection" in result.meta.message

            # C. 即使失败，最好也有一个简要的 hint 给前端展示 (取决于具体实现，这里验证是否有某种反馈)
            # 如果代码中没有专门处理失败时的 summary_hint，这里可能为 None，
            # 但通常 Agent 框架会根据 meta.message 生成默认提示。
            # 此处主要验证程序没有崩溃 (Crash)。

    def test_e2e_registry_integrity(self):
        """
        【场景】验证注册表本身是否正常
        【目的】确保 get_skill_by_name 能找到我们的技能，且名称匹配
        """
        # 1. 检查列表非空
        assert len(AVAILABLE_SKILLS) > 0

        # 2. 检查我们的技能在列表中
        skill_names = [s.name for s in AVAILABLE_SKILLS]
        assert "get_market_data" in skill_names

        # 3. 检查查找函数
        skill = get_skill_by_name("get_market_data")
        assert skill.name == "get_market_data"

        # 4. 检查找不到时的异常
        with pytest.raises(ValueError) as exc_info:
            get_skill_by_name("non_existent_skill")
        assert "non_existent_skill" in str(exc_info.value)