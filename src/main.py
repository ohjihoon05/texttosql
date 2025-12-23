"""Chainlit main entry point for Excel Text-to-SQL system."""

import logging
import sys
from pathlib import Path

# Add project root to path for imports BEFORE any local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import chainlit as cl

# Import config and services
from src.config import get_settings
from src.services.sql_agent import SQLAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@cl.on_chat_start
async def on_chat_start():
    """Initialize chat session."""
    logger.info("New chat session started")

    # Initialize SQL Agent for this session
    agent = SQLAgent()
    cl.user_session.set("agent", agent)

    # Send welcome message
    await cl.Message(
        content=(
            "## Excel Text-to-SQL 시스템\n\n"
            "안녕하세요! Excel 파일을 자연어로 질의할 수 있는 시스템입니다.\n\n"
            "**사용 방법:**\n"
            "1. Excel 파일(.xlsx, .xls)을 업로드해주세요\n"
            "2. 자연어로 질문하세요 (예: '김철수가 뭘 했어?')\n\n"
            "파일을 업로드하려면 클립 아이콘을 클릭하세요."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages."""
    logger.info(f"Message received: {message.content[:50] if message.content else 'No content'}")
    logger.info(f"Elements: {message.elements}")

    agent: SQLAgent = cl.user_session.get("agent")

    if agent is None:
        await cl.Message(content="세션 오류가 발생했습니다. 페이지를 새로고침 해주세요.").send()
        return

    # Check for file uploads
    if message.elements:
        await handle_file_upload(message, agent)
        return

    # Check if file is loaded
    if agent.get_schema() is None:
        await cl.Message(
            content="먼저 Excel 파일을 업로드해주세요. 📎 아이콘을 클릭하세요."
        ).send()
        return

    # Process question
    await handle_question(message.content, agent)


async def handle_file_upload(message: cl.Message, agent: SQLAgent) -> None:
    """Handle Excel file upload.

    Args:
        message: Message with file elements
        agent: SQL Agent instance
    """
    # Find Excel files in attachments (check by mime type or name)
    excel_mimes = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    )
    excel_files = [
        el for el in message.elements
        if el.path and (
            getattr(el, 'mime', '') in excel_mimes
            or el.name.lower().endswith(('.xlsx', '.xls'))
        )
    ]
    logger.info(f"Found Excel files: {[f.name for f in excel_files]}")

    if not excel_files:
        await cl.Message(
            content="Excel 파일(.xlsx, .xls)만 지원됩니다. 다른 파일을 업로드해주세요."
        ).send()
        return

    # Use first Excel file
    file = excel_files[0]
    original_path = Path(file.path)

    # Copy file with proper extension (Chainlit saves without extension)
    import shutil
    temp_dir = Path(".files_temp")
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.name
    shutil.copy2(original_path, file_path)
    logger.info(f"Copied file to: {file_path}")

    try:
        # Show loading message
        loading_msg = cl.Message(content=f"📂 '{file.name}' 파일을 로딩 중...")
        await loading_msg.send()

        # Load file
        schema = agent.load_file(file_path)

        # Format schema summary
        schema_summary = format_schema_summary(schema)

        # Update loading message
        loading_msg.content = (
            f"✅ **'{schema.file_name}' 파일 로드 완료!**\n\n"
            f"**파일 정보:**\n"
            f"- 크기: {schema.file_size_mb:.2f} MB\n"
            f"- 시트 수: {len(schema.sheets)}개\n"
            f"- 총 행 수: {schema.total_rows:,}행\n"
            f"- 로드 시간: {schema.load_time_seconds:.2f}초\n\n"
            f"**시트 목록:**\n{schema_summary}\n\n"
            "이제 자연어로 질문해보세요! 예: '김철수가 뭘 했어?'"
        )
        await loading_msg.update()

        logger.info(f"File loaded: {schema.file_name}")

    except FileNotFoundError as e:
        await cl.Message(content=f"❌ 파일을 찾을 수 없습니다: {e}").send()
    except ValueError as e:
        await cl.Message(content=f"❌ 파일 오류: {e}").send()
    except Exception as e:
        logger.error(f"File loading error: {e}")
        await cl.Message(content=f"❌ 파일 로딩 중 오류가 발생했습니다: {e}").send()


def format_schema_summary(schema) -> str:
    """Format schema into readable summary.

    Args:
        schema: ExcelSchema instance

    Returns:
        Formatted string summary
    """
    lines = []
    for sheet_name, sheet in schema.sheets.items():
        col_names = ", ".join(sheet.column_names[:5])
        if len(sheet.column_names) > 5:
            col_names += f" ... (+{len(sheet.column_names) - 5}개)"
        lines.append(f"- **{sheet_name}** ({sheet.row_count}행): {col_names}")
    return "\n".join(lines)


async def handle_question(question: str, agent: SQLAgent) -> None:
    """Handle natural language question.

    Args:
        question: User's question
        agent: SQL Agent instance
    """
    # Show thinking message
    thinking_msg = cl.Message(content="🤔 질문을 분석하고 SQL을 생성 중...")
    await thinking_msg.send()

    try:
        # Ask agent
        response = await agent.ask(question)

        # Format response
        result_content = f"## 답변\n\n{response.answer}\n\n"

        if response.sql_query:
            result_content += f"### 실행된 SQL\n```sql\n{response.sql_query}\n```\n\n"

        if response.data_preview:
            result_content += f"### 데이터 미리보기\n{response.data_preview}\n\n"

        if response.source_sheets:
            result_content += f"📊 사용된 테이블: {', '.join(response.source_sheets)}"

        # Update thinking message with result
        thinking_msg.content = result_content
        await thinking_msg.update()

        logger.info(f"Question processed: {question[:50]}...")

    except Exception as e:
        logger.error(f"Question processing error: {e}")
        thinking_msg.content = f"❌ 처리 중 오류가 발생했습니다: {e}"
        await thinking_msg.update()


@cl.on_stop
async def on_stop():
    """Handle session stop."""
    agent: SQLAgent = cl.user_session.get("agent")
    if agent:
        agent.close()
    logger.info("Chat session ended")


if __name__ == "__main__":
    # For development/testing
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)
