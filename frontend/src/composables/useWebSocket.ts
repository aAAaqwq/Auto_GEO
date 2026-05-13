/**
 * WebSocket Hook
 * 我用这个来简化 WebSocket 通信！
 */

import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useWebSocket as useWsService } from '@/services/websocket'

type MessageHandler = (data: any) => void
type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket(url?: string) {
  const wsService = useWsService()

  const status = wsService.status
  const handlers = new Map<string, Set<MessageHandler>>()

  // 连接
  const connect = (wsUrl?: string) => {
    const targetUrl = wsUrl || url || import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws'
    wsService.connect(targetUrl)
  }

  // 断开
  const disconnect = () => {
    wsService.disconnect()
    handlers.clear()
  }

  // 发送消息
  const send = (data: any) => {
    wsService.send(data)
  }

  // 订阅消息
  const on = (type: string, handler: MessageHandler) => {
    if (!handlers.has(type)) {
      handlers.set(type, new Set())
    }
    handlers.get(type)!.add(handler)

    // 同时在服务层订阅
    const unsubscribe = wsService.on(type, handler)

    // 返回取消订阅函数
    return () => {
      handlers.get(type)?.delete(handler)
      unsubscribe()
    }
  }

  // 订阅发布进度
  const onPublishProgress = (callback: (data: {
    taskId: string
    articleTitle: string
    platform: string
    platformName: string
    accountName: string
    status: number
    errorMsg?: string
  }) => void) => {
    return on('publish_progress', callback)
  }

  // 订阅发布完成
  const onPublishComplete = (callback: (data: any) => void) => {
    return on('publish_complete', callback)
  }

  // 订阅授权完成
  const onAuthComplete = (callback: (data: any) => void) => {
    return on('auth_complete', callback)
  }

  // 订阅自动发布任务进度
  const onAutoPublishProgress = (callback: (data: {
    taskId: number
    recordId: number
    articleId: number
    articleTitle: string
    accountId: number
    accountName: string
    platform: string
    platformName: string
    status: string
    platformUrl?: string
    errorMsg?: string
    completedCount: number
    failedCount: number
    totalCount: number
  }) => void) => {
    return on('auto_publish_progress', callback)
  }

  // 清理
  onUnmounted(() => {
    disconnect()
  })

  return {
    status,
    connect,
    disconnect,
    send,
    on,
    onPublishProgress,
    onPublishComplete,
    onAuthComplete,
    onAutoPublishProgress,
  }
}
