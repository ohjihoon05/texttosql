# Contract: ResponseGenerator

**Module**: `src/services/response_generator.py`

## Class: ResponseGenerator

### Constructor

```python
def __init__(self, llm_router: LLMRouter | None = None):
    """Initialize response generator.
    
    Args:
        llm_router: Optional LLM router instance. Creates new if not provided.
    """
```

### Methods

#### generate_response (async)

```python
async def generate_response(
    self,
    question: str,
    result: QueryResult,
    timeout: float = 2.0
) -> str:
    """Generate natural language response from query result.
    
    Args:
        question: Original user question
        result: SQL query result
        timeout: LLM call timeout in seconds (default 2.0)
    
    Returns:
        Natural language response string
        
    Behavior:
        - 0 rows: "해당 조건에 맞는 데이터를 찾을 수 없습니다..."
        - 1 row: Detailed sentence with data values
        - 2-10 rows: List summary with key highlights
        - 10+ rows: Summary focused with top examples
        - Error: Friendly error message with suggestion
        - Timeout: Falls back to simple template response
    """
```

#### get_response_type

```python
def get_response_type(self, result: QueryResult) -> ResponseType:
    """Determine response type from result.
    
    Args:
        result: Query result to analyze
        
    Returns:
        ResponseType enum value
    """
```

#### generate_suggested_questions (P3)

```python
async def generate_suggested_questions(
    self,
    question: str,
    result: QueryResult,
    max_suggestions: int = 2
) -> List[str]:
    """Generate follow-up question suggestions.
    
    Args:
        question: Original question
        result: Query result for context
        max_suggestions: Maximum suggestions to return
        
    Returns:
        List of suggested follow-up questions
    """
```

## Integration Point

### SQLAgent._format_answer modification

```python
# Before (current)
def _format_answer(self, question: str, result: QueryResult) -> str:
    if result.is_empty:
        return "검색 결과가 없습니다."
    return f"{result.row_count}건의 결과를 찾았습니다."

# After (new)
async def _format_answer(self, question: str, result: QueryResult) -> str:
    response_gen = ResponseGenerator()
    return await response_gen.generate_response(question, result)
```
