/**
 * 本地浏览器桥接服务管理器
 * 我用这个来管理本地浏览器桥接服务，支持授权和发布操作！
 */

import { spawn, ChildProcess, execSync } from 'child_process'
import { join, dirname } from 'path'
import * as os from 'os'
import { app } from 'electron'

// 浏览器桥接配置
const BRIDGE_CONFIG = {
  // 桥接服务脚本目录
  get bridgeDir(): string {
    const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged
    if (isDev) {
      const currentDir = __dirname
      const rootDir = join(currentDir, '../../../..')
      return join(rootDir, 'backend')
    } else {
      return join(process.resourcesPath, 'backend')
    }
  },

  // Python 解释器路径
  get pythonPath(): string {
    return os.platform() === 'win32' ? 'python' : 'python3'
  },

  // 桥接服务脚本
  bridgeScript: 'services/browser_bridge_server.py',

  // CDP 端口
  cdpPort: 9222,

  // 健康检查 URL（桥接服务启动后检查）
  get healthUrl(): string {
    return `http://127.0.0.1:9222`
  }
}

// 桥接服务状态
export type BridgeStatus = 'stopped' | 'starting' | 'running' | 'error'

/**
 * 检查 Python 是否可用
 */
function checkPython(): boolean {
  try {
    const pythonCmd = os.platform() === 'win32' ? 'python' : 'python3'
    execSync(`${pythonCmd} --version`, { encoding: 'utf8', windowsHide: true })
    return true
  } catch {
    return false
  }
}

/**
 * 桥接服务管理器类
 */
class BrowserBridgeManager {
  private process: ChildProcess | null = null
  private status: BridgeStatus = 'stopped'
  private healthCheckTimer: NodeJS.Timeout | null = null
  private startupTimer: NodeJS.Timeout | null = null
  private restartCount = 0
  private maxRestarts = 3

  /**
   * 启动浏览器桥接服务
   */
  async start(): Promise<boolean> {
    if (this.status === 'running' || this.status === 'starting') {
      console.log('[BrowserBridge] 桥接服务已在运行或启动中')
      return true
    }

    // 检查 Python
    if (!checkPython()) {
      console.error('[BrowserBridge] ❌ Python 不可用！请确保已安装 Python 3.10+')
      this.status = 'error'
      return false
    }

    console.log('[BrowserBridge] 🚀 正在启动本地浏览器桥接服务...')
    this.status = 'starting'

    try {
      // 检查桥接服务脚本是否存在
      const scriptPath = join(BRIDGE_CONFIG.bridgeDir, BRIDGE_CONFIG.bridgeScript)

      // 准备启动参数
      const pythonExe = BRIDGE_CONFIG.pythonPath
      const bridgeDir = BRIDGE_CONFIG.bridgeDir
      const projectRoot = join(bridgeDir, '..')

      console.log('[BrowserBridge] 📂 桥接服务目录:', bridgeDir)
      console.log('[BrowserBridge] 🐍 Python 命令:', pythonExe)

      // 启动 Python 桥接服务进程
      this.process = spawn(pythonExe, ['-c', `
import sys
sys.path.insert(0, '${projectRoot.replace(/\\/g, '/')}')
from backend.services.local_browser_bridge import local_browser_bridge
import asyncio

async def main():
    result = await local_browser_bridge.start(headless=False, use_cdp=True, cdp_port=${BRIDGE_CONFIG.cdpPort})
    if result['success']:
        print('Bridge started, CDP:', result.get('cdp_url'))
        # 保持运行
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await local_browser_bridge.stop()
    else:
        print('Bridge failed:', result.get('error'))
        sys.exit(1)

asyncio.run(main())
`], {
        cwd: projectRoot,
        shell: false,
        windowsHide: false, // 显示控制台，方便调试
        env: {
          ...process.env,
          PYTHONPATH: projectRoot,
          PYTHONUTF8: '1',
          PYTHONIOENCODING: 'utf-8',
          DISPLAY: process.env.DISPLAY || ':0'
        },
        stdio: ['ignore', 'pipe', 'pipe']
      })

      const pid = this.process.pid
      console.log('[BrowserBridge] ✅ 桥接服务进程已启动，PID:', pid)

      // 监听输出
      this.process.stdout?.on('data', (data) => {
        const msg = data.toString().trim()
        if (msg) console.log('[BrowserBridge-OUT]', msg)
      })

      this.process.stderr?.on('data', (data) => {
        const msg = data.toString().trim()
        if (msg) console.error('[BrowserBridge-ERR]', msg)
      })

      // 监听进程退出
      this.process.on('close', (code) => {
        console.log(`[BrowserBridge] ⛔ 桥接服务进程退出，代码: ${code}`)
        this.status = 'stopped'
        this.stopHealthCheck()
        this.clearStartupTimer()

        // 非正常退出且应用还在运行，尝试重启
        if (code !== 0 && code !== null && !this.isAppQuitting()) {
          if (this.restartCount < this.maxRestarts) {
            this.restartCount++
            console.log(`[BrowserBridge] 🔄 尝试重启桥接服务 (${this.restartCount}/${this.maxRestarts})`)
            setTimeout(() => this.start(), 2000)
          } else {
            console.error('[BrowserBridge] ❌ 桥接服务启动失败，已达到最大重试次数')
            this.status = 'error'
          }
        }
      })

      this.process.on('error', (err) => {
        console.error('[BrowserBridge] ❌ 进程错误:', err.message)
        this.status = 'error'
      })

      // 启动健康检查
      this.startHealthCheck()

      // 设置启动超时
      this.startupTimer = setTimeout(() => {
        if (this.status === 'starting') {
          console.warn('[BrowserBridge] ⚠️ 桥接服务启动超时')
        }
      }, 15000) // 15 秒超时

      return true
    } catch (error) {
      console.error('[BrowserBridge] ❌ 启动失败:', error)
      this.status = 'error'
      return false
    }
  }

  /**
   * 停止浏览器桥接服务
   */
  stop(): void {
    console.log('[BrowserBridge] 🛑 正在停止浏览器桥接服务...')

    this.clearStartupTimer()
    this.stopHealthCheck()

    if (this.process) {
      const pid = this.process.pid

      if (os.platform() === 'win32') {
        try {
          // Windows 下强制结束
          execSync(`taskkill /F /T /PID ${pid}`, { windowsHide: true })
          console.log('[BrowserBridge] ✅ 已强制结束桥接服务进程:', pid)
        } catch (e) {
          this.process.kill('SIGTERM')
        }
      } else {
        this.process.kill('SIGTERM')
      }

      this.process = null
    }

    this.status = 'stopped'
    this.restartCount = 0
  }

  /**
   * 重启桥接服务
   */
  async restart(): Promise<boolean> {
    console.log('[BrowserBridge] 🔄 正在重启桥接服务...')
    this.stop()
    await new Promise(resolve => setTimeout(resolve, 1500))
    return this.start()
  }

  /**
   * 获取桥接服务状态
   */
  getStatus(): BridgeStatus {
    return this.status
  }

  /**
   * 获取桥接服务配置
   */
  getConfig() {
    return {
      bridgeDir: BRIDGE_CONFIG.bridgeDir,
      pythonPath: BRIDGE_CONFIG.pythonPath,
      cdpPort: BRIDGE_CONFIG.cdpPort,
      healthUrl: BRIDGE_CONFIG.healthUrl,
      status: this.status,
      pid: this.process?.pid || null,
    }
  }

  /**
   * 启动健康检查
   */
  private startHealthCheck(): void {
    this.stopHealthCheck()

    // 延迟开始检查
    setTimeout(async () => {
      await this.checkHealth()
    }, 2000)

    // 定期检查
    this.healthCheckTimer = setInterval(async () => {
      await this.checkHealth()
    }, 10000)
  }

  /**
   * 停止健康检查
   */
  private stopHealthCheck(): void {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer)
      this.healthCheckTimer = null
    }
  }

  /**
   * 清除启动超时计时器
   */
  private clearStartupTimer(): void {
    if (this.startupTimer) {
      clearTimeout(this.startupTimer)
      this.startupTimer = null
    }
  }

  /**
   * 检查桥接服务健康状态
   * 通过检查 CDP 端口是否开放
   */
  private async checkHealth(): Promise<void> {
    try {
      // 尝试连接 CDP 端口
      const response = await fetch(BRIDGE_CONFIG.healthUrl, {
        method: 'GET',
        signal: AbortSignal.timeout(3000)
      })

      if (response.ok || response.status === 200 || response.status === 404) {
        // CDP 端口可访问（可能返回404但端口是开放的）
        if (this.status === 'starting') {
          console.log('[BrowserBridge] ✅ 桥接服务启动成功！CDP端口可用')
          this.restartCount = 0
          this.clearStartupTimer()
        }
        this.status = 'running'
      }
    } catch (error) {
      // CDP 端口不可访问
      if (this.status === 'running') {
        console.warn('[BrowserBridge] ⚠️ CDP端口不可访问，桥接服务可能已停止')
        this.status = 'error'
      }
    }
  }

  /**
   * 检查应用是否正在退出
   */
  private isAppQuitting(): boolean {
    // 这里需要和后端管理器共享退出状态
    // 暂时返回 false
    return false
  }
}

// 导出单例
export const browserBridgeManager = new BrowserBridgeManager()
