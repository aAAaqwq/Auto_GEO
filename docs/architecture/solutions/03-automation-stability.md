# 卡点3: 自动化程序执行稳定性

> 类型: 技术方案文档 (PRD)
> 优先级: P1
> 预估工时: 2周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

当前自动化流程的可靠性直接影响用户体验:

| 风险 | 影响 | 概率 | 当前缓解 |
|------|------|------|---------|
| Playwright崩溃 | 发布任务中断 | 高 | 无 |
| 浏览器内存泄漏 | 服务器OOM | 中 | 无 |
| 网络超时 | 任务卡死 | 中 | 部分超时 |
| n8n工作流失败 | AI生成中断 | 中 | 无重试 |
| RAGFlow不可用 | 知识检索失败 | 低 | 无 |

### 1.2 核心问题

自动化流程缺乏**任务状态机**、**断点续跑**、**资源隔离**和**健康探针**机制。

---

## 2. 技术架构

### 2.1 目标架构

```
                    ┌──────────────┐
                    │   任务调度器   │ (APScheduler)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   任务队列     │ (内存队列 + DB持久化)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │ Worker 1  │ │Worker 2│ │ Worker 3 │  (最多3并发)
        │ Playwright│ │Publish │ │  AI Gen  │
        └─────┬─────┘ └───┬────┘ └────┬─────┘
              │            │            │
        ┌─────▼────────────▼────────────▼─────┐
        │           状态持久化 + 错误恢复        │
        └──────────────────────────────────────┘
```

---

## 3. 详细设计

### 3.1 任务状态机

```
pending → queued → running → success
                   ↓            ↑
                failed ──→ retrying (max 3次)
                   ↓
               cancelled / dead_letter
```

### 3.2 数据库变更

```python
# models.py — 任务队列表

class TaskQueue(Base):
    """持久化任务队列"""
    __tablename__ = "task_queue"
    
    id = Column(Integer, primary_key=True)
    task_type = Column(String(50))        # "publish" / "generate" / "index_check"
    status = Column(String(20), default="pending")  # pending/queued/running/success/failed/retrying
    priority = Column(Integer, default=5) # 1(最高)-10(最低)
    payload = Column(Text)                # JSON: 任务参数
    result = Column(Text, nullable=True)  # JSON: 执行结果
    error_msg = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    worker_id = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # 断点续跑
    checkpoint = Column(Text, nullable=True)  # JSON: 执行进度快照
```

### 3.3 任务调度器

```python
# backend/services/task_scheduler.py (新建 ~250行)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

class TaskScheduler:
    """任务调度器"""
    
    MAX_CONCURRENT = 3
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running_tasks = {}  # task_id → asyncio.Task
    
    async def submit(self, task_type: str, payload: dict, priority: int = 5):
        """提交任务到队列"""
        task = TaskQueue(
            task_type=task_type,
            payload=json.dumps(payload),
            priority=priority,
            status="pending"
        )
        self.db.add(task)
        self.db.commit()
        return task.id
    
    async def _worker_loop(self):
        """Worker循环: 从队列取任务执行"""
        while True:
            # 获取下一个待执行任务 (按优先级)
            task = self._next_pending_task()
            if not task:
                await asyncio.sleep(5)
                continue
            
            if len(self._running_tasks) >= self.MAX_CONCURRENT:
                await asyncio.sleep(2)
                continue
            
            # 启动任务
            task.status = "running"
            task.started_at = datetime.now()
            self.db.commit()
            
            coro = self._execute_task(task)
            self._running_tasks[task.id] = asyncio.create_task(coro)
    
    async def _execute_task(self, task: TaskQueue):
        """执行单个任务，含重试和断点续跑"""
        try:
            if task.task_type == "publish":
                result = await self._execute_publish(task)
            elif task.task_type == "generate":
                result = await self._execute_generate(task)
            # ...
            
            task.status = "success"
            task.result = json.dumps(result)
            
        except Exception as e:
            task.error_msg = str(e)
            if task.retry_count < task.max_retries:
                task.status = "retrying"
                task.retry_count += 1
                # 指数退避
                delay = 2 ** task.retry_count * 60  # 2min, 4min, 8min
                await asyncio.sleep(delay)
                self._enqueue_retry(task)
            else:
                task.status = "failed"
        finally:
            task.completed_at = datetime.now()
            self.db.commit()
            self._running_tasks.pop(task.id, None)
    
    async def _execute_publish(self, task: TaskQueue):
        """发布任务执行，支持断点续跑"""
        payload = json.loads(task.payload)
        checkpoint = json.loads(task.checkpoint) if task.checkpoint else {}
        
        # 如果有checkpoint，从断点恢复
        start_platform = checkpoint.get("current_platform", 0)
        
        # ... 执行发布逻辑 ...
        
        # 更新checkpoint
        task.checkpoint = json.dumps({"current_platform": i})
        self.db.commit()
```

### 3.4 Playwright健康探针

```python
# backend/services/browser_health.py (新建 ~80行)

class BrowserHealthMonitor:
    """浏览器健康监控"""
    
    async def check(self, browser) -> dict:
        """检查浏览器实例健康状态"""
        checks = {
            "is_connected": browser.is_connected(),
            "memory_mb": await self._get_memory(browser),
            "context_count": len(browser.contexts),
        }
        checks["healthy"] = (
            checks["is_connected"] and 
            checks["memory_mb"] < 2048  # 超过2GB认为不健康
        )
        return checks
    
    async def auto_restart(self, playwright_mgr):
        """不健康时自动重启"""
        health = await self.check(playwright_mgr._browser)
        if not health["healthy"]:
            logger.warning(f"浏览器不健康: {health}, 执行重启")
            await playwright_mgr.stop()
            await playwright_mgr.start()
```

---

## 4. 测试方案

1. **崩溃恢复测试**: 模拟Playwright崩溃，验证任务自动重试
2. **内存泄漏测试**: 连续运行100个任务，监控内存增长
3. **并发测试**: 3个Worker同时执行不同类型任务
4. **断点续跑测试**: 模拟在发布第2个平台时崩溃，验证从断点恢复

---

## 5. 权威参考文献

1. **APScheduler Documentation (2025).** "Advanced Python Scheduler — Task Queuing and State Management."
   - Python任务调度框架，支持持久化、重试、并发控制

2. **Microsoft Playwright Team (2025).** "Browser Context Management Best Practices."
   - 浏览器资源管理指南，推荐单实例内存上限2GB，超时自动关闭

3. **Kreps, J. (2019).** "The Log: What every software engineer should know about real-time data." *LinkedIn Engineering*.
   - 任务队列设计原则：持久化、重试、幂等性

4. **Nygard, M. T. (2018).** "Release It! Design and Deploy Production-Ready Software." *Pragmatic Bookshelf*, 2nd Edition.
   - 生产环境稳定性设计模式：断路器、超时、重试、舱壁

5. **RabbitMQ Team (2025).** "Reliability Guide — Message Acknowledgement and Redelivery."
   - 消息队列可靠性最佳实践，重试策略和死信队列设计

6. **Kubernetes Documentation (2025).** "Liveness and Readiness Probes."
   - 健康探针设计模式，适用于进程级健康监控
