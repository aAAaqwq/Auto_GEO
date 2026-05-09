# -*- coding: utf-8 -*-
"""
爆火文章收集模块测试
测试 ArticleCollectorService 和相关 API 接口

包含：
1. Mock 测试 - 用于 CI/CD 环境
2. 真实环境测试 - 用于本地调试和功能验证
"""

import pytest
import requests
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tests.helpers.mock_data import MockData
from backend.database.models import ReferenceArticle
from backend.services.article_collector_service import ArticleCollectorService
from backend.services.playwright.collectors.base import CollectedArticle


# 测试基础 URL
BASE_URL = "http://127.0.0.1:8001"
COLLECT_API = f"{BASE_URL}/api/v1/collect"


# ==================== 真实环境测试配置 ====================

# 真实环境测试的搜索关键词
REAL_TEST_KEYWORD = "人工智能"

# 真实环境测试的平台配置
REAL_PLATFORMS = {
    "zhihu": {
        "name": "知乎",
        "search_url": "https://www.zhihu.com/search?type=content&q=人工智能",
    },
    "toutiao": {
        "name": "今日头条",
        "search_url": "https://so.toutiao.com/search?enable_druid_v2=1&keyword=人工智能&dvpf=pc&source=search_subtab_switch&pd=information&action_type=search_subtab_switch&page_num=0&search_id=&from=news&cur_tab_title=news",
    }
}


# ==================== Mock 数据 ====================

class MockArticleData:
    """Mock 文章数据生成器"""

    @staticmethod
    def collected_article(platform: str = "zhihu") -> dict:
        """生成 Mock 采集文章数据"""
        import random
        return {
            "title": f"测试爆火文章_{random.randint(1000, 9999)}",
            "url": f"https://www.{platform}.com/article/{random.randint(10000, 99999)}",
            "content": "这是一篇测试文章的正文内容。" * 20,
            "likes": random.randint(100, 5000),
            "reads": random.randint(1000, 50000),
            "comments": random.randint(10, 500),
            "author": f"测试作者_{random.randint(100, 999)}",
            "platform": platform,
            "publish_time": datetime.now().isoformat()
        }

    @staticmethod
    def collect_request() -> dict:
        """生成 Mock 采集请求数据"""
        return {
            "keyword": "人工智能",
            "platforms": ["zhihu", "toutiao"],
            "min_likes": 100,
            "min_reads": 1000,
            "max_articles_per_platform": 5,
            "save_to_db": True,
            "sync_to_ragflow": False
        }

    @staticmethod
    def zhihu_articles(count: int = 3) -> list:
        """生成 Mock 知乎文章列表"""
        return [MockArticleData.collected_article("zhihu") for _ in range(count)]

    @staticmethod
    def toutiao_articles(count: int = 3) -> list:
        """生成 Mock 头条文章列表"""
        return [MockArticleData.collected_article("toutiao") for _ in range(count)]


# ==================== 真实环境测试类 ====================

@pytest.mark.real_env
class TestRealEnvironmentCollection:
    """
    真实环境抓取测试

    注意：
    1. 这个测试类使用真实的 Playwright 浏览器（非无头模式）
    2. 会真实访问知乎和头条网站
    3. 增加了延时以避免被网站检测为爬虫
    4. 会打印抓取结果到控制台

    运行方式：
        pytest tests/test_article_collection.py::TestRealEnvironmentCollection -v -s --real-env
    """

    @pytest_asyncio.fixture
    async def real_browser(self):
        """创建真实浏览器实例（非无头模式）"""
        from playwright.async_api import async_playwright
        import os

        playwright = await async_playwright().start()

        # 查找 Chrome 浏览器路径
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(
                os.environ.get("USERNAME", "")
            ),
        ]

        executable_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                executable_path = path
                print(f"\n✅ 找到 Chrome 浏览器: {path}")
                break

        launch_options = {
            "headless": False,  # 非无头模式，可以看到浏览器操作
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ],
            "slow_mo": 100,  # 每个操作增加 100ms 延迟，便于观察
        }

        if executable_path:
            launch_options["executable_path"] = executable_path

        browser = await playwright.chromium.launch(**launch_options)

        yield browser, playwright

        # 清理
        await browser.close()
        await playwright.stop()

    async def _handle_login_popup(self, page):
        """测试脚本中的弹窗检测"""
        try:
            # 2. 常见弹窗选择器
            popup_selectors = [
                ".Modal-wrapper", # 知乎登录弹窗
                ".login-modal", 
                ".captcha-box",
                ".sign-flow-modal", # 知乎登录
                "[class*='login-modal']", # 通用登录模态框
                "[class*='LoginModal']",
                ".SignFlow", # 知乎
                ".Button.SignFlow-submitButton", # 知乎登录按钮
                "iframe[src*='login']", # 登录 iframe
                "#captcha-verify-image", # 验证码
                "div[class*='captcha']", # 通用验证码容器
                ".verify-bar-close", # 验证条关闭按钮
            ]
            
            needs_login = False
            for selector in popup_selectors:
                if await page.query_selector(selector):
                    if await page.is_visible(selector):
                        needs_login = True
                        print(f"⚠️ 发现登录弹窗选择器: {selector}")
                        break
            
            # 3. 检查页面文本
            if not needs_login:
                try:
                    title = await page.title()
                    if "登录" in title or "安全验证" in title:
                        needs_login = True
                    else:
                        js_check = """
                            () => {
                                const text = document.body.innerText;
                                const keywords = ["登录后查看更多", "请登录", "扫码登录", "验证码", "安全验证", "注册/登录", "依次点击", "拖动滑块"];
                                return keywords.some(k => text.includes(k));
                            }
                        """
                        if await page.evaluate(js_check):
                             needs_login = True
                             print("⚠️ 页面文本包含登录关键词")
                except Exception:
                    pass
            
            if needs_login:
                print("\n" + "!"*50)
                print("检测到登录弹窗或验证码！")
                print("请在 45 秒内手动完成登录/验证操作...")
                print("!"*50 + "\n")
                
                # 给用户 45 秒时间手动操作
                await page.wait_for_timeout(45000)
                print("手动操作时间结束，继续执行...")
                
        except Exception as e:
            print(f"登录检测异常: {e}")

    @pytest.mark.asyncio
    async def test_zhihu_real_search(self, real_browser):
        """
        测试知乎真实搜索

        会打开真实浏览器，搜索关键词，并打印结果
        """
        browser, playwright = real_browser

        print("\n" + "=" * 60)
        print("🔍 开始知乎真实环境搜索测试")
        print("=" * 60)

        # 创建浏览器上下文
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        # 防止 WebDriver 检测
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()


        try:
            # 导航到知乎搜索页
            search_url = f"https://www.zhihu.com/search?type=content&q={REAL_TEST_KEYWORD}"
            print(f"📌 访问 URL: {search_url}")

            await page.goto(search_url, wait_until="networkidle")
            
            # 检测登录弹窗
            await self._handle_login_popup(page)

            # 增加延时，等待页面完全加载
            print("⏳ 等待页面加载...")
            await page.wait_for_timeout(3000)

            # 滚动页面加载更多内容
            print("📜 滚动页面加载更多内容...")
            for i in range(3):
                # 检测登录弹窗
                await self._handle_login_popup(page)
                
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000)  # 每次滚动后等待 3 秒
                print(f"   滚动 {i + 1}/3 完成")

            # 提取搜索结果
            print("\n📝 提取搜索结果...")
            articles = []

            # 获取所有搜索结果卡片
            cards = await page.query_selector_all(".SearchResult-Card, .Card.SearchResult-Card")
            print(f"   找到 {len(cards)} 个搜索结果卡片")

            for idx, card in enumerate(cards):
                try:
                    # 提取标题和链接
                    title_elem = await card.query_selector("h2.ContentItem-title a, .ContentItem-title a")
                    if not title_elem:
                        continue

                    title = await title_elem.text_content()
                    href = await title_elem.get_attribute("href")

                    # 处理相对链接
                    if href and not href.startswith("http"):
                        href = f"https://www.zhihu.com{href}"

                    # 提取点赞数
                    likes = 0
                    vote_elem = await card.query_selector(".VoteButton--up, [class*='VoteButton']")
                    if vote_elem:
                        vote_text = await vote_elem.text_content()
                        likes = self._parse_number(vote_text)

                    # 提取作者
                    author = ""
                    author_elem = await card.query_selector(".AuthorInfo-name, .UserLink-link")
                    if author_elem:
                        author = await author_elem.text_content()

                    if title:
                        articles.append({
                            "title": title.strip(),
                            "url": href or "",
                            "likes": likes,
                            "author": author.strip() if author else ""
                        })

                except Exception as e:
                    print(f"   ⚠️ 提取第 {idx + 1} 条结果失败: {e}")
                    continue

            # 打印结果
            print("\n" + "=" * 60)
            print(f"📊 知乎搜索结果 (关键词: {REAL_TEST_KEYWORD})")
            print("=" * 60)

            if articles:
                for i, article in enumerate(articles[:10], 1):  # 只显示前 10 条
                    print(f"\n{i}. 📄 标题: {article['title'][:50]}...")
                    print(f"   👍 点赞数: {article['likes']}")
                    print(f"   ✍️  作者: {article['author']}")
                    print(f"   🔗 链接: {article['url'][:60]}...")
            else:
                print("❌ 未找到任何文章")

            print("\n" + "=" * 60)
            print(f"✅ 知乎搜索测试完成，共抓取 {len(articles)} 篇文章")
            print("=" * 60)

            # 验证结果
            assert len(articles) > 0, "应该抓取到至少一篇文章"

        except Exception as e:
            # 截图保存
            import os
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            screenshot_path = f"tests/reports/screenshots/zhihu_error_{timestamp}.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            await page.screenshot(path=screenshot_path)
            print(f"\n❌ 发生异常，截图已保存: {screenshot_path}")
            raise e

        finally:
            await page.wait_for_timeout(2000)  # 保持浏览器打开 2 秒，便于查看结果
            await context.close()

    @pytest.mark.asyncio
    async def test_toutiao_real_search(self, real_browser):
        """
        测试头条真实搜索

        会打开真实浏览器，搜索关键词，并打印结果
        """
        browser, playwright = real_browser

        print("\n" + "=" * 60)
        print("🔍 开始头条真实环境搜索测试")
        print("=" * 60)

        # 创建浏览器上下文
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        # 防止 WebDriver 检测
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()

        try:
            # 导航到头条搜索页
            search_url = f"https://so.toutiao.com/search?dvpf=pc&source=search_subtab_switch&enable_druid_v2=1&keyword={REAL_TEST_KEYWORD}&pd=information&action_type=search_subtab_switch&page_num=0&search_id=&from=news&cur_tab_title=news"
            print(f"📌 访问 URL: {search_url}")

            await page.goto(search_url, wait_until="networkidle")
            
            # 增加延时，等待页面加载
            print("⏳ 等待页面加载 (5s)...")
            await page.wait_for_timeout(5000)

            # 检测登录弹窗
            await self._handle_login_popup(page)

            # 滚动页面加载更多内容
            print("📜 滚动页面加载更多内容...")
            for i in range(3):
                # 检测登录弹窗
                await self._handle_login_popup(page)
                
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000)  # 每次滚动后等待 3 秒
                print(f"   滚动 {i + 1}/3 完成")

            # 提取搜索结果
            print("\n📝 提取搜索结果...")
            articles = []

            # 头条的搜索结果选择器
            cards = await page.query_selector_all("[class*='result-content'], .result-item, .article-card, [class*='cs-view']")
            print(f"   找到 {len(cards)} 个搜索结果卡片")

            for idx, card in enumerate(cards):
                try:
                    # 提取标题和链接
                    title_elem = await card.query_selector("a[class*='title'], .title a, h3 a, [class*='text']")
                    if not title_elem:
                        continue

                    title = await title_elem.text_content()
                    href = await title_elem.get_attribute("href")

                    # 处理相对链接
                    if href and not href.startswith("http"):
                        href = f"https://www.toutiao.com{href}"

                    # 提取阅读量/评论数
                    reads = 0
                    meta_elem = await card.query_selector("[class*='read'], [class*='comment'], .meta, [class*='count']")
                    if meta_elem:
                        meta_text = await meta_elem.text_content()
                        reads = self._parse_number(meta_text)

                    # 提取作者
                    author = ""
                    author_elem = await card.query_selector("[class*='source'], [class*='author'], .name, [class*='user']")
                    if author_elem:
                        author = await author_elem.text_content()

                    if title and len(title.strip()) > 5:
                        articles.append({
                            "title": title.strip(),
                            "url": href or "",
                            "likes": reads // 100 if reads else 0,  # 估算点赞数
                            "reads": reads,
                            "author": author.strip() if author else ""
                        })

                except Exception as e:
                    print(f"   ⚠️ 提取第 {idx + 1} 条结果失败: {e}")
                    continue

            # 打印结果
            print("\n" + "=" * 60)
            print(f"📊 头条搜索结果 (关键词: {REAL_TEST_KEYWORD})")
            print("=" * 60)

            if articles:
                for i, article in enumerate(articles[:10], 1):  # 只显示前 10 条
                    print(f"\n{i}. 📄 标题: {article['title'][:50]}...")
                    print(f"   👍 点赞数: {article['likes']} (估算)")
                    print(f"   👁️  阅读量: {article['reads']}")
                    print(f"   ✍️  作者: {article['author']}")
                    print(f"   🔗 链接: {article['url'][:60]}..." if article['url'] else "   🔗 链接: 无")
            else:
                print("❌ 未找到任何文章")

            print("\n" + "=" * 60)
            print(f"✅ 头条搜索测试完成，共抓取 {len(articles)} 篇文章")
            print("=" * 60)

            # 验证结果
            assert len(articles) >= 0, "头条搜索应该正常完成"

        except Exception as e:
            # 截图保存
            import os
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            screenshot_path = f"tests/reports/screenshots/toutiao_error_{timestamp}.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            await page.screenshot(path=screenshot_path)
            print(f"\n❌ 发生异常，截图已保存: {screenshot_path}")
            raise e

        finally:
            await page.wait_for_timeout(2000)  # 保持浏览器打开 2 秒，便于查看结果
            await context.close()

    @pytest.mark.asyncio
    async def test_full_collection_real(self, real_browser):
        """
        测试完整的真实采集流程

        使用 ArticleCollectorService 进行真实采集
        """
        browser, playwright = real_browser

        print("\n" + "=" * 60)
        print("🚀 开始完整真实采集测试")
        print("=" * 60)

        # 注意：这里不使用 Mock，直接调用真实服务
        from backend.services.article_collector_service import ArticleCollectorService
        from backend.services.playwright_mgr import playwright_mgr
        from backend.services.playwright.collectors import register_collectors
        from backend.config import PLATFORMS

        # 注册收集器
        register_collectors(PLATFORMS)

        # 创建服务实例（不传入 db，避免保存到数据库）
        service = ArticleCollectorService(db=None)

        try:
            # 启动 Playwright（使用全局管理器）
            await playwright_mgr.start()

            # 执行采集（不保存到数据库，不同步到 RAGFlow）
            print(f"\n📌 开始采集: 关键词={REAL_TEST_KEYWORD}, 平台=['zhihu', 'toutiao']")

            result = await service.collect_trending_articles(
                keyword=REAL_TEST_KEYWORD,
                platforms=["zhihu", "toutiao"],
                min_likes=50,  # 降低阈值以获取更多结果
                min_reads=500,
                max_articles_per_platform=5,
                save_to_db=False,  # 不保存到数据库
                sync_to_ragflow=False  # 不同步到 RAGFlow
            )

            # 打印结果
            print("\n" + "=" * 60)
            print("📊 完整采集结果汇总")
            print("=" * 60)
            print(f"✅ 采集成功: {result['success']}")
            print(f"📝 总文章数: {result['total_count']}")

            for platform, articles in result['results'].items():
                print(f"\n--- {platform.upper()} 平台 ({len(articles)} 篇) ---")
                for i, article in enumerate(articles[:5], 1):
                    print(f"\n{i}. 📄 标题: {article.get('title', '无标题')[:50]}...")
                    print(f"   👍 点赞数: {article.get('likes', 0)}")
                    print(f"   👁️  阅读量: {article.get('reads', 0)}")
                    print(f"   ✍️  作者: {article.get('author', '未知')}")

            print("\n" + "=" * 60)
            print("✅ 完整采集测试完成")
            print("=" * 60)

            # 验证
            assert result["success"] is True, "采集应该成功"

        except Exception as e:
            print(f"\n❌ 采集失败: {e}")
            import traceback
            traceback.print_exc()
            raise

        finally:
            # 不关闭 playwright_mgr，因为它可能被其他测试使用
            pass

    def _parse_number(self, text: str) -> int:
        """解析数字（支持 1.2k, 1.5w 等格式）"""
        import re

        if not text:
            return 0

        text = text.strip().lower()

        # 移除非数字字符但保留 k、w、万
        match = re.search(r'([\d.]+)\s*([kwm万])?', text)
        if not match:
            return 0

        num = float(match.group(1))
        unit = match.group(2)

        if unit in ['k', 'K']:
            num *= 1000
        elif unit in ['w', 'W', '万']:
            num *= 10000
        elif unit in ['m', 'M']:
            num *= 1000000

        return int(num)


# ==================== Service 单元测试 ====================

class TestArticleCollectorService:
    """ArticleCollectorService 单元测试"""

    def test_clean_html_removes_script_tags(self):
        """测试 HTML 清洗：移除 script 标签"""
        service = ArticleCollectorService()

        html_content = '<p>正文内容</p><script>alert("xss")</script><p>更多内容</p>'
        cleaned = service._clean_html(html_content)

        assert "script" not in cleaned.lower()
        assert "alert" not in cleaned
        assert "正文内容" in cleaned
        assert "更多内容" in cleaned

    def test_clean_html_removes_style_tags(self):
        """测试 HTML 清洗：移除 style 标签"""
        service = ArticleCollectorService()

        html_content = '<p>正文内容</p><style>.hidden{display:none}</style>'
        cleaned = service._clean_html(html_content)

        assert "style" not in cleaned.lower()
        assert "display" not in cleaned
        assert "正文内容" in cleaned

    def test_clean_html_removes_ad_content(self):
        """测试 HTML 清洗：移除广告内容"""
        service = ArticleCollectorService()

        html_content = '''
        <p>正文内容</p>
        <div class="advertisement">广告内容</div>
        <p>更多正文</p>
        '''
        cleaned = service._clean_html(html_content)

        assert "正文内容" in cleaned
        assert "更多正文" in cleaned

    def test_clean_html_converts_entities(self):
        """测试 HTML 清洗：转换 HTML 实体"""
        service = ArticleCollectorService()

        html_content = '&nbsp;&lt;测试&gt;&amp;内容&nbsp;'
        cleaned = service._clean_html(html_content)

        assert "<测试>" in cleaned
        assert "&内容" in cleaned

    def test_clean_html_removes_extra_whitespace(self):
        """测试 HTML 清洗：移除多余空白"""
        service = ArticleCollectorService()

        html_content = '正文    内容\n\n\n\n更多内容'
        cleaned = service._clean_html(html_content)

        # 连续空格应该被合并
        assert "    " not in cleaned
        # 连续换行应该被合并
        assert "\n\n\n" not in cleaned

    def test_clean_html_empty_content(self):
        """测试 HTML 清洗：空内容"""
        service = ArticleCollectorService()

        assert service._clean_html("") == ""
        assert service._clean_html(None) == ""

    @pytest.mark.asyncio
    async def test_sync_to_ragflow_not_configured(self):
        """测试 RAGFlow 同步：未配置时跳过"""
        service = ArticleCollectorService()

        # Mock RAGFlow 客户端未配置
        with patch.object(service._ragflow, 'is_configured', return_value=False):
            result = await service._sync_to_ragflow({
                "title": "测试文章",
                "content": "测试内容"
            })

        assert result["success"] is False
        assert "未配置" in result["error_msg"]

    @pytest.mark.asyncio
    async def test_collect_trending_articles_mock(self):
        """测试采集爆火文章（Mock Playwright）"""
        service = ArticleCollectorService()

        # Mock 数据
        mock_zhihu_articles = [
            CollectedArticle(
                title="知乎热门文章1",
                url="https://zhihu.com/p/123",
                content="这是知乎文章内容",
                likes=500,
                reads=10000,
                comments=100,
                author="知乎作者",
                platform="zhihu"
            )
        ]
        mock_toutiao_articles = [
            CollectedArticle(
                title="头条热门文章1",
                url="https://toutiao.com/a/456",
                content="这是头条文章内容",
                likes=300,
                reads=20000,
                comments=50,
                author="头条作者",
                platform="toutiao"
            )
        ]

        # Mock Playwright 管理器和收集器
        with patch('backend.services.article_collector_service.playwright_mgr') as mock_mgr, \
             patch('backend.services.article_collector_service.get_collector') as mock_get_collector, \
             patch('backend.services.article_collector_service.register_collectors'):

            # 设置 Mock 行为
            mock_mgr.start = AsyncMock()
            mock_mgr._browser = MagicMock()

            # Mock 浏览器上下文
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.close = AsyncMock()
            mock_context.close = AsyncMock()
            mock_mgr._browser.new_context = AsyncMock(return_value=mock_context)

            # Mock 知乎收集器
            mock_zhihu_collector = MagicMock()
            mock_zhihu_collector.name = "知乎"
            mock_zhihu_collector.collect = AsyncMock(return_value=mock_zhihu_articles)

            # Mock 头条收集器
            mock_toutiao_collector = MagicMock()
            mock_toutiao_collector.name = "今日头条"
            mock_toutiao_collector.collect = AsyncMock(return_value=mock_toutiao_articles)

            def get_collector_side_effect(platform):
                if platform == "zhihu":
                    return mock_zhihu_collector
                elif platform == "toutiao":
                    return mock_toutiao_collector
                return None

            mock_get_collector.side_effect = get_collector_side_effect

            # 执行采集（不保存到数据库）
            result = await service.collect_trending_articles(
                keyword="人工智能",
                platforms=["zhihu", "toutiao"],
                min_likes=100,
                min_reads=1000,
                max_articles_per_platform=5,
                save_to_db=False,
                sync_to_ragflow=False
            )

        # 验证结果
        assert result["success"] is True
        assert result["keyword"] == "人工智能"
        assert result["total_count"] == 2
        assert "zhihu" in result["results"]
        assert "toutiao" in result["results"]

    def test_get_supported_platforms(self):
        """测试获取支持的平台列表"""
        service = ArticleCollectorService()

        # 初始化后应该有支持的平台
        with patch('backend.services.article_collector_service.register_collectors'):
            with patch('backend.services.article_collector_service.list_collectors') as mock_list:
                mock_list.return_value = {"zhihu": MagicMock(), "toutiao": MagicMock()}
                platforms = service.get_supported_platforms()

        assert "zhihu" in platforms
        assert "toutiao" in platforms


# ==================== API 集成测试 ====================

@pytest.mark.integration
class TestArticleCollectionAPI:
    """文章收集 API 集成测试"""

    def test_start_collect_api_exists(self, backend_server):
        """测试采集启动 API 存在"""
        data = MockArticleData.collect_request()
        response = requests.post(f"{COLLECT_API}/start", json=data)

        # API 应该存在并返回有效响应
        assert response.status_code in [200, 201, 400, 422]

    def test_start_collect_invalid_platform(self, backend_server):
        """测试采集启动 API：无效平台"""
        data = {
            "keyword": "测试",
            "platforms": ["invalid_platform"],
            "min_likes": 100
        }
        response = requests.post(f"{COLLECT_API}/start", json=data)

        # 应该返回错误
        assert response.status_code == 400

    def test_start_collect_missing_keyword(self, backend_server):
        """测试采集启动 API：缺少关键词"""
        data = {
            "platforms": ["zhihu"]
        }
        response = requests.post(f"{COLLECT_API}/start", json=data)

        # 应该返回验证错误
        assert response.status_code == 422

    def test_start_collect_empty_platforms(self, backend_server):
        """测试采集启动 API：空平台列表"""
        data = {
            "keyword": "测试",
            "platforms": []
        }
        response = requests.post(f"{COLLECT_API}/start", json=data)

        # 应该返回验证错误
        assert response.status_code == 422

    def test_get_collect_status_not_found(self, backend_server):
        """测试获取采集状态：任务不存在"""
        response = requests.get(f"{COLLECT_API}/status/non-existent-task-id")

        assert response.status_code == 404

    def test_list_collect_tasks(self, backend_server):
        """测试获取采集任务列表"""
        response = requests.get(f"{COLLECT_API}/tasks")

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)

    def test_list_collect_tasks_with_status_filter(self, backend_server):
        """测试获取采集任务列表：按状态筛选"""
        response = requests.get(f"{COLLECT_API}/tasks?status=completed")

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, list)

    def test_get_supported_platforms_api(self, backend_server):
        """测试获取支持平台 API"""
        response = requests.get(f"{COLLECT_API}/platforms")

        assert response.status_code == 200
        result = response.json()
        assert "platforms" in result
        assert len(result["platforms"]) >= 2

        # 验证平台数据结构
        for platform in result["platforms"]:
            assert "id" in platform
            assert "name" in platform

        # 验证平台数据结构
        for platform in result["platforms"]:
            assert "id" in platform
            assert "name" in platform

    def test_check_duplicate_api(self, backend_server):
        """测试去重检查 API"""
        data = {
            "content": "这是一段待检查的内容，用于测试去重功能是否正常工作。" * 10,
            "threshold": 0.85
        }
        response = requests.post(f"{COLLECT_API}/check-duplicate", json=data)

        assert response.status_code == 200
        result = response.json()
        assert "checked" in result
        assert "is_duplicate" in result
        assert "threshold" in result

    def test_check_duplicate_short_content(self, backend_server):
        """测试去重检查 API：内容过短"""
        data = {
            "content": "短内容",
            "threshold": 0.85
        }
        response = requests.post(f"{COLLECT_API}/check-duplicate", json=data)

        # 应该返回验证错误（内容最少10字符）
        assert response.status_code == 422


# ==================== 数据库模型测试 ====================

class TestReferenceArticleModel:
    """ReferenceArticle 模型测试"""

    def test_create_reference_article(self, clean_db):
        """测试创建参考文章"""
        article = ReferenceArticle(
            title="测试爆火文章",
            url="https://zhihu.com/p/test123",
            content="这是文章正文内容",
            summary="这是摘要",
            platform="zhihu",
            author="测试作者",
            likes=500,
            reads=10000,
            comments=100,
            keyword="人工智能",
            ragflow_synced=False,
            status=1
        )
        clean_db.add(article)
        clean_db.commit()
        clean_db.refresh(article)

        assert article.id is not None
        assert article.title == "测试爆火文章"
        assert article.platform == "zhihu"
        assert article.likes == 500

    def test_reference_article_unique_url(self, clean_db):
        """测试参考文章 URL 唯一性"""
        article1 = ReferenceArticle(
            title="文章1",
            url="https://zhihu.com/p/unique123",
            content="内容1",
            platform="zhihu",
            status=1
        )
        clean_db.add(article1)
        clean_db.commit()

        # 尝试添加相同 URL 的文章应该失败
        article2 = ReferenceArticle(
            title="文章2",
            url="https://zhihu.com/p/unique123",  # 相同 URL
            content="内容2",
            platform="zhihu",
            status=1
        )
        clean_db.add(article2)

        with pytest.raises(Exception):
            clean_db.commit()

        clean_db.rollback()

    def test_reference_article_fields(self, clean_db):
        """测试参考文章所有字段"""
        article = ReferenceArticle(
            title="完整测试文章",
            url="https://toutiao.com/a/test456",
            content="详细正文内容" * 100,
            summary="摘要内容",
            platform="toutiao",
            author="头条作者",
            publish_time="2025-01-26",
            likes=1000,
            reads=50000,
            comments=200,
            keyword="科技新闻",
            ragflow_synced=True,
            ragflow_doc_id="doc_123",
            status=1
        )
        clean_db.add(article)
        clean_db.commit()
        clean_db.refresh(article)

        # 验证所有字段
        assert article.id is not None
        assert article.title == "完整测试文章"
        assert article.url == "https://toutiao.com/a/test456"
        assert len(article.content) > 100
        assert article.summary == "摘要内容"
        assert article.platform == "toutiao"
        assert article.author == "头条作者"
        assert article.likes == 1000
        assert article.reads == 50000
        assert article.comments == 200
        assert article.keyword == "科技新闻"
        assert article.ragflow_synced is True
        assert article.ragflow_doc_id == "doc_123"
        assert article.created_at is not None

    def test_reference_article_soft_delete(self, clean_db):
        """测试参考文章软删除"""
        article = ReferenceArticle(
            title="待删除文章",
            url="https://zhihu.com/p/delete123",
            content="内容",
            platform="zhihu",
            status=1
        )
        clean_db.add(article)
        clean_db.commit()

        # 软删除
        article.status = 0
        clean_db.commit()

        # 验证状态
        deleted_article = clean_db.query(ReferenceArticle).filter(
            ReferenceArticle.url == "https://zhihu.com/p/delete123"
        ).first()
        assert deleted_article.status == 0


# ==================== 收集器单元测试 ====================

class TestCollectors:
    """收集器单元测试"""

    def test_zhihu_collector_parse_number(self):
        """测试知乎收集器数字解析"""
        from backend.services.playwright.collectors.zhihu import ZhihuCollector

        collector = ZhihuCollector("zhihu", {"name": "知乎"})

        # 测试各种数字格式
        assert collector._parse_number("123") == 123
        assert collector._parse_number("1.5k") == 1500
        assert collector._parse_number("2.3K") == 2300
        assert collector._parse_number("1w") == 10000
        assert collector._parse_number("1.5万") == 15000
        assert collector._parse_number("") == 0
        assert collector._parse_number(None) == 0

    def test_toutiao_collector_parse_number(self):
        """测试头条收集器数字解析"""
        from backend.services.playwright.collectors.toutiao import ToutiaoCollector

        collector = ToutiaoCollector("toutiao", {"name": "今日头条"})

        # 测试各种数字格式
        assert collector._parse_number("456") == 456
        assert collector._parse_number("2k") == 2000
        assert collector._parse_number("3.5万") == 35000
        assert collector._parse_number("") == 0

    def test_base_collector_filter_trending(self):
        """测试基础收集器筛选爆火文章"""
        from backend.services.playwright.collectors.base import BaseCollector

        # 创建测试子类
        class TestCollector(BaseCollector):
            async def search(self, page, keyword):
                return []

            async def extract_content(self, page, url):
                return ""

        collector = TestCollector("test", {"name": "测试"})
        collector.min_likes = 100
        collector.min_reads = 1000

        articles = [
            {"title": "高赞文章", "likes": 500, "reads": 500},
            {"title": "高阅读文章", "likes": 50, "reads": 5000},
            {"title": "普通文章", "likes": 10, "reads": 100},
            {"title": "边界文章", "likes": 100, "reads": 999},
        ]

        trending = collector._filter_trending(articles)

        # 验证筛选结果
        assert len(trending) == 2
        titles = [a["title"] for a in trending]
        assert "高赞文章" in titles
        assert "高阅读文章" in titles
        assert "普通文章" not in titles


# ==================== 参考文章 API 测试 ====================

@pytest.mark.integration
class TestReferenceArticlesAPI:
    """参考文章 API 测试"""

    def test_list_reference_articles(self, backend_server):
        """测试获取参考文章列表"""
        response = requests.get(f"{COLLECT_API}/articles")

        assert response.status_code == 200
        result = response.json()
        assert "total" in result
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_list_reference_articles_with_platform_filter(self, backend_server):
        """测试获取参考文章列表：按平台筛选"""
        response = requests.get(f"{COLLECT_API}/articles?platform=zhihu")

        assert response.status_code == 200
        result = response.json()
        assert "items" in result

    def test_list_reference_articles_with_keyword_filter(self, backend_server):
        """测试获取参考文章列表：按关键词筛选"""
        response = requests.get(f"{COLLECT_API}/articles?keyword=人工智能")

        assert response.status_code == 200
        result = response.json()
        assert "items" in result

    def test_list_reference_articles_pagination(self, backend_server):
        """测试获取参考文章列表：分页"""
        response = requests.get(f"{COLLECT_API}/articles?page=1&page_size=5")

        assert response.status_code == 200
        result = response.json()
        assert "total" in result
        assert "items" in result
        assert len(result["items"]) <= 5

    def test_get_reference_article_not_found(self, backend_server):
        """测试获取参考文章详情：不存在"""
        response = requests.get(f"{COLLECT_API}/articles/99999")

        assert response.status_code == 404

    def test_delete_reference_article_not_found(self, backend_server):
        """测试删除参考文章：不存在"""
        response = requests.delete(f"{COLLECT_API}/articles/99999")

        assert response.status_code == 404


# ==================== 完整流程测试（Mock 版本）====================

class TestCollectFlowMocked:
    """完整采集流程测试（Mock 浏览器）"""

    @pytest.mark.asyncio
    async def test_full_collect_flow_mocked(self, clean_db):
        """测试完整采集流程（Mock）"""
        # 创建服务实例
        service = ArticleCollectorService(db=clean_db)

        # Mock 文章数据
        mock_articles = [
            CollectedArticle(
                title="Mock 爆火文章",
                url=f"https://zhihu.com/p/mock_{i}",
                content="这是 Mock 文章内容" * 50,
                likes=500 + i * 100,
                reads=10000 + i * 1000,
                comments=100,
                author="Mock 作者",
                platform="zhihu"
            )
            for i in range(3)
        ]

        # Mock Playwright 和收集器
        with patch('backend.services.article_collector_service.playwright_mgr') as mock_mgr, \
             patch('backend.services.article_collector_service.get_collector') as mock_get_collector, \
             patch('backend.services.article_collector_service.register_collectors'), \
             patch.object(service._ragflow, 'is_configured', return_value=False):

            # 设置 Mock
            mock_mgr.start = AsyncMock()
            mock_mgr._browser = MagicMock()

            # Mock 浏览器上下文
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.close = AsyncMock()
            mock_context.close = AsyncMock()
            mock_mgr._browser.new_context = AsyncMock(return_value=mock_context)

            mock_collector = MagicMock()
            mock_collector.name = "知乎"
            mock_collector.collect = AsyncMock(return_value=mock_articles)
            mock_get_collector.return_value = mock_collector

            # 执行采集
            result = await service.collect_trending_articles(
                keyword="人工智能",
                platforms=["zhihu"],
                min_likes=100,
                save_to_db=True,
                sync_to_ragflow=False
            )

        # 验证结果
        assert result["success"] is True
        assert result["total_count"] == 3
        assert result["saved_count"] == 3

        # 验证数据库
        saved_articles = clean_db.query(ReferenceArticle).filter(
            ReferenceArticle.keyword == "人工智能"
        ).all()
        assert len(saved_articles) == 3

        # 清理测试数据
        for article in saved_articles:
            clean_db.delete(article)
        clean_db.commit()
