# app/services/fashion_agent.py
import json
import operator
from typing import Annotated, Sequence, List, Optional, Dict, Any, TypedDict
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.core.logger import logger
from app.models.closet import ClothingItem, OutfitCombo
from app.services.color_math import (
    evaluate_color_compatibility,
    evaluate_outfit_palette_compatibility,
    get_color_name_from_hex
)
from app.services.embedding_service import search_wardrobe_hybrid
from app.services.weather import get_weather_by_query_sync
from app.services.outfit_service import get_or_create_outfit_combo

# ============================================================================
# 1. AGENT STATE DEFINITION
# ============================================================================

class FashionAgentState(MessagesState):
    """Trạng thái trung tâm được truyền qua các Node trong LangGraph"""
    user_id: int
    user_location: str
    preferred_style: str
    saved_outfit_id: Optional[int]
    db_session: Any
        

# ============================================================================
# 2. STRUCTURED TOOLS DEFINITION
# ============================================================================

def create_agent_tools(db: Session, user_id: int):
    """Factory tạo danh sách Tools có bind session Database và User ID"""

    @tool
    def get_weather_forecast(location: str = "Hanoi", date: str = "today") -> str:
        """
        Lấy thông tin dự báo thời tiết tại một địa điểm (Nhiệt độ, tình trạng mưa/nắng, độ ẩm).
        Hãy dùng tool này khi người dùng nhắc tới sự kiện, địa điểm hoặc cần phối đồ theo thời tiết.
        """
        try:
            weather_data = get_weather_by_query_sync(location_query=location, date_str=date)
            return json.dumps(weather_data, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"Không thể lấy thời tiết: {str(e)}"})

    @tool
    def search_closet_rag(query: str, category: Optional[str] = None, top_k: int = 5) -> str:
        """
        Tìm kiếm ngữ nghĩa (RAG Hybrid Search với pgvector) các món đồ trong tủ đồ của người dùng.
        Tham số:
        - query: Mô tả món đồ cần tìm (ví dụ: 'áo khoác ấm đi tiệc', 'đầm đỏ mận dạ hội', 'áo dài tết', 'quần tây đen thanh lịch', 'giày sneaker năng động')
        - category: (Tùy chọn) Lọc theo loại 'Shirts', 'T-Shirts', 'Pants', 'Jeans', 'Shorts', 'Dresses', 'Skirts', 'Jackets', 'Shoes', 'Bags', 'Accessories'
        - top_k: Số lượng món đồ tối đa cần lấy (mặc định: 5)
        """
        try:
            from app.services.embedding_service import search_wardrobe_hybrid_sync
            categories = [category] if category else None
            items = search_wardrobe_hybrid_sync(db, user_id, query, categories=categories, top_k=top_k)

            if not items:
                return json.dumps({"message": "Không tìm thấy món đồ nào phù hợp trong tủ đồ."}, ensure_ascii=False)

            results = []
            for item in items:
                results.append({
                    "id": item.id,
                    "category": item.category,
                    "color_name": item.color_name or get_color_name_from_hex(item.color_code),
                    "color_code": item.color_code,
                    "style_tag": item.style_tag,
                    "description": item.description_text or ""
                })
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[Tool Error search_closet_rag]: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def check_color_harmony(color_hex_1: str, color_hex_2: str) -> str:
        """
        Kiểm tra độ hòa hợp màu sắc (Color Harmony) giữa 2 món đồ sử dụng toán học CIELAB và Delta-E 76.
        Dùng tool này để đảm bảo 2 món đồ phối cùng nhau không bị xung đột sắc độ (Color Clash).
        """
        try:
            analysis = evaluate_color_compatibility(color_hex_1, color_hex_2)
            return json.dumps(analysis, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def check_outfit_palette_harmony(hex_colors: List[str]) -> str:
        """
        Kiểm tra và chấm điểm độ hòa hợp màu sắc cho toàn bộ bảng phối màu cả set đồ (3-5 món: Áo trong, Áo khoác, Quần, Giày...).
        Trả về điểm số Harmony Score (0-100), phong cách phối màu (Monochromatic, Balanced, High Contrast) và cảnh báo xung đột màu nếu có.
        """
        try:
            analysis = evaluate_outfit_palette_compatibility(hex_colors)
            return json.dumps(analysis, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def save_recommended_outfit(item_ids: List[int], style_name: str) -> str:
        """
        Lưu bộ phối trang phục (Outfit Combo) hoàn chỉnh vào Database của người dùng.
        Bắt buộc phải gọi tool này khi đã chọn được các món đồ (item_ids) ưng ý từ tủ đồ để user có thể lưu lại và sử dụng!
        LƯU Ý QUAN TRỌNG: Chỉ truyền các ID thực sự tồn tại trong kết quả trả về từ tool `search_closet_rag`.
        """
        try:
            if not item_ids or len(item_ids) < 2:
                return json.dumps({
                    "status": "error",
                    "error": "Cần ít nhất 2 món đồ để tạo một bộ outfit hoàn chỉnh."
                }, ensure_ascii=False)

            # 🛡️ Anti-Hallucination Guardrail: Xác thực tính tồn tại & quyền sở hữu của từng ID trong DB
            clean_item_ids = [int(i) for i in item_ids if str(i).isdigit()]
            valid_items = db.query(ClothingItem).filter(
                ClothingItem.user_id == user_id,
                ClothingItem.id.in_(clean_item_ids)
            ).all()

            valid_ids = {item.id for item in valid_items}
            hallucinated_ids = [i for i in clean_item_ids if i not in valid_ids]

            if hallucinated_ids:
                logger.warning(f"[Guardrail Hallucination Alert] Agent tried to use non-existent item IDs: {hallucinated_ids}")
                return json.dumps({
                    "status": "error",
                    "error": f"Các món đồ có ID {hallucinated_ids} không tồn tại trong tủ đồ của người dùng. Vui lòng chỉ chọn từ các ID trả về bởi tool search_closet_rag!"
                }, ensure_ascii=False)

            if len(valid_items) < 2:
                return json.dumps({
                    "status": "error",
                    "error": "Không đủ tối thiểu 2 món đồ hợp lệ trong tủ đồ để tạo thành một set đồ."
                }, ensure_ascii=False)

            combo = get_or_create_outfit_combo(db, user_id, style_name, clean_item_ids)
            if combo:
                return json.dumps({
                    "status": "success",
                    "outfit_id": combo.id,
                    "style_name": style_name,
                    "item_ids": [item.id for item in combo.items],
                    "message": f"Đã lưu thành công bộ outfit '{style_name}' (ID: {combo.id}) vào tủ đồ!"
                }, ensure_ascii=False)
            return json.dumps({"status": "error", "error": "Không thể tạo bộ outfit trong DB."})
        except Exception as e:
            logger.error(f"[Tool Error save_recommended_outfit]: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    return [
        get_weather_forecast,
        search_closet_rag,
        check_color_harmony,
        check_outfit_palette_harmony,
        save_recommended_outfit
    ]


# ============================================================================
# 3. LLM INITIALIZATION & STATEGRAPH BUILDER
# ============================================================================

def _extract_text_from_ai_message(content: Any) -> str:
    """Trích xuất chuỗi văn bản sạch từ nội dung AIMessage (chuỗi hoặc danh sách Content Blocks)"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return str(content)

def get_agent_llm():
    """Khởi tạo Model LLM hỗ trợ Tool Calling (Gemini hoặc OpenAI) với Fallback tự động"""
    gemini_key = settings.GEMINI_API_KEY
    if gemini_key and "your_" not in gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            primary_model = settings.GEMINI_MODEL if settings.GEMINI_MODEL else "gemini-3.1-flash-lite"
            if any(deprecated in primary_model for deprecated in ["1.5", "2.0", "3.6"]):
                primary_model = "gemini-3.1-flash-lite"

            candidate_models = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.7-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]
            fallback_names = [m for m in candidate_models if m != primary_model]

            primary_llm = ChatGoogleGenerativeAI(
                model=primary_model,
                api_key=gemini_key
            )
            fallback_llms = [
                ChatGoogleGenerativeAI(model=m, api_key=gemini_key)
                for m in fallback_names
            ]
            return primary_llm.with_fallbacks(fallback_llms)
        except Exception as e:
            logger.warning(f"Không thể khởi tạo ChatGoogleGenerativeAI: {e}")

    openai_key = settings.OPENAI_API_KEY
    if openai_key and "your_" not in openai_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=openai_key,
                temperature=0.3
            )
        except Exception as e:
            logger.warning(f"Không thể khởi tạo ChatOpenAI: {e}")

    return None

def build_fashion_agent_graph(tools: list, llm_model: Any):
    """Xây dựng StateGraph LangGraph cho Fashion Stylist Agent"""
    
    # 1. Bind danh sách Tools vào LLM
    llm_with_tools = llm_model.bind_tools(tools)

    # 2. Node Agent: LLM suy luận và quyết định hành động
    def agent_node(state: FashionAgentState):
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # 3. Node Tool: Thực thi các Tool được LLM yêu cầu
    tool_node = ToolNode(tools)

    # 4. Conditional Edge: Kiểm tra xem có cần gọi Tool tiếp không
    def should_continue(state: FashionAgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    # 5. Khởi tạo Graph
    workflow = StateGraph(FashionAgentState)  # type: ignore[bad-specialization,arg-type]
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()


# ============================================================================
# 4. RUNNER FUNCTION (SERVICE API)
# ============================================================================

SYSTEM_STYLIS_PROMPT = """Bạn là Senior AI Fashion Stylist & Image Consultant cao cấp của FitCheck.
Nhiệm vụ của bạn là tư vấn phong cách, phối đồ và giải quyết mọi bài toán thời trang cho người dùng.

QUY TẮC BẮT BUỘC:
1. Độc lập & Tự chủ (Agentic): Khi người dùng yêu cầu phối đồ cho một sự kiện/thời tiết hoặc chat nhiều lượt, hãy chủ động:
   - Dùng tool `get_weather_forecast` nếu có yếu tố thời tiết, địa điểm cần cân nhắc.
   - Dùng tool `search_closet_rag` để tìm các món đồ phù hợp trong tủ đồ của họ.
   - Dùng tool `check_outfit_palette_harmony` hoặc `check_color_harmony` để kiểm tra độ hòa hợp màu sắc khi cần.
   - Dùng tool `save_recommended_outfit` để lưu bộ phối khi đã chọn được các món đồ cụ thể từ tủ đồ.
   - KHÔNG gọi lặp lại cùng một công cụ với tham số tương tự. Nếu trong tủ đồ chưa có đủ món phù hợp, hãy tư vấn phối các món hiện có và gợi ý thêm món đồ nên bổ sung.
   - Nếu người dùng chỉ chào hỏi, hỏi kiến thức phối màu chung hoặc tư vấn cơ bản, hãy trực tiếp trả lời thân thiện mà KHÔNG cần gọi tool tìm kiếm hay lưu outfit.
2. 🛡️ QUY TẮC CHỐNG BỊA ĐẶT (ANTI-HALLUCINATION):
   - Khi gọi `save_recommended_outfit`, bạn BẮT BUỘC CHỈ ĐƯỢC PHÉP dùng các `id` nguyên bản xuất hiện trong kết quả trả về của tool `search_closet_rag`.
   - TUYỆT ĐỐI KHÔNG tự nghĩ ra, đoán mò hoặc bịa đặt `item_ids`.
   - Một set đồ hoàn chỉnh cần tối thiểu 2 món đồ thực sự từ tủ đồ (ví dụ: Áo + Quần, hoặc Đầm + Giày/Túi).
3. Ngôn ngữ: Trả lời lịch sự, tinh tế, chuyên nghiệp bằng tiếng Việt. Nêu rõ lý do tại sao các món đồ lại hợp nhau về màu sắc, chất liệu và ngữ cảnh.
"""

async def run_fashion_stylist_agent(
    user_id: int,
    message: str,
    db: Session,
    user_location: str = "Hanoi",
    preferred_style: str = "Casual",
    history: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Thực thi Agentic Workflow với LangGraph cho phiên chat thời trang (hỗ trợ Multi-turn Memory & Guardrails)
    """
    llm = get_agent_llm()
    if not llm:
        # Fallback khi chưa cấu hình API key
        return {
            "reply": "Xin lỗi, hệ thống AI Stylist chưa được cấu hình API Key. Vui lòng thử lại sau.",
            "suggested_outfit_id": None
        }

    tools = create_agent_tools(db, user_id)
    app_graph = build_fashion_agent_graph(tools, llm)

    initial_messages: list[BaseMessage] = [
        SystemMessage(content=SYSTEM_STYLIS_PROMPT)
    ]

    # Nạp lịch sử hội thoại nhiều lượt (Multi-turn Chat Memory)
    if history:
        for h in history:
            role = getattr(h, "role", None) or (h.get("role") if isinstance(h, dict) else None)
            content = getattr(h, "content", None) or (h.get("content") if isinstance(h, dict) else None)
            if content and isinstance(content, str):
                if role in ("user", "human"):
                    initial_messages.append(HumanMessage(content=content))
                elif role in ("assistant", "ai"):
                    initial_messages.append(AIMessage(content=content))

    # Thêm tin nhắn hiện tại của người dùng
    initial_messages.append(HumanMessage(content=message))

    initial_state: Dict[str, Any] = {
        "messages": initial_messages,
        "user_id": user_id,
        "user_location": user_location,
        "preferred_style": preferred_style,
        "saved_outfit_id": None,
        "db_session": db
    }

    try:
        # Chạy đồ thị trạng thái LangGraph với Guardrail giới hạn recursion_limit = 25
        result = app_graph.invoke(initial_state, config={"recursion_limit": 25})
        messages = result.get("messages", [])
            
        last_ai_message = ""
        saved_outfit_id = None

        # Trích xuất câu trả lời cuối cùng và Outfit ID được tạo (nếu có)
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                last_ai_message = _extract_text_from_ai_message(msg.content)
                break

        for msg in messages:
            if isinstance(msg, ToolMessage) and "outfit_id" in str(msg.content):
                try:
                    if isinstance(msg.content, str):
                        tool_data = json.loads(msg.content)
                    elif isinstance(msg.content, dict):
                        tool_data = msg.content
                    elif isinstance(msg.content, list) and msg.content and isinstance(msg.content[0], dict):
                        tool_data = msg.content[0]
                    else:
                        tool_data = json.loads(str(msg.content))

                    if isinstance(tool_data, dict) and "outfit_id" in tool_data:
                        candidate_id = int(tool_data["outfit_id"])
                        # 🛡️ Post-Execution Guardrail: Xác thực sở hữu outfit_id trực tiếp trong DB
                        verified_combo = db.query(OutfitCombo).filter(
                            OutfitCombo.id == candidate_id,
                            OutfitCombo.user_id == user_id
                        ).first()
                        if verified_combo:
                            saved_outfit_id = candidate_id
                        else:
                            logger.warning(f"[Guardrail Alert] Outfit ID {candidate_id} không hợp lệ cho user_id={user_id}")
                except Exception:
                    pass

        return {
            "reply": last_ai_message or "Đã hoàn thành tư vấn trang phục!",
            "suggested_outfit_id": saved_outfit_id
        }

    except Exception as e:
        err_msg = str(e)
        if "Recursion limit" in err_msg or "GraphRecursionError" in type(e).__name__:
            logger.warning(f"[Fashion Agent]: Đạt giới hạn recursion limit: {err_msg}. Phục hồi câu trả lời tinh gọn.")
            return {
                "reply": "Dựa trên tủ đồ và phong cách của bạn, tôi đã tổng hợp các gợi ý phù hợp. Bạn hãy ưu tiên kết hợp các món đồ có tông màu tương phản nhẹ hoặc đồng điệu đã chọn để tạo nên set đồ thanh lịch nhé!",
                "suggested_outfit_id": None
            }
        logger.exception(f"[Fashion Agent Error]: {e}")
        return {
            "reply": f"Rất tiếc, đã có lỗi xảy ra trong quá trình trợ lý AI xử lý yêu cầu: {err_msg}",
            "suggested_outfit_id": None
        }

