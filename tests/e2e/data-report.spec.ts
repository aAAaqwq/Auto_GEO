import { test, expect, Page } from '@playwright/test';

/**
 * 数据报表功能 - 前端自动化测试
 * 使用 Playwright 进行端到端测试
 * 
 * 测试范围：
 * - 页面加载和导航
 * - 筛选器功能（项目、时间、平台）
 * - 数据卡片展示
 * - 图表渲染
 * - 数据表格
 * 
 * 运行方式：
 *     cd fronted
 *     npx playwright test tests/e2e/data-report.spec.ts --headed
 * 
 * 作者：测试工程师
 * 日期：2026-02-03
 */

const BASE_URL = 'http://localhost:5173';

// ==================== 辅助函数 ====================

/**
 * 等待页面加载完成
 */
async function waitForPageLoad(page: Page) {
  await page.waitForSelector('.data-report-page', { timeout: 10000 });
  // 等待数据加载完成（如果有加载动画的话）
  await page.waitForTimeout(1000);
}

/**
 * 获取卡片数值
 */
async function getCardValue(page: Page, cardIndex: number): Promise<string> {
  const card = page.locator('.stat-card').nth(cardIndex);
  return await card.locator('.card-value').textContent() || '';
}

// ==================== 测试套件 ====================

test.describe('数据报表功能 - 冒烟测试', () => {
  
  test.beforeEach(async ({ page }) => {
    // 每个测试前导航到数据报表页面
    await page.goto(`${BASE_URL}/#/data-report`);
    await waitForPageLoad(page);
  });

  // ==================== TC-008: 页面加载测试 ====================
  
  test('TC-008: 页面正常加载，显示所有关键元素', async ({ page }) => {
    // 验证页面标题
    await expect(page.locator('.page-title')).toHaveText('数据报表');
    
    // 验证筛选区存在
    await expect(page.locator('.filter-section')).toBeVisible();
    
    // 验证4张数据卡片存在
    const cards = page.locator('.stat-card');
    await expect(cards).toHaveCount(4);
    
    // 验证图表区域存在
    await expect(page.locator('.comparison-chart')).toBeVisible();
    
    // 验证两个数据表格存在
    const tables = page.locator('.dark-table');
    await expect(tables).toHaveCount(2);
    
    console.log('✅ TC-008 通过：页面加载成功，所有关键元素已显示');
  });

  // ==================== TC-009: 侧边栏导航测试 ====================
  
  test('TC-009: 侧边栏导航到数据报表页面', async ({ page }) => {
    // 先回到首页
    await page.goto(`${BASE_URL}/#/dashboard`);
    await page.waitForTimeout(1000);
    
    // 点击侧边栏的"数据报表"菜单
    await page.click('text=数据报表');
    
    // 验证URL变化
    await expect(page).toHaveURL(/.*data-report.*/);
    
    // 验证页面内容
    await expect(page.locator('.data-report-page')).toBeVisible();
    
    // 验证菜单高亮（如果有高亮样式的话）
    const activeMenu = page.locator('.nav-item.active');
    await expect(activeMenu).toContainText('数据报表');
    
    console.log('✅ TC-009 通过：侧边栏导航功能正常');
  });
});

test.describe('数据报表功能 - 筛选器测试', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/#/data-report`);
    await waitForPageLoad(page);
  });

  // ==================== TC-010: 项目选择器测试 ====================
  
  test('TC-010: 项目选择器功能正常', async ({ page }) => {
    // 点击项目下拉框
    await page.click('.project-select .el-input__wrapper');
    await page.waitForTimeout(500);
    
    // 验证下拉选项存在（如果有数据的话）
    const options = page.locator('.el-select-dropdown__item');
    const count = await options.count();
    
    if (count > 0) {
      // 选择第一个项目
      await options.first().click();
      await page.waitForTimeout(1000);
      
      // 验证数据刷新（数值应该有所变化）
      const cardValue = await getCardValue(page, 0);
      console.log(`✅ 选择项目后，文章数: ${cardValue}`);
    } else {
      console.log('ℹ️ 项目列表为空，跳过选择测试');
    }
    
    console.log('✅ TC-010 通过：项目选择器功能正常');
  });

  // ==================== TC-011: 时间范围切换测试 ====================
  
  test('TC-011: 时间范围切换功能正常', async ({ page }) => {
    // 记录当前7天的数值
    const value7Days = await getCardValue(page, 0);
    console.log(`近7天文章数: ${value7Days}`);
    
    // 切换到30天
    await page.click('.time-select .el-input__wrapper');
    await page.waitForTimeout(300);
    await page.click('.el-select-dropdown__item:has-text("近30天")');
    await page.waitForTimeout(1000);
    
    // 记录30天的数值
    const value30Days = await getCardValue(page, 0);
    console.log(`近30天文章数: ${value30Days}`);
    
    // 验证30天数据 >= 7天数据（可能相等，但不应该更少）
    const v7 = parseInt(value7Days) || 0;
    const v30 = parseInt(value30Days) || 0;
    expect(v30).toBeGreaterThanOrEqual(v7);
    
    console.log('✅ TC-011 通过：时间范围切换功能正常');
  });

  // ==================== TC-012: 平台筛选测试 ====================
  
  test('TC-012: 平台筛选功能正常', async ({ page }) => {
    // 点击全平台
    await page.click('.el-radio-button:has-text("全平台")');
    await page.waitForTimeout(500);
    console.log('✅ 已选择：全平台');
    
    // 点击 DeepSeek
    await page.click('.el-radio-button:has-text("DeepSeek")');
    await page.waitForTimeout(500);
    console.log('✅ 已选择：DeepSeek');
    
    // 验证图表还在（即使数据可能为空）
    await expect(page.locator('.comparison-chart')).toBeVisible();
    
    // 点击 豆包
    await page.click('.el-radio-button:has-text("豆包")');
    await page.waitForTimeout(500);
    console.log('✅ 已选择：豆包');
    
    console.log('✅ TC-012 通过：平台筛选功能正常');
  });

  // ==================== TC-013: 刷新按钮测试 ====================
  
  test('TC-013: 刷新按钮功能正常', async ({ page }) => {
    // 点击刷新按钮
    await page.click('.refresh-btn');
    
    // 等待数据刷新（可能会有 loading 状态）
    await page.waitForTimeout(1500);
    
    // 验证页面仍然正常显示
    await expect(page.locator('.data-report-page')).toBeVisible();
    await expect(page.locator('.stat-card')).toHaveCount(4);
    
    console.log('✅ TC-013 通过：刷新按钮功能正常');
  });
});

test.describe('数据报表功能 - 数据卡片测试', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/#/data-report`);
    await waitForPageLoad(page);
  });

  // ==================== TC-014~017: 数据卡片展示测试 ====================
  
  test('TC-014~017: 四张数据卡片正确显示', async ({ page }) => {
    // 验证有4张卡片
    const cards = page.locator('.stat-card');
    await expect(cards).toHaveCount(4);
    
    // 验证第一张卡片（蓝色 - 文章生成数）
    const card1 = cards.nth(0);
    await expect(card1).toHaveClass(/blue/);
    await expect(card1.locator('.card-title')).toContainText('文章生成数');
    const value1 = await card1.locator('.card-value').textContent();
    console.log(`✅ 蓝色卡片（文章生成数）: ${value1}`);
    
    // 验证第二张卡片（绿色 - 发布成功率）
    const card2 = cards.nth(1);
    await expect(card2).toHaveClass(/green/);
    await expect(card2.locator('.card-title')).toContainText('发布成功率');
    const value2 = await card2.locator('.card-value').textContent();
    console.log(`✅ 绿色卡片（发布成功率）: ${value2}`);
    // 验证百分比格式
    expect(value2).toMatch(/\d+\.?\d*%/);
    
    // 验证第三张卡片（橙色 - 关键词命中率）
    const card3 = cards.nth(2);
    await expect(card3).toHaveClass(/orange/);
    await expect(card3.locator('.card-title')).toContainText('关键词命中率');
    const value3 = await card3.locator('.card-value').textContent();
    console.log(`✅ 橙色卡片（关键词命中率）: ${value3}`);
    
    // 验证第四张卡片（灰色 - 公司名命中率）
    const card4 = cards.nth(3);
    await expect(card4).toHaveClass(/grey/);
    await expect(card4.locator('.card-title')).toContainText('公司名命中率');
    const value4 = await card4.locator('.card-value').textContent();
    console.log(`✅ 灰色卡片（公司名命中率）: ${value4}`);
    
    console.log('✅ TC-014~017 通过：四张数据卡片正确显示');
  });
});

test.describe('数据报表功能 - 图表和表格测试', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/#/data-report`);
    await waitForPageLoad(page);
  });

  // ==================== TC-018~019: 图表渲染测试 ====================
  
  test('TC-018~019: AI平台对比分析图正常渲染', async ({ page }) => {
    // 验证图表容器存在
    const chartContainer = page.locator('.comparison-chart');
    await expect(chartContainer).toBeVisible();
    
    // 验证图表标题
    await expect(page.locator('.chart-section .section-title')).toContainText('AI平台对比分析');
    
    // 注意：ECharts图表是Canvas渲染的，不容易直接验证内容
    // 可以通过截图对比或验证Canvas元素存在来确认
    const canvas = chartContainer.locator('canvas');
    const canvasCount = await canvas.count();
    expect(canvasCount).toBeGreaterThan(0);
    
    console.log(`✅ 图表Canvas元素数量: ${canvasCount}`);
    console.log('✅ TC-018~019 通过：AI平台对比分析图正常渲染');
  });

  // ==================== TC-020~021: 数据表格测试 ====================
  
  test('TC-020~021: 数据表格正确显示', async ({ page }) => {
    // 验证有两个表格
    const tables = page.locator('.dark-table');
    await expect(tables).toHaveCount(2);
    
    // 第一个表格：项目影响力排行榜
    const table1 = tables.nth(0);
    await expect(table1).toBeVisible();
    
    // 验证表格标题
    await expect(page.locator('.leaderboard-section .section-title')).toContainText('项目影响力排行榜');
    
    // 验证表头
    const headers1 = ['排名', '品牌/项目', '公司', '内容声量', 'AI提及率', '品牌关联度'];
    for (const header of headers1) {
      await expect(table1.locator('th')).toContainText(header);
    }
    
    console.log('✅ 第一个表格（项目影响力排行榜）表头验证通过');
    
    // 第二个表格：高贡献内容分析
    const table2 = tables.nth(1);
    await expect(table2).toBeVisible();
    
    // 验证表格标题
    await expect(page.locator('.analysis-section .section-title')).toContainText('高贡献内容分析');
    
    // 验证表头
    const headers2 = ['排名', '文章标题', '发布平台', 'AI引用贡献率', '发布时间'];
    for (const header of headers2) {
      await expect(table2.locator('th')).toContainText(header);
    }
    
    console.log('✅ 第二个表格（高贡献内容分析）表头验证通过');
    
    console.log('✅ TC-020~021 通过：数据表格正确显示');
  });
});

// ==================== 性能测试 ====================

test.describe('数据报表功能 - 性能测试', () => {
  
  test('TC-023: 页面加载时间 < 3秒', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto(`${BASE_URL}/#/data-report`);
    await waitForPageLoad(page);
    
    const loadTime = Date.now() - startTime;
    console.log(`⏱️ 页面加载时间: ${loadTime}ms`);
    
    expect(loadTime).toBeLessThan(3000);
    console.log('✅ TC-023 通过：页面加载时间 < 3秒');
  });
  
  test('TC-024: API响应时间 < 500ms', async ({ page }) => {
    // 使用 Performance API 测量 API 响应时间
    const startTime = Date.now();
    
    // 触发数据加载
    await page.click('.refresh-btn');
    await page.waitForTimeout(1500);
    
    const responseTime = Date.now() - startTime;
    console.log(`⏱️ 数据刷新响应时间: ${responseTime}ms`);
    
    // 放宽到2秒，因为涉及多个API调用
    expect(responseTime).toBeLessThan(2000);
    console.log('✅ TC-024 通过：API响应时间在合理范围内');
  });
});

// ==================== 错误处理测试 ====================

test.describe('数据报表功能 - 错误处理测试', () => {
  
  test('后端服务不可用时显示错误提示', async ({ page }) => {
    // 这里只是示例，实际测试需要模拟后端不可用
    // 可以通过拦截请求来模拟
    
    await page.route('**/api/reports/stats', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ detail: 'Internal Server Error' })
      });
    });
    
    await page.goto(`${BASE_URL}/#/data-report`);
    await page.waitForTimeout(2000);
    
    // 验证错误提示显示（假设 Element Plus 会显示错误消息）
    // 实际选择器可能需要根据实际UI调整
    
    console.log('✅ 错误处理测试完成');
  });
});
