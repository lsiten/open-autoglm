<template>
  <div class="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 custom-scrollbar scroll-smooth" ref="chatContainer" @scroll="handleChatScroll">
    <div v-if="isLoadingMore" class="w-full flex justify-center py-2 text-gray-500">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <div v-for="(msg, index) in messages" :key="msg.id || index" class="group flex w-full" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
      <!-- Agent Avatar -->
      <div v-if="msg.role === 'agent'" class="w-8 h-8 mr-3 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/20 text-white text-xs font-bold">
        AI
      </div>

      <!-- Message Content -->
      <div class="max-w-[85%] sm:max-w-[75%] flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
        <!-- User Bubble -->
        <div v-if="msg.role === 'user'" class="bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-md text-sm leading-relaxed">
          {{ msg.content }}
        </div>

        <!-- Agent Components -->
        <template v-else>
          <!-- INFO Message -->
          <InfoMessage
            v-if="msg.isInfo && msg.content"
            :message="msg"
            :index="index"
            :collapse-state="collapseState[index]?.info ?? true"
            @toggle="toggleCollapse(index, 'info')"
            @preview-image="$emit('preview-image', $event)"
          />

          <!-- Screenshot Only -->
          <ScreenshotMessage
            v-else-if="msg.screenshot && !msg.thought && !msg.content && !msg.isInfo"
            :screenshot="msg.screenshot"
            @preview-image="$emit('preview-image', $event)"
          />

          <!-- Think/Reasoning -->
          <ThinkMessage
            v-if="msg.thought && !msg.action && !msg.isAnswer"
            :message="msg"
            :index="index"
            :collapse-state="collapseState[index]?.thought ?? true"
            @toggle="toggleCollapse(index, 'thought')"
            @preview-image="$emit('preview-image', $event)"
          />

          <!-- Answer/Action -->
          <AnswerMessage
            v-if="msg.isAnswer || msg.action || (msg.content && !msg.isInfo && !msg.thought && !msg.isThinking)"
            :message="msg"
            @preview-image="$emit('preview-image', $event)"
          />

          <!-- Task Failed/Error -->
          <ErrorMessage
            v-if="msg.isFailed || msg.isError"
            :message="msg"
            @preview-image="$emit('preview-image', $event)"
          />

          <!-- Interaction: Confirmation/Choice -->
          <ConfirmMessage
            v-if="msg.type === 'confirm'"
            :message="msg"
            @action="$emit('card-action', $event)"
          />

          <!-- Interaction: Input -->
          <InputMessage
            v-if="msg.type === 'input'"
            :message="msg"
            @input="$emit('card-input', $event)"
          />

          <!-- Interaction: Click Annotation -->
          <ClickAnnotationMessage
            v-if="msg.type === 'click_annotation'"
            :message="msg"
            :latest-screenshot="latestScreenshot"
            @annotation="$emit('card-annotation', $event)"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import InfoMessage from './messages/InfoMessage.vue'
import ScreenshotMessage from './messages/ScreenshotMessage.vue'
import ThinkMessage from './messages/ThinkMessage.vue'
import AnswerMessage from './messages/AnswerMessage.vue'
import ErrorMessage from './messages/ErrorMessage.vue'
import ConfirmMessage from './messages/ConfirmMessage.vue'
import InputMessage from './messages/InputMessage.vue'
import ClickAnnotationMessage from './messages/ClickAnnotationMessage.vue'

defineProps<{
  messages: any[]
  isLoadingMore?: boolean
  collapseState: Record<number, { thought?: boolean, screenshot?: boolean, info?: boolean }>
  latestScreenshot?: string
}>()

defineEmits<{
  'preview-image': [url: string]
  'card-action': [data: { msg: any, option: any }]
  'card-input': [data: { msg: any }]
  'card-annotation': [data: { msg: any, annotation: { x: number, y: number, description: string } }]
  'scroll': [event: Event]
}>()

const chatContainer = ref<HTMLElement | null>(null)

const toggleCollapse = (index: number, type: 'thought' | 'info' | 'screenshot') => {
  // This will be handled by parent component
}

const handleChatScroll = (e: Event) => {
  // Emit scroll event to parent
}
</script>

