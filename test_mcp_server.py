from unittest.mock import patch

from mcp_server import search_knowledge


def test_search_success():
    with patch("mcp_server.retrieve_documents", return_value=["文書A", "文書B"]):
        result = search_knowledge("MyDot")
    assert "文書A" in result
    assert "文書B" in result


def test_search_empty():
    with patch("mcp_server.retrieve_documents", return_value=[]):
        result = search_knowledge("存在しない情報")
    assert result == "関連する文書が見つかりませんでした。"


def test_search_error():
    with patch(
        "mcp_server.retrieve_documents",
        side_effect=RuntimeError("Dify接続エラー"),
    ):
        result = search_knowledge("MyDot")
    assert result == "Difyナレッジ検索に失敗しました。"


def test_search_blank_query():
    with patch("mcp_server.retrieve_documents") as mock_retrieve:
        result = search_knowledge("   ")
    assert result == "検索キーワードを指定してください。"
    mock_retrieve.assert_not_called()
