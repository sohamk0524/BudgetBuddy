import os
import litellm
from tavily import TavilyClient

SCHOOL_DISPLAY_NAMES = {
    "uc_berkeley": "UC Berkeley",
    "uc_davis": "UC Davis",
    "uc_irvine": "UC Irvine",
    "uc_los_angeles": "UCLA",
    "uc_merced": "UC Merced",
    "uc_riverside": "UC Riverside",
    "uc_san_diego": "UC San Diego",
    "uc_santa_barbara": "UC Santa Barbara",
    "uc_santa_cruz": "UC Santa Cruz",
}

SEARCH_REWRITE_PROMPT = """You are a search query optimizer. Given a user's question and their university, rewrite it into an effective web search query that will find school-specific financial information (deals, discounts, scholarships, student resources).

User's university: {school}
User's question: {query}

Respond with ONLY the search query string, nothing else. Make it specific to the school and include the current year (2026) if relevant."""

SYNTHESIS_SYSTEM_PROMPT = """You are a helpful financial advisor for college students at {school}. Based on the search results provided, give a concise, actionable answer to the student's question.

Guidelines:
- Be specific to {school} and its surrounding area
- Include concrete names, prices, and locations when available
- Format your response in markdown with bullet points for easy reading
- If the search results don't contain relevant information, provide general tips that would apply to students at {school}
- Keep your response under 300 words
- Do not make up specific deals or prices that aren't in the search results"""


def get_school_advice(user_query: str, school_slug: str) -> dict:
    """
    Search the web for school-specific financial advice and synthesize an answer.

    Args:
        user_query: The student's question (e.g., "cheap coffee near campus")
        school_slug: The school identifier (e.g., "uc_davis")

    Returns:
        dict with "answer" and "sources" keys on success, or "error" key on failure.
    """
    school_display = SCHOOL_DISPLAY_NAMES.get(
        school_slug, school_slug.replace("_", " ").title()
    )

    # Step 1: Rewrite the query for web search using LLM
    try:
        rewrite_response = litellm.completion(
            model="claude-sonnet-4-5-20250929",
            messages=[
                {
                    "role": "user",
                    "content": SEARCH_REWRITE_PROMPT.format(
                        school=school_display, query=user_query
                    ),
                }
            ],
            max_tokens=100,
        )
        search_query = rewrite_response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM query rewrite failed, using fallback: {e}")
        search_query = f"{user_query} {school_display} student"

    # Step 2: Search the web with Tavily
    try:
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            return {"error": "TAVILY_API_KEY not configured"}

        client = TavilyClient(api_key=tavily_key)
        search_results = client.search(
            query=search_query, search_depth="advanced", include_answer=True
        )
    except Exception as e:
        print(f"Tavily search error: {e}")
        return {"error": f"Search failed: {str(e)}"}

    # Step 3: Format search results into context
    results_list = search_results.get("results", [])
    if results_list:
        context_parts = []
        for i, result in enumerate(results_list, 1):
            title = result.get("title", "Untitled")
            snippet = result.get("content", "")
            url = result.get("url", "")
            context_parts.append(f"[{i}] {title}\nURL: {url}\n{snippet}")
        context_block = "\n\n".join(context_parts)
    else:
        context_block = "No search results were found. Please provide general tips based on your knowledge."

    # Step 4: Synthesize answer with LLM
    try:
        synthesis_response = litellm.completion(
            model="claude-sonnet-4-5",
            messages=[
                {
                    "role": "system",
                    "content": SYNTHESIS_SYSTEM_PROMPT.format(school=school_display),
                },
                {
                    "role": "user",
                    "content": f"Question: {user_query}\n\nSearch Results:\n{context_block}",
                },
            ],
            max_tokens=1000,
        )
        answer = synthesis_response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM synthesis error: {e}")
        return {"error": f"Answer generation failed: {str(e)}"}

    # Step 5: Extract sources
    sources = []
    for result in results_list:
        title = result.get("title", "")
        url = result.get("url", "")
        if title and url:
            sources.append({"title": title, "url": url})

    return {"answer": answer, "sources": sources}
