<template>
  <div class="agent-page">
    <section class="agent-shell">
      <div class="chat-pane">
        <div class="chat-toolbar">
          <div>
            <h2>AutoGEO 智能体</h2>
            <p>用自然语言整理生成、发布和任务查询需求。信息齐全后会自动生成并发布。</p>
          </div>
          <el-button :icon="Refresh" circle @click="resetChat" />
        </div>

        <div ref="messageListRef" class="message-list">
          <div
            v-for="item in messages"
            :key="item.id"
            class="message-row"
            :class="item.role"
          >
            <div class="message-bubble">
              <div class="message-text">{{ item.content }}</div>
              <div v-if="item.questions?.length" class="question-list">
                <button
                  v-for="question in item.questions"
                  :key="question"
                  type="button"
                  @click="useQuestion(question)"
                >
                  {{ question }}
                </button>
              </div>
              <div v-if="item.meta" class="message-meta">
                <el-tag size="small" :type="statusTagType(item.meta.status)">
                  {{ statusText(item.meta.status) }}
                </el-tag>
                <span>{{ item.meta.intent }}</span>
                <span>{{ item.meta.trace_id }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="composer">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="3"
            resize="none"
            maxlength="1000"
            show-word-limit
            placeholder="例如：帮我写一篇关于数字人工项目的文章，发布到知乎"
            @keydown.ctrl.enter.prevent="sendMessage"
          />
          <div class="composer-actions">
            <div class="quick-prompts">
              <el-button size="small" @click="fillPrompt('帮我写一篇关于数字人工项目的文章')">生成文章</el-button>
              <el-button size="small" @click="fillPrompt('帮我写一篇关于数字人工项目的文章，发布到知乎')">生成并发布</el-button>
              <el-button size="small" @click="fillPrompt('查询最近任务进度')">查进度</el-button>
            </div>
            <el-button type="primary" :loading="sending" @click="sendMessage">
              <el-icon><Promotion /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Refresh } from '@element-plus/icons-vue'
import { conversationApi, type ConversationResult } from '@/services/api'

interface ChatMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
  questions?: string[]
  meta?: ConversationResult
}

const inputText = ref('')
const sending = ref(false)
const sessionId = ref('')
const messageListRef = ref<HTMLElement>()
const messages = ref<ChatMessage[]>([
  {
    id: 'welcome',
    role: 'assistant',
    content: '你好，我是 AutoGEO 后台智能体。你可以告诉我要使用哪个项目或公司，并说明要发布到哪个平台。',
  },
])

function fillPrompt(text: string) {
  inputText.value = text
}

function useQuestion(question: string) {
  inputText.value = question
}

function resetChat() {
  sessionId.value = ''
  inputText.value = ''
  messages.value = [
    {
      id: 'welcome',
      role: 'assistant',
      content: '新的对话已开始。告诉我要使用哪个项目或公司，以及要发布到哪个平台。',
    },
  ]
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  messages.value.push({
    id: `user_${Date.now()}`,
    role: 'user',
    content: text,
  })
  inputText.value = ''
  sending.value = true
  await scrollToBottom()

  try {
    const result = await conversationApi.sendMessage({
      message: text,
      session_id: sessionId.value || undefined,
    })
    sessionId.value = result.conversation_id
    messages.value.push({
      id: result.trace_id,
      role: 'assistant',
      content: result.reply,
      questions: result.next_questions,
      meta: result,
    })
  } catch (error) {
    ElMessage.error('智能体请求失败')
    messages.value.push({
      id: `error_${Date.now()}`,
      role: 'assistant',
      content: '这次请求没有成功，请稍后再试，或检查登录状态和后端服务。',
    })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

function statusText(status?: string) {
  const map: Record<string, string> = {
    accepted: '已受理',
    understood: '已理解',
    need_clarification: '需补充',
    confirm_required: '需确认',
    running: '执行中',
    review_required: '需审核',
    completed: '已完成',
    cancelled: '已取消',
    binding_required: '需绑定',
    project_required: '缺项目',
    account_required: '缺账号',
    failed: '失败',
  }
  return status ? map[status] || status : '待识别'
}

function statusTagType(status?: string) {
  if (status === 'accepted') return 'success'
  if (status === 'running' || status === 'completed') return 'success'
  if (status === 'need_clarification' || status === 'confirm_required' || status === 'review_required') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}
</script>

<style scoped lang="scss">
.agent-page {
  height: 100%;
  min-height: calc(100vh - 96px);
}

.agent-shell {
  display: block;
  height: calc(100vh - 112px);
}

.chat-pane {
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.72);
  border-radius: 8px;
}

.chat-pane {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.chat-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);

  h2 {
    margin: 0 0 6px;
    font-size: 20px;
  }

  p {
    margin: 0;
    color: #94a3b8;
    font-size: 13px;
  }
}

.message-list {
  overflow-y: auto;
  padding: 20px;
}

.message-row {
  display: flex;
  margin-bottom: 14px;

  &.user {
    justify-content: flex-end;
  }
}

.message-bubble {
  max-width: min(680px, 82%);
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.92);
  color: #e5e7eb;
  line-height: 1.6;
}

.message-row.user .message-bubble {
  background: #2563eb;
  color: white;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
  color: #94a3b8;
  font-size: 12px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;

  button {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid rgba(96, 165, 250, 0.45);
    border-radius: 6px;
    background: rgba(37, 99, 235, 0.12);
    color: #bfdbfe;
    text-align: left;
    cursor: pointer;
  }
}

.composer {
  padding: 14px;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.composer-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 1100px) {
  .agent-shell {
    height: auto;
  }

  .chat-pane {
    min-height: 680px;
  }
}
</style>
