from mcp.server.fastmcp import FastMCP
from mydot import retrieve_documents

mcp = FastMCP("MyDot Knowledge")


@mcp.tool()
def search_knowledge(query: str) -> str:
    """MyDotのDifyナレッジベースから関連文書を検索する。"""
    if not query.strip():
        return "検索キーワードを指定してください。"

    try:
        documents = retrieve_documents(query)
    except RuntimeError:
        return "Difyナレッジ検索に失敗しました。"

    if not documents:
        return "関連する文書が見つかりませんでした。"

    return "\n\n---\n\n".join(documents)


if __name__ == "__main__":
    mcp.run(transport="stdio")
