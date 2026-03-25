# test_skills.py (临时测试文件)
from skills import AVAILABLE_SKILLS, get_skill_by_name

print("=== 技能注册测试 ===")

# 1. 检查列表
print(f"当前可用技能数量: {len(AVAILABLE_SKILLS)}")
for skill in AVAILABLE_SKILLS:
    print(f"- 技能名称: {skill.name}")
    print(f"  技能描述: {skill.description[:50]}...")

# 2. 检查查找功能
try:
    # 假设您的 skill.name 是 "get_market_data" 或类似的名字
    # 如果不确定名字，可以先打印 skill.name 看看
    target_name = AVAILABLE_SKILLS[0].name
    found_skill = get_skill_by_name(target_name)
    print(f"\n✅ 成功找到技能: {found_skill.name}")

    # 3. 检查是否有 prompt (如果您创建了 prompt.txt 且 BaseSkill 支持读取)
    if hasattr(found_skill, 'prompt_template') and found_skill.prompt_template:
        print("✅ Prompt 模板已加载")
    else:
        print("⚠️ 未检测到 Prompt 模板 (可能是基类未实现或文件未创建)")

except Exception as e:
    print(f"❌ 测试失败: {e}")