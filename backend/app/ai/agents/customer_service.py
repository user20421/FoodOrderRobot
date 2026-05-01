"""
客服智能体 (CustomerServiceAgent)

职责：处理闲聊、问候、感谢、告别等社交互动，以及无法被其他智能体分类的请求。
作为兜底智能体，当 Supervisor 无法确定具体业务意图时，由本智能体接手。

适用场景：
  - "你好"
  - "谢谢"
  - "再见"
  - "你们店在哪里？"
  - 无法归类的表达

工具集：
  - get_welcome_message: 欢迎语
  - get_quick_help: 快捷帮助提示
  - get_system_info: 店铺信息
"""
from app.ai.agents.base import BaseAgent
from app.ai.tools import get_all_menu_items, get_system_info


class CustomerServiceAgent(BaseAgent):
    """
    客服智能体
    友好、亲切、简洁。能识别问候/感谢/告别，必要时引导用户到业务场景。
    """

    def __init__(self):
        super().__init__(
            name="客服专员",
            description="处理闲聊、问候、感谢、告别及兜底回复",
        )

    async def run(self, user_id: int, message: str, cart: list = None) -> dict:
        """
        客服流程：
        1. 识别消息类型（问候/感谢/告别/其他）
        2. 返回对应的标准化回复
        3. 附带快捷操作引导
        """
        msg = message.lower()

        # 问候
        if self._is_greeting(msg):
            return {"response": await self._greeting_response()}

        # 感谢
        if self._is_thanks(msg):
            return {"response": "不客气！很高兴能帮到您。还有其他需要吗？"}

        # 告别
        if self._is_farewell(msg):
            return {"response": "好的，期待您的下次光临！祝您用餐愉快～"}

        # 询问店铺信息（兜底场景）
        if any(k in msg for k in ["在哪", "地址", "电话", "联系", "营业", "配送", "外卖", "打包"]):
            return {"response": get_system_info()}

        # 其他兜底：引导用户
        return {"response": await self._default_response()}

    def _is_greeting(self, msg: str) -> bool:
        """判断是否是问候"""
        return any(k in msg for k in ["你好", "在吗", "在不在", "hi", "hello", "您好", "有人在吗", "欢迎"])

    def _is_thanks(self, msg: str) -> bool:
        """判断是否是感谢"""
        return any(k in msg for k in ["谢谢", "感谢", "多谢", "谢了"])

    def _is_farewell(self, msg: str) -> bool:
        """判断是否是告别"""
        return any(k in msg for k in ["再见", "拜拜", "bye", "走了", "下次", "回头见"])

    async def _greeting_response(self) -> str:
        """生成问候回复"""
        items = await get_all_menu_items()
        if not items:
            return (
                "您好！欢迎光临，我是本店服务员小餐～\n"
                "您可以这样问我：\n"
                "* '推荐几个菜'\n"
                "* '来一份宫保鸡丁'\n"
                "* '查询我的订单'"
            )

        hot = [it for it in items if it.category == "热菜"][:3]
        hot_str = "、".join([f"{it.name}（{it.price}元）" for it in hot])

        return (
            f"您好！欢迎光临，我是本店服务员小餐，很高兴为您服务～\n"
            f"本店目前有 {len(items)} 道精选菜品，涵盖热菜、素菜、海鲜、汤品、主食等。\n\n"
            f"今天最受欢迎的几道是：{hot_str}。\n\n"
            f"您可以这样问我：\n"
            f"* '推荐几个下饭菜'\n"
            f"* '有什么清淡的菜'\n"
            f"* '来一份宫保鸡丁'\n"
            f"* '查询我的订单'"
        )

    async def _default_response(self) -> str:
        """生成兜底回复"""
        items = await get_all_menu_items()
        if not items:
            return (
                "您好！我是本店服务员小餐～\n"
                "您可以这样问我：\n"
                "* '推荐几个菜'\n"
                "* '来一份宫保鸡丁'\n"
                "* '查询我的订单'"
            )

        hot = [it for it in items if it.category == "热菜"][:3]
        hot_str = "、".join([f"{it.name}（{it.price}元）" for it in hot])

        return (
            f"您好！我是本店服务员小餐～\n"
            f"本店有各类热菜、素菜、海鲜、汤品、主食等 {len(items)} 道精选菜品。\n\n"
            f"目前最受欢迎的几道是：{hot_str}。\n\n"
            f"您可以这样问我：\n"
            f"* '推荐几个下饭菜'\n"
            f"* '有什么清淡的菜'\n"
            f"* '来一份宫保鸡丁'\n"
            f"* '查询我的订单'"
        )
