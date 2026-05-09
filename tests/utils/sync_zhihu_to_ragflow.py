import asyncio
import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# 添加项目根目录到系统路径
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.services.article_collector_service import ArticleCollectorService
from backend.services.ragflow_integration_colleague import RAGFlowClient

# 加载环境变量
load_dotenv()

async def sync_zhihu_to_ragflow(keyword: str, max_articles: int = 5):
    """
    爬取知乎文章并使用同事提供的接口同步到 RAGFlow
    """
    # 1. 获取配置
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
    api_key = os.getenv("RAGFLOW_API_KEY")
    dataset_id = os.getenv("RAGFLOW_DATASET_ID")

    if not api_key or not dataset_id:
        logger.error("错误：请在 .env 文件中配置 RAGFLOW_API_KEY 和 RAGFLOW_DATASET_ID")
        return

    logger.info(f"开始同步知乎文章，关键词: {keyword}")
    
    # 2. 爬取知乎文章
    collector_service = ArticleCollectorService()
    # 我们只运行采集逻辑，不使用内置的同步逻辑（因为要使用同事的版本）
    result = await collector_service.collect_trending_articles(
        keyword=keyword,
        platforms=["zhihu"],
        max_articles_per_platform=max_articles,
        save_to_db=False,  # 不保存到数据库，我们手动同步
        sync_to_ragflow=False  # 不使用内置同步逻辑
    )

    articles = result.get("results", {}).get("zhihu", [])
    if not articles:
        logger.warning("未采集到任何知乎文章")
        return

    logger.info(f"成功采集到 {len(articles)} 篇知乎文章，准备同步到 RAGFlow...")

    # 3. 初始化同事提供的客户端
    ragflow_client = RAGFlowClient(base_url, api_key)

    # 4. 创建临时目录存放文章文件
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, article in enumerate(articles):
            title = article.get("title", f"zhihu_article_{i}")
            content = article.get("content", "")
            
            if not content:
                logger.warning(f"文章 '{title}' 内容为空，跳过")
                continue

            # 处理标题中的非法字符
            safe_title = "".join([c for c in title if c.isalnum() or c in (" ", "_", "-")]).strip()
            file_path = Path(tmpdir) / f"{safe_title}.txt"
            
            # 写入临时文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Title: {title}\n")
                f.write(f"URL: {article.get('url', '')}\n")
                f.write(f"Author: {article.get('author', 'Unknown')}\n\n")
                f.write(content)

            # 5. 调用同事提供的接口上传文档
            try:
                logger.info(f"正在上传文档: {title}...")
                upload_result = ragflow_client.upload_document(dataset_id, str(file_path))
                
                if upload_result.get("code") == 0:
                    logger.success(f"文档 '{title}' 上传成功！")
                    
                    # 6. 获取文档 ID 并启动自动解析
                    doc_data = upload_result.get("data")
                    # RAGFlow 上传接口通常返回的是一个列表或者单个对象，根据实际返回提取
                    doc_id = None
                    if isinstance(doc_data, list) and len(doc_data) > 0:
                        doc_id = doc_data[0].get("id")
                    elif isinstance(doc_data, dict):
                        doc_id = doc_data.get("id")
                    
                    if doc_id:
                        logger.info(f"正在为文档 '{title}' (ID: {doc_id}) 启动自动解析...")
                        run_result = ragflow_client.run_document_analysis([doc_id])
                        if run_result.get("code") == 0:
                            logger.success(f"文档 '{title}' 已成功启动自动解析！")
                        else:
                            logger.error(f"文档 '{title}' 启动解析失败: {run_result.get('message')}")
                    else:
                        logger.warning(f"未能从上传结果中提取到文档 ID，无法自动启动解析")
                else:
                    logger.error(f"文档 '{title}' 上传失败: {upload_result.get('message')}")
            except Exception as e:
                logger.error(f"同步文档 '{title}' 时发生异常: {e}")

    logger.info("同步任务完成！")

if __name__ == "__main__":
    # 可以通过命令行参数传入关键词
    test_keyword = "人工智能"
    if len(sys.argv) > 1:
        test_keyword = sys.argv[1]
    
    asyncio.run(sync_zhihu_to_ragflow(test_keyword))
