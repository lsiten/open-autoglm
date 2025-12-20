<template>
  <!-- Main Container: Force dark background and full viewport -->
  <div class="flex h-screen w-full bg-[#0f1115] text-gray-200 overflow-hidden font-sans">
    
    <!-- Left Sidebar: Device & Settings -->
    <!-- Fixed width, no shrink to prevent collapse -->
    <transition name="slide-fade">
      <div v-if="sidebarOpen" class="w-72 min-w-[18rem] bg-[#161b22] border-r border-gray-800 flex flex-col shrink-0 z-30">
        <!-- Brand -->
        <div class="h-16 border-b border-gray-800 flex items-center px-5 gap-3 shrink-0">
          <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
             <img src="/logo.svg" alt="Logo" class="w-5 h-5 invert brightness-0" />
          </div>
          <span class="font-bold text-lg tracking-tight text-white">AutoGLM</span>
        </div>

        <!-- Connection Error Banner -->
        <div v-if="!wsConnected && !loadingDevices" class="bg-red-900/20 border-b border-red-900/50 p-2 text-center">
            <p class="text-[10px] text-red-300 mb-1">{{ t('sidebar.connection_failed') }} {{ wsBaseUrl }}</p>
            <p v-if="wsError" class="text-[9px] text-red-400 mb-1 font-mono break-all">{{ wsError }}</p>
            <a :href="`${backendRootUrl}/docs`" target="_blank" class="text-[10px] text-blue-400 underline hover:text-blue-300 block">
                {{ t('sidebar.trust_certificate') }}
            </a>
            <span class="text-[9px] text-gray-500 block mt-1">{{ t('sidebar.accept_unsafe') }}</span>
        </div>

        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <!-- Device Section -->
          <div class="flex items-center justify-between mb-3">
             <div class="text-xs font-bold text-gray-500 uppercase tracking-wider">{{ t('sidebar.devices') }}</div>
             <el-button link type="primary" size="small" @click="fetchDevices" :loading="loadingDevices">
               <el-icon><Refresh /></el-icon>
             </el-button>
          </div>
          
          <div class="space-y-2">
            <!-- Always show Connect Guide button -->
            
            <div 
              class="p-3 rounded-lg border border-dashed border-gray-700 text-center hover:bg-gray-800/50 cursor-pointer transition-colors flex items-center justify-center gap-2" 
              @click="showConnectionGuide = true"
            >
               <el-icon class="text-blue-400"><Plus /></el-icon>
               <span class="text-xs text-gray-500">{{ t('sidebar.add_device') }}</span>
            </div>

            <div 
              v-for="dev in devices"  
              :key="dev.id"
              class="group relative p-3 rounded-xl border border-gray-700/50 bg-gray-800/30 transition-all duration-200"
              :class="{ 
                '!bg-blue-900/10 !border-blue-500/80 shadow-[0_0_15px_-3px_rgba(59,130,246,0.3)]': activeDeviceId === dev.id,
                'opacity-60 grayscale cursor-not-allowed': dev.status === 'offline',
                'hover:bg-gray-800 hover:border-blue-500/50 cursor-pointer': dev.status !== 'offline'
              }"
              @click="selectDevice(dev)"
            >
              <!-- Device content ... -->
              <div class="flex items-center justify-between mb-1">
                 <div class="flex items-center gap-2 overflow-hidden flex-1 mr-2">
                   <el-icon :class="activeDeviceId === dev.id ? 'text-blue-400' : 'text-gray-400'" class="shrink-0"><Iphone /></el-icon>
                   
                   <!-- Rename UI -->
                   <div v-if="editingDeviceId === dev.id" class="flex items-center gap-1 w-full" @click.stop>
                       <el-input v-model="editName" size="small" @keyup.enter="saveDeviceName(dev)" ref="renameInput" />
                       <el-button size="small" circle type="success" @click="saveDeviceName(dev)"><el-icon><Check /></el-icon></el-button>
                       <el-button size="small" circle @click="cancelEdit"><el-icon><Close /></el-icon></el-button>
                   </div>
                   <div v-else class="flex items-center gap-2 group/name w-full overflow-hidden">
                       <span class="text-sm font-medium text-gray-200 truncate" :title="dev.id">{{ dev.displayName || dev.model || dev.id }}</span>
                       <el-icon class="opacity-0 group-hover/name:opacity-100 cursor-pointer text-gray-500 hover:text-white" @click.stop="startEdit(dev)"><Edit /></el-icon>
                   </div>
                 </div>
                 
                 <div class="flex items-center gap-2">
                    <!-- Delete Button (visible on hover) -->
                    <el-button 
                      v-if="dev.type === 'webrtc'"
                      class="!p-1 opacity-0 group-hover:opacity-100 transition-opacity" 
                      type="danger" 
                      link 
                      @click.stop="deleteDevice(dev)"
                    >
                        <el-icon><Delete /></el-icon>
                    </el-button>

                    <div class="flex h-2 w-2 shrink-0">
                        <span v-if="dev.status !== 'offline'" class="animate-ping absolute inline-flex h-2 w-2 rounded-full opacity-75" :class="dev.status === 'device' || dev.status === 'connected' ? 'bg-green-400' : 'bg-red-400'"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2" :class="{
                            'bg-green-500': dev.status === 'device' || dev.status === 'connected',
                            'bg-red-500': dev.status === 'unauthorized',
                            'bg-gray-500': dev.status === 'offline'
                        }"></span>
                    </div>
                 </div>
              </div>
              <div class="flex items-center gap-2 text-[10px] text-gray-500 font-mono">
                 <span class="px-1.5 py-0.5 rounded bg-gray-700/50">{{ dev.type.toUpperCase() }}</span>
                 <span>{{ dev.connection_type }}</span>
                 <span v-if="dev.status === 'offline'" class="text-red-400 italic">{{ t('sidebar.offline') || 'Offline' }}</span>
              </div>
            </div>
          </div>

                <!-- Config -->
                <div v-if="activeDeviceId" @click="showConfig = true" class="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 cursor-pointer group transition-colors">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center group-hover:bg-gray-700 transition-colors">
                            <el-icon><Setting /></el-icon>
                        </div>
                        <span class="text-sm text-gray-400 group-hover:text-gray-200">{{ t('sidebar.model_settings') }}</span>
                    </div>
                    <el-icon class="text-gray-600 group-hover:text-gray-400"><ArrowRight /></el-icon>
                </div>
         </div>
         
        <!-- Sidebar Footer -->
        <div class="p-4 border-t border-gray-800 bg-[#161b22] shrink-0">
           <div class="flex items-center gap-2 text-xs text-gray-500">
              <div class="w-2 h-2 rounded-full" :class="wsConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-red-500'"></div>
              <span>{{ wsConnected ? t('sidebar.connected') : t('sidebar.disconnected') }}</span>
           </div>
        </div>
      </div>
    </transition>

    <!-- Main Content: Chat & Workspace -->
    <div class="flex-1 flex flex-col min-w-0 bg-[#0f1115] relative z-10">
       <!-- Top Bar -->
       <div class="h-16 border-b border-gray-800 flex items-center justify-between px-4 sm:px-6 bg-[#0f1115]/80 backdrop-blur z-20 sticky top-0 shrink-0">
          <div class="flex items-center gap-4">
            <el-button circle text @click="sidebarOpen = !sidebarOpen">
              <el-icon><Menu /></el-icon>
            </el-button>
            
            <!-- Current Session / Task Selector -->
            <el-dropdown v-if="activeDeviceId" trigger="click" @command="selectTask" class="min-w-[200px]">
                <div class="flex items-center gap-3 cursor-pointer hover:bg-gray-800 px-3 py-1.5 rounded-lg transition-colors border border-transparent hover:border-gray-700">
                    <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-blue-400 shrink-0">
                        <el-icon v-if="activeTask?.type === 'background'"><Monitor /></el-icon>
                        <el-icon v-else><ChatLineRound /></el-icon>
                    </div>
                    <div class="flex flex-col min-w-0">
                       <span class="text-[10px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                         {{ activeTask?.type === 'background' ? t('task.task') : t('task.session') }}
                         <span v-if="agentStatus === 'running'" class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                       </span>
                       <span class="text-sm font-medium text-white flex items-center gap-2 truncate max-w-[150px]">
                         {{ activeTask?.name || t('task.select_session') }}
                         <el-icon class="text-gray-500 text-xs shrink-0"><ArrowDown /></el-icon>
                       </span>
                    </div>
                </div>
                <template #dropdown>
                    <el-dropdown-menu class="min-w-[280px] p-2 custom-dropdown">
                        <!-- Sessions (IndexedDB) -->
                        <div class="px-3 py-2 text-[10px] font-bold text-gray-500 uppercase flex justify-between items-center bg-gray-50/5 rounded mb-1">
                            <span>{{ t('task.sessions_local') }}</span>
                            <el-button link type="primary" size="small" @click.stop="openCreateTaskDialog('chat')"><el-icon><Plus /></el-icon></el-button>
                        </div>
                        
                        <div class="max-h-[200px] overflow-y-auto custom-scrollbar" @scroll="handleSessionScroll">
                            <el-dropdown-item v-for="s in visibleSessions" :key="s.id" :command="s" :class="{'!text-blue-400 !bg-blue-900/10': activeTaskId === s.id}">
                                <div class="flex items-center justify-between w-full gap-3 group/item">
                                    <div class="flex items-center gap-2 overflow-hidden flex-1">
                                        <el-icon><ChatLineRound /></el-icon>
                                        <span class="truncate">{{ s.name }}</span>
                                    </div>
                                    <div class="flex items-center gap-1 shrink-0 opacity-0 group-hover/item:opacity-100 transition-opacity">
                                        <el-icon class="text-gray-500 hover:text-white" @click.stop="startEditTask(s)"><Edit /></el-icon>
                                        <el-icon class="text-gray-500 hover:text-red-400" @click.stop="deleteTask(s)"><Delete /></el-icon>
                                    </div>
                                </div>
                            </el-dropdown-item>
                            <div v-if="sessions.length > visibleSessions.length" class="text-center py-2 text-[10px] text-gray-500">
                                <el-icon class="is-loading"><Loading /></el-icon>
                            </div>
                        </div>
                        <div v-if="sessions.length === 0" class="px-4 py-2 text-xs text-gray-500 italic">{{ t('task.no_sessions') }}</div>

                        <div class="border-t border-gray-700/50 my-2"></div>

                        <!-- Tasks (Backend) -->
                        <div class="px-3 py-2 text-[10px] font-bold text-gray-500 uppercase flex justify-between items-center bg-gray-50/5 rounded mb-1">
                            <span>{{ t('task.background_tasks_remote') }}</span>
                            <el-button link type="primary" size="small" @click.stop="openCreateTaskDialog('background')"><el-icon><Plus /></el-icon></el-button>
                        </div>
                        <el-dropdown-item v-for="t in backgroundTasks" :key="t.id" :command="t" :class="{'!text-blue-400 !bg-blue-900/10': activeTaskId === t.id}">
                             <div class="flex items-center justify-between w-full gap-3 group/item">
                                <div class="flex items-center gap-2 overflow-hidden flex-1">
                                    <el-icon><Monitor /></el-icon>
                                    <span class="truncate">{{ t.name }}</span>
                                </div>
                                <div class="flex items-center gap-1 shrink-0 opacity-0 group-hover/item:opacity-100 transition-opacity">
                                    <span v-if="t.status === 'running'" class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                                    <el-icon class="text-gray-500 hover:text-white" @click.stop="startEditTask(t)"><Edit /></el-icon>
                                    <el-icon class="text-gray-500 hover:text-red-400" @click.stop="deleteTask(t)"><Delete /></el-icon>
                                </div>
                            </div>
                        </el-dropdown-item>
                         <div v-if="backgroundTasks.length === 0" class="px-4 py-2 text-xs text-gray-500 italic">{{ t('task.no_tasks') }}</div>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
          </div>

          <div class="flex items-center gap-3">
             <!-- Permissions Button (Moved to Top Bar) -->
             <el-tooltip :content="t('permissions.title')" placement="bottom">
                <el-button v-if="activeDeviceId" circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="openPermissions">
                    <el-icon><Lock /></el-icon>
                </el-button>
             </el-tooltip>

             <!-- Language Switcher -->
             <el-dropdown @command="(lang: string) => locale = lang">
                <span class="text-xs text-gray-400 hover:text-white cursor-pointer flex items-center">
                   {{ locale.toUpperCase() }} <el-icon class="ml-1"><ArrowDown /></el-icon>
                </span>
                <template #dropdown>
                   <el-dropdown-menu>
                      <el-dropdown-item command="en">English</el-dropdown-item>
                      <el-dropdown-item command="zh">中文</el-dropdown-item>
                      <el-dropdown-item command="ja">日本語</el-dropdown-item>
                      <el-dropdown-item command="ko">한국어</el-dropdown-item>
                   </el-dropdown-menu>
                </template>
             </el-dropdown>

             <el-button v-if="agentStatus === 'running'" type="danger" size="small" round @click="stopTask">
                <el-icon class="mr-1"><VideoPause /></el-icon> {{ t('common.stop') }}
             </el-button>
          </div>
       </div>

       <!-- Chat Area -->
       <div class="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 custom-scrollbar scroll-smooth" ref="chatContainer" @scroll="handleChatScroll">
          
          <!-- State 1: No Devices Detected - Show Connection Guide -->
          <div v-if="devices.length === 0 && !loadingDevices" class="h-full flex flex-col items-center justify-center animate-fade-in">
             <div class="max-w-2xl w-full bg-[#161b22] border border-gray-800 rounded-2xl p-8 shadow-2xl">
                <!-- ... Guide Content (Unchanged) ... -->
                <div class="text-center mb-8">
                   <div class="w-16 h-16 bg-blue-900/30 text-blue-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-blue-500/30">
                      <el-icon :size="32"><Iphone /></el-icon>
                   </div>
                   <h2 class="text-2xl font-bold text-white mb-2">{{ t('guide.title') }}</h2>
                   <p class="text-gray-400">{{ t('guide.subtitle') }}</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                   <!-- USB Method -->
                   <div class="bg-[#0d1117] border border-gray-700/50 rounded-xl p-5 hover:border-blue-500/50 transition-colors">
                      <div class="flex items-center gap-2 mb-3 text-blue-400">
                         <el-icon><Connection /></el-icon>
                         <h3 class="font-bold">{{ t('guide.usb_option') }}</h3>
                      </div>
                      <ol class="list-decimal list-inside text-sm text-gray-400 space-y-2 marker:text-gray-600">
                         <li>{{ t('guide.usb_steps.step1') }}</li>
                         <li v-html="t('guide.usb_steps.step2')"></li>
                         <li>{{ t('guide.usb_steps.step3') }}</li>
                         <li>{{ t('guide.usb_steps.step4') }}</li>
                      </ol>
                   </div>

                   <!-- WiFi Method -->
                   <div class="bg-[#0d1117] border border-gray-700/50 rounded-xl p-5 hover:border-green-500/50 transition-colors">
                      <div class="flex items-center gap-2 mb-3 text-green-400">
                         <el-icon><Wifi /></el-icon>
                         <h3 class="font-bold">{{ t('guide.wifi_option') }}</h3>
                      </div>
                      <div class="text-sm text-gray-400 space-y-3">
                         <p>{{ t('guide.wifi_text') }}</p>
                         <div class="bg-black/50 p-2 rounded border border-gray-800 font-mono text-xs">
                            <div class="text-gray-500 mb-1">{{ t('guide.wifi_step1') }}</div>
                            <div class="text-green-300">adb tcpip 5555</div>
                            <div class="text-gray-500 my-1">{{ t('guide.wifi_step2') }}</div>
                            <div class="text-green-300">adb connect PHONE_IP:5555</div>
                         </div>
                         <p class="text-xs text-gray-500">{{ t('guide.wifi_tip') }}</p>
                      </div>
                   </div>
                </div>

                <div class="mt-8 pt-6 border-t border-gray-800 flex justify-between items-center text-xs text-gray-500">
                   <div class="flex gap-4">
                      <span>• {{ t('chat.harmony_os_tip') }}</span>
                      <span>• {{ t('chat.ios_tip') }}</span>
                   </div>
                   <el-button link type="primary" size="small" @click="fetchDevices">
                      <el-icon class="mr-1"><Refresh /></el-icon> {{ t('guide.refresh_list') }}
                   </el-button>
                </div>
             </div>
          </div>

          <!-- State 2: Device Connected but Empty Chat -->
          <div v-else-if="chatHistory.length === 0" class="h-full flex flex-col items-center justify-center text-gray-600 opacity-50 select-none">
             <el-icon :size="64" class="mb-4"><ChatDotRound /></el-icon>
             <p class="text-lg font-medium">{{ t('chat.ready_title') }}</p>
             <p class="text-sm">{{ activeDeviceId ? t('chat.ready_subtitle', { device: activeDeviceId }) : t('chat.ready_subtitle_no_device') }}</p>
          </div>

          <!-- State 3: Active Chat History -->
          <div v-if="isLoadingMore" class="w-full flex justify-center py-2 text-gray-500">
               <el-icon class="is-loading"><Loading /></el-icon>
          </div>
          <div v-for="(msg, index) in filteredChatHistory" :key="msg.id || index" class="group flex w-full" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
             
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
                    <!-- Thought Process (Always Visible if present) -->
                    <div v-if="msg.thought" class="mb-2 w-full max-w-xl">
                       <div class="bg-[#1c2128] border border-gray-700/50 rounded-xl overflow-hidden">
                          <div class="bg-[#22272e] px-3 py-2 border-b border-gray-700/50 flex items-center gap-2">
                             <el-icon class="text-amber-500" :class="{ 'is-loading': msg.isThinking }"><Loading v-if="msg.isThinking" /><Cpu v-else /></el-icon>
                             <span class="text-xs font-medium text-gray-400 uppercase tracking-wide">{{ t('chat.reasoning_chain') }}</span>
                          </div>
                          <div class="p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap leading-5 bg-[#0d1117] max-h-64 overflow-y-auto custom-scrollbar">
                             {{ msg.thought }}
                          </div>
                       </div>
                    </div>

                    <!-- Final Response / Message -->
                    <div v-if="msg.content" class="bg-[#1c2128] text-gray-200 px-5 py-3 rounded-2xl rounded-tl-sm border border-gray-700/50 shadow-sm text-sm leading-relaxed">
                       {{ msg.content }}
                    </div>

                    <!-- Action Card -->
                    <div v-if="msg.action" class="mt-2 flex items-center gap-3 bg-[#1c2128] border border-green-900/30 px-3 py-2 rounded-lg max-w-fit">
                       <div class="w-6 h-6 rounded-full bg-green-900/50 flex items-center justify-center text-green-400">
                          <el-icon :size="12"><Pointer /></el-icon>
                       </div>
                       <div class="flex flex-col">
                          <span class="text-[10px] text-gray-500 uppercase font-bold">{{ t('chat.action_executed') }}</span>
                          <span class="text-xs text-green-400 font-mono">{{ msg.action }}</span>
                       </div>
                    </div>

                    <!-- Interaction: Confirmation/Choice -->
                    <div v-if="msg.type === 'confirm'" class="mt-2 w-full max-w-sm bg-[#1c2128] border border-blue-500/30 rounded-xl overflow-hidden shadow-lg animate-fade-in">
                        <div class="px-4 py-3 border-b border-gray-700/50 bg-blue-900/10 flex items-center gap-2">
                            <el-icon class="text-blue-400"><QuestionFilled /></el-icon>
                            <span class="text-xs font-bold text-blue-100">{{ msg.title || 'Confirmation Required' }}</span>
                        </div>
                        <div class="p-4 space-y-4">
                            <p class="text-sm text-gray-300">{{ msg.content }}</p>
                            <div v-if="!msg.submitted" class="flex gap-3 justify-end">
                                <el-button 
                                    v-for="opt in (msg.options || [{label: 'Cancel', value: 'Cancel', type: 'info'}, {label: 'Confirm', value: 'Confirm', type: 'primary'}])" 
                                    :key="opt.label"
                                    :type="opt.type || 'default'" 
                                    size="small"
                                    @click="handleCardAction(msg, opt)"
                                >
                                    {{ opt.label }}
                                </el-button>
                            </div>
                            <div v-else class="text-xs text-gray-500 text-right italic flex items-center justify-end gap-1">
                                <el-icon><Check /></el-icon> {{ t('chat.selected') }} {{ msg.selectedValue }}
                            </div>
                        </div>
                    </div>

                    <!-- Interaction: Input -->
                    <div v-if="msg.type === 'input'" class="mt-2 w-full max-w-sm bg-[#1c2128] border border-amber-500/30 rounded-xl overflow-hidden shadow-lg animate-fade-in">
                        <div class="px-4 py-3 border-b border-gray-700/50 bg-amber-900/10 flex items-center gap-2">
                            <el-icon class="text-amber-400"><EditPen /></el-icon>
                            <span class="text-xs font-bold text-amber-100">{{ msg.title || 'Input Required' }}</span>
                        </div>
                        <div class="p-4 space-y-3">
                            <p class="text-sm text-gray-300">{{ msg.content }}</p>
                            <div v-if="!msg.submitted" class="flex gap-2">
                                <el-input v-model="msg.inputValue" :placeholder="msg.placeholder || 'Enter value...'" size="small" @keyup.enter="handleCardInput(msg)" />
                                <el-button type="primary" size="small" @click="handleCardInput(msg)">Submit</el-button>
                            </div>
                             <div v-else class="text-xs text-gray-500 italic flex items-center justify-end gap-1">
                                <el-icon><Check /></el-icon> {{ t('chat.input_submitted') }}
                            </div>
                        </div>
                    </div>
                </template>
             </div>
          </div>
       </div>

       <!-- Input Area -->
       <div class="p-4 sm:p-6 bg-[#0f1115] border-t border-gray-800 z-20 shrink-0">
          <div class="relative max-w-4xl mx-auto w-full">
             <!-- Toolbar & Preview (Unchanged) -->
             <div class="mb-3 flex flex-col gap-2">
                 <!-- Attachments Preview -->
                 <div v-if="attachments.length > 0" class="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                     <div v-for="(file, idx) in attachments" :key="idx" class="relative group bg-[#161b22] border border-gray-700 rounded-lg p-2 flex items-center gap-2 min-w-[120px] max-w-[200px]">
                         <div v-if="file.type === 'image'" class="w-8 h-8 rounded bg-cover bg-center shrink-0" :style="{ backgroundImage: `url(${file.url})` }"></div>
                         <div v-else class="w-8 h-8 rounded bg-gray-800 flex items-center justify-center text-gray-400 shrink-0">
                             <el-icon v-if="file.type === 'video'"><VideoCamera /></el-icon>
                             <el-icon v-else-if="file.type === 'audio'"><Microphone /></el-icon>
                             <el-icon v-else><Document /></el-icon>
                         </div>
                         <span class="text-xs text-gray-300 truncate flex-1">{{ file.name }}</span>
                         <button @click="removeAttachment(idx)" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
                             <el-icon :size="10"><Close /></el-icon>
                         </button>
                     </div>
                 </div>
                 
                 <!-- Toolbar -->
                 <div v-if="activeDeviceId" class="flex items-center gap-4 px-1">
                    <el-tooltip :content="t('input.upload_image')" placement="top">
                        <button @click="triggerUpload('image')" class="text-gray-500 hover:text-blue-400 transition-colors"><el-icon :size="20"><Picture /></el-icon></button>
                    </el-tooltip>
                    <!-- ... other toolbar items ... -->
                    <el-tooltip :content="t('input.select_app')" placement="top">
                        <button @click="triggerAppSelect" class="text-gray-500 hover:text-green-400 transition-colors"><el-icon :size="20"><Grid /></el-icon></button>
                    </el-tooltip>
                    <input type="file" ref="fileInput" class="hidden" @change="handleFileSelect" />
                 </div>
             </div>

             <!-- App Suggestions Popover (Unchanged) -->
             <div v-if="showAppSuggestions" class="absolute bottom-full left-0 mb-2 bg-[#161b22] border border-gray-700 rounded-lg shadow-xl max-h-64 overflow-y-auto w-72 z-50 custom-scrollbar animate-fade-in">
                 <div class="px-3 py-1.5 text-[10px] text-gray-500 font-bold uppercase tracking-wider border-b border-gray-700/50 flex justify-between">
                    <span>{{ t('input.apps') }}</span>
                    <span class="text-[9px] bg-gray-800 px-1 rounded">{{ availableApps.length }}</span>
                 </div>
                 <div v-for="app in availableApps.filter(a => a.name.toLowerCase().includes(appSuggestionQuery))" :key="app.name" 
                      @click="selectApp(app.name)" 
                      class="px-3 py-2 hover:bg-blue-900/20 hover:text-blue-400 cursor-pointer text-sm text-gray-300 flex items-center gap-2 transition-colors border-b border-gray-800/30 last:border-0">
                      <div class="w-8 h-8 bg-gray-800 rounded flex items-center justify-center text-xs font-bold shrink-0" :class="app.type === 'supported' ? 'text-green-400 bg-green-900/10' : 'text-gray-500'">{{ app.name[0].toUpperCase() }}</div>
                      <div class="flex flex-col min-w-0 flex-1">
                        <span class="truncate font-medium">{{ app.name }}</span>
                        <span v-if="app.package" class="text-[10px] text-gray-500 truncate font-mono">{{ app.package }}</span>
                      </div>
                      <el-tag v-if="app.type === 'supported'" size="small" type="success" effect="plain" class="scale-75 origin-right">{{ t('input.support_tag') }}</el-tag>
                 </div>
             </div>

             <el-input
                ref="inputRef"
                v-model="input"
                @input="onInputChange"
                :disabled="agentStatus === 'running' || !activeDeviceId"
                :placeholder="activeDeviceId ? t('chat.input_placeholder') : t('chat.select_device_placeholder')"
                class="custom-input !text-base w-full"
                size="large"
                @keyup.enter="sendMessage"
             >
                <template #prefix>
                   <el-icon class="text-gray-500"><Search /></el-icon>
                </template>
                <template #suffix>
                   <el-button type="primary" circle @click="sendMessage" :loading="sending" :disabled="!input">
                      <el-icon><Position /></el-icon>
                   </el-button>
                </template>
             </el-input>
          </div>
       </div>
    </div>

    <!-- Right: Screen Mirror (Unchanged) -->
    <div v-if="activeDeviceId" class="w-[400px] min-w-[350px] bg-[#000] border-l border-gray-800 flex flex-col relative shrink-0 z-20">
       <div class="h-16 border-b border-gray-800/50 flex items-center justify-between px-4 bg-[#0d1117] shrink-0">
          <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">{{ t('mirror.title') }}</span>
          <div class="flex items-center gap-2">
             <!-- Stream Quality Selector -->
             <el-dropdown @command="updateStreamQuality" trigger="click">
                <span class="el-dropdown-link text-[10px] font-mono text-gray-400 hover:text-white cursor-pointer bg-gray-800 border border-gray-700 px-2 py-0.5 rounded flex items-center gap-1">
                   {{ t('mirror.quality_' + streamQuality) }}
                   <el-icon><ArrowDown /></el-icon>
                </span>
                <template #dropdown>
                   <el-dropdown-menu class="custom-dropdown">
                      <el-dropdown-item v-for="opt in qualityOptions" :key="opt.key" :command="opt.key" :class="{'!text-blue-400': streamQuality === opt.key}">
                          {{ t('mirror.quality_' + opt.key) }}
                      </el-dropdown-item>
                   </el-dropdown-menu>
                </template>
             </el-dropdown>
             <el-tag size="small" effect="dark" class="!bg-gray-800 !border-gray-700 text-gray-400 font-mono text-[10px]">{{ fps }} {{ t('chat.fps') }}</el-tag>
          </div>
       </div>
       
       <div class="flex-1 flex items-center justify-center p-4 sm:p-6 bg-[url('/grid.svg')] bg-repeat opacity-100 overflow-hidden">
          <!-- Phone Frame -->
          <div class="relative w-full bg-gray-900 rounded-[2.5rem] ring-8 ring-gray-800 shadow-2xl overflow-hidden select-none transition-all duration-500"
               :class="isLandscape ? 'max-w-[600px] aspect-[19.5/9]' : 'max-w-[320px] aspect-[9/19.5]'">
             <div v-if="!isLandscape" class="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-6 bg-black rounded-b-xl z-20"></div>
             
             <!-- Screen Content -->
             <div class="w-full h-full relative group cursor-crosshair" 
                  @mousedown="handleMouseDown"
                  @mousemove="handleMouseMove"
                  @mouseup="handleMouseUp"
                  @mouseleave="handleMouseUp">
                <img v-if="latestScreenshot" :src="latestScreenshot" class="w-full h-full object-fill pointer-events-none select-none" draggable="false" />
                
                <!-- Loading State -->
                <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-600 gap-3 bg-[#050505]">
                   <div class="relative">
                     <div class="w-12 h-12 border-2 border-gray-700 rounded-full animate-spin border-t-blue-500"></div>
                     <el-icon class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-gray-600"><VideoCamera /></el-icon>
                   </div>
                   <span class="text-xs font-mono text-center px-4" v-html="t('mirror.waiting_signal').replace(' ', '<br>')"></span>
                </div>

                <!-- Click Ripple Effect -->
                <div v-for="click in clickEffects" :key="click.id" 
                     class="absolute rounded-full border-2 border-blue-400 bg-blue-400/30 animate-ping pointer-events-none"
                     :style="{ left: click.x + 'px', top: click.y + 'px', width: '20px', height: '20px', transform: 'translate(-50%, -50%)' }">
                </div>
             </div>
          </div>
       </div>
       
       <!-- Quick Actions Footer -->
       <div class="h-16 border-t border-gray-800 bg-[#0d1117] flex items-center justify-around px-4 shrink-0">
          <el-tooltip :content="t('mirror.home')" placement="top">
            <el-button circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="goHome">
              <el-icon><House /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip :content="t('mirror.back')" placement="top">
            <el-button circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="goBack">
              <el-icon><Back /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip :content="t('mirror.recent_apps')" placement="top">
            <el-button circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="goRecent">
              <el-icon><Menu /></el-icon>
            </el-button>
          </el-tooltip>
       </div>
    </div>

    <!-- Permissions Dialog -->
    <el-dialog v-model="showPermissions" :title="t('permissions.title')" width="400px" class="dark-dialog permissions-dialog">
        <div class="space-y-4">
            <p class="text-xs text-gray-400 mb-4">{{ t('permissions.description') }}</p>
            
            <div class="flex items-center justify-between">
                <span class="text-sm transition-colors" :class="devicePermissions.install_app ? 'text-black font-medium' : 'text-gray-400'">{{ t('permissions.install_app') }}</span>
                <el-switch v-model="devicePermissions.install_app" />
            </div>
            <div class="flex items-center justify-between">
                <span class="text-sm transition-colors" :class="devicePermissions.payment ? 'text-black font-medium' : 'text-gray-400'">{{ t('permissions.payment') }}</span>
                <el-switch v-model="devicePermissions.payment" />
            </div>
            <div class="flex items-center justify-between">
                <span class="text-sm transition-colors" :class="devicePermissions.wechat_reply ? 'text-black font-medium' : 'text-gray-400'">{{ t('permissions.reply_wechat') }}</span>
                <el-switch v-model="devicePermissions.wechat_reply" />
            </div>
            <div class="flex items-center justify-between">
                <span class="text-sm transition-colors" :class="devicePermissions.send_sms ? 'text-black font-medium' : 'text-gray-400'">{{ t('permissions.send_sms') }}</span>
                <el-switch v-model="devicePermissions.send_sms" />
            </div>
            <div class="flex items-center justify-between">
                <span class="text-sm transition-colors" :class="devicePermissions.make_call ? 'text-black font-medium' : 'text-gray-400'">{{ t('permissions.make_call') }}</span>
                <el-switch v-model="devicePermissions.make_call" />
            </div>
        </div>
        <template #footer>
            <span class="dialog-footer">
                <el-button @click="showPermissions = false">{{ t('common.cancel') }}</el-button>
                <el-button type="primary" @click="savePermissions">{{ t('common.save') }}</el-button>
            </span>
        </template>
    </el-dialog>
    <el-dialog v-model="showConfig" :title="t('settings.title')" width="500px" class="custom-dialog" align-center>
       <el-form label-position="top" class="mt-2">
         <el-form-item :label="t('settings.provider')">
           <el-select v-model="selectedProvider" :placeholder="t('settings.select_provider')" @change="updateProviderConfig">
             <el-option :label="t('settings.provider_vllm')" value="vllm" />
             <el-option :label="t('settings.provider_ollama')" value="ollama" />
             <el-option :label="t('settings.provider_bailian')" value="bailian" />
             <el-option :label="t('settings.provider_gemini')" value="gemini" />
             <el-option :label="t('settings.provider_claude')" value="claude" />
             <el-option :label="t('settings.provider_custom')" value="custom" />
           </el-select>
         </el-form-item>
         
         <el-form-item :label="t('settings.base_url')">
           <el-input v-model="config.baseUrl" placeholder="e.g. http://localhost:8000/v1" />
         </el-form-item>
         <el-form-item :label="t('settings.model_name')">
           <el-input v-model="config.model" placeholder="e.g. autoglm-phone-9b" />
         </el-form-item>
         <el-form-item :label="t('settings.api_key')">
           <el-input v-model="config.apiKey" type="password" show-password placeholder="sk-..." />
           <div class="text-xs text-gray-500 mt-1" v-if="selectedProvider === 'vllm'">{{ t('settings.local_tip') }}</div>
         </el-form-item>
       </el-form>
       <template #footer>
         <div class="flex justify-end gap-2">
            <el-button @click="showConfig = false" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">{{ t('common.cancel') }}</el-button>
            <el-button type="primary" @click="saveConfig" class="!bg-blue-600 !border-none">{{ t('common.save') }}</el-button>
         </div>
       </template>
    </el-dialog>

    <!-- Create Task Dialog -->
    <el-dialog v-model="showTaskDialog" :title="t('task.new_task_title')" width="450px" class="custom-dialog" align-center>
       <el-form label-position="top" class="mt-2">
          <el-form-item :label="t('task.type')">
             <el-radio-group v-model="newTask.type" size="small">
                <el-radio-button label="chat">{{ t('task.session') }}</el-radio-button>
                <el-radio-button label="background">{{ t('task.task') }}</el-radio-button>
             </el-radio-group>
          </el-form-item>
          <el-form-item :label="t('task.name')">
             <el-input v-model="newTask.name" :placeholder="t('task.name_placeholder')" />
          </el-form-item>
          <template v-if="newTask.type === 'background'">
              <el-form-item :label="t('task.role')">
                 <el-input v-model="newTask.role" type="textarea" :rows="2" :placeholder="t('task.role_placeholder')" />
              </el-form-item>
              <el-form-item :label="t('task.details')">
                 <el-input v-model="newTask.details" type="textarea" :rows="3" :placeholder="t('task.details_placeholder')" />
              </el-form-item>
          </template>
       </el-form>
       <template #footer>
          <div class="flex justify-end gap-2">
            <el-button @click="showTaskDialog = false" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">{{ t('common.cancel') }}</el-button>
            <el-button type="primary" @click="createTask" class="!bg-blue-600 !border-none">{{ t('common.create') }}</el-button>
          </div>
       </template>
    </el-dialog>
    
    <!-- Edit Task Name Dialog -->
    <el-dialog v-model="showEditTaskDialog" :title="t('common.rename')" width="400px" class="custom-dialog" align-center>
        <el-input v-model="editTaskNameValue" :placeholder="t('common.enter_new_name')" @keyup.enter="saveTaskName" />
        <template #footer>
            <div class="flex justify-end gap-2">
                <el-button @click="showEditTaskDialog = false" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">{{ t('common.cancel') }}</el-button>
                <el-button type="primary" @click="saveTaskName" class="!bg-blue-600 !border-none">{{ t('common.save') }}</el-button>
            </div>
        </template>
    </el-dialog>

    <!-- Device Connection Wizard -->
    <el-dialog v-model="showConnectionGuide" :title="t('wizard.title')" width="500px" class="custom-dialog" align-center :show-close="false">
       <!-- Wizard Steps (Unchanged) -->
       <div class="py-4">
         <!-- Step 1: Select Type -->
         <div v-if="wizardStep === 1" class="space-y-4">
            <h3 class="text-gray-300 text-sm font-bold mb-4">{{ t('wizard.step_type') }}</h3>
            <div class="grid grid-cols-3 gap-3">
               <div class="border border-gray-700 rounded-xl p-4 hover:border-blue-500 cursor-pointer transition-colors flex flex-col items-center gap-3 bg-[#0d1117]"
                    :class="{ '!border-blue-500 bg-blue-900/10': wizardType === 'usb' }"
                    @click="wizardType = 'usb'">
                  <el-icon class="text-3xl text-blue-400"><Connection /></el-icon>
                  <span class="text-xs font-medium text-center">{{ t('wizard.type_usb') }}</span>
               </div>
               <div class="border border-gray-700 rounded-xl p-4 hover:border-green-500 cursor-pointer transition-colors flex flex-col items-center gap-3 bg-[#0d1117]"
                    :class="{ '!border-green-500 bg-green-900/10': wizardType === 'wifi' }"
                    @click="wizardType = 'wifi'">
                  <el-icon class="text-3xl text-green-400"><Wifi /></el-icon>
                  <span class="text-xs font-medium text-center">{{ t('wizard.type_wifi') }}</span>
               </div>
               <div class="border border-gray-700 rounded-xl p-4 hover:border-purple-500 cursor-pointer transition-colors flex flex-col items-center gap-3 bg-[#0d1117]"
                    :class="{ '!border-purple-500 bg-purple-900/10': wizardType === 'webrtc' }"
                    @click="wizardType = 'webrtc'">
                  <el-icon class="text-3xl text-purple-400"><VideoCamera /></el-icon>
                  <span class="text-xs font-medium text-center">{{ t('wizard.type_webrtc') }}</span>
               </div>
            </div>
         </div>

         <!-- Step 2: USB Instructions -->
         <div v-if="wizardStep === 2 && wizardType === 'usb'" class="space-y-4 animate-fade-in">
             <div class="p-4 bg-blue-900/20 border border-blue-800 rounded-lg">
                <h4 class="font-bold text-blue-400 mb-2">{{ t('wizard.step_usb') }}</h4>
                <ol class="list-decimal list-inside text-sm text-gray-300 space-y-2">
                   <li>{{ t('wizard.usb_instr_1') }}</li>
                   <li>{{ t('wizard.usb_instr_2') }}</li>
                </ol>
             </div>
             <div class="flex justify-center py-4">
                <el-button type="primary" :loading="checkingUsb" @click="checkUsbConnection">
                   {{ t('wizard.usb_check') }}
                </el-button>
             </div>
             <div v-if="usbStatus" class="text-center text-sm font-bold" :class="usbStatus === 'found' ? 'text-green-400' : 'text-red-400'">
                {{ usbStatus === 'found' ? t('wizard.usb_found') : t('wizard.usb_not_found') }}
             </div>
         </div>

         <!-- Step 2: WiFi Setup (Mode Selection) -->
         <div v-if="wizardStep === 2 && wizardType === 'wifi'" class="space-y-6 animate-fade-in">
             <div class="border border-gray-700 rounded-lg p-4 bg-[#0d1117]">
                <div class="flex items-center justify-between mb-2">
                   <h4 class="font-bold text-gray-200 text-sm">{{ t('wizard.wifi_mode_title') }}</h4>
                   <el-tag size="small" type="info">{{ t('chat.step_1') }}</el-tag>
                </div>
                <p class="text-xs text-gray-500 mb-3">{{ t('wizard.wifi_mode_desc') }}</p>
                <el-button size="small" :loading="enablingWifi" @click="enableWifiMode">
                   {{ t('wizard.wifi_mode_btn') }}
                </el-button>
             </div>
             <div class="border border-gray-700 rounded-lg p-4 bg-[#0d1117]">
                <div class="flex items-center justify-between mb-2">
                   <h4 class="font-bold text-gray-200 text-sm">{{ t('wizard.wifi_ip_title') }}</h4>
                   <el-tag size="small" type="success">{{ t('chat.step_2') }}</el-tag>
                </div>
                <p class="text-xs text-gray-500 mb-3">{{ t('wizard.wifi_ip_desc') }}</p>
                <div class="flex gap-2">
                   <el-input v-model="wifiIp" :placeholder="t('wizard.wifi_ip_placeholder')" size="small" />
                   <el-button type="success" size="small" :loading="connectingWifi" @click="connectWifi" :disabled="!wifiIp">
                      {{ t('wizard.btn_connect') }}
                   </el-button>
                </div>
             </div>
         </div>

         <!-- Step 2: WebRTC Setup -->
         <div v-if="wizardStep === 2 && wizardType === 'webrtc'" class="space-y-4 animate-fade-in">
             <div class="border border-gray-700 rounded-lg p-6 bg-[#0d1117] flex flex-col items-center gap-4">
                <div v-if="!webrtcUrl" class="text-center">
                   <el-icon class="is-loading text-blue-500 text-2xl mb-2"><Loading /></el-icon>
                   <p class="text-xs text-gray-500">{{ t('chat.generating_session') }}</p>
                </div>
                <template v-else>
                   <div class="bg-white p-2 rounded-lg">
                      <qrcode-vue :value="webrtcUrl" :size="200" level="H" />
                   </div>
                   <div class="text-center">
                      <p class="text-sm font-bold text-gray-200 mb-1">{{ t('wizard.scan_to_connect') }}</p>
                      <p class="text-xs text-gray-500 max-w-xs mx-auto mb-2">{{ t('wizard.webrtc_desc') }}</p>
                      <div class="bg-gray-800 p-2 rounded text-[10px] text-gray-400 font-mono break-all select-all">
                         {{ webrtcUrl }}
                      </div>
                   </div>
                   <div class="flex items-center gap-2 text-xs text-blue-400 animate-pulse">
                      <el-icon><Connection /></el-icon>
                      <span>{{ t('wizard.waiting_device') }}</span>
                   </div>
                </template>
             </div>
         </div>

         <!-- Step 3: Success -->
         <div v-if="wizardStep === 3" class="text-center py-8 animate-fade-in">
             <div class="w-16 h-16 bg-green-500/20 text-green-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/50">
                <el-icon :size="32"><Check /></el-icon>
             </div>
             <h3 class="text-xl font-bold text-white">{{ t('wizard.success') }}</h3>
         </div>
       </div>
       
       <!-- Footer Navigation -->
       <template #footer>
         <div class="flex justify-between items-center border-t border-gray-700/50 pt-4">
            <el-button v-if="wizardStep > 1 && wizardStep < 3" @click="wizardStep--" class="!bg-transparent !border-gray-600 !text-gray-400 hover:!text-white">
               {{ t('wizard.btn_prev') }}
            </el-button>
            <div v-else></div>

            <div class="flex gap-2">
               <el-button v-if="wizardStep === 1" type="primary" @click="wizardStep++" :disabled="!wizardType" class="!bg-blue-600 !border-none">
                  {{ t('wizard.btn_next') }}
               </el-button>
               <el-button v-if="wizardStep === 3" type="success" @click="finishWizard" class="!bg-green-600 !border-none">
                  {{ t('wizard.btn_finish') }}
               </el-button>
               <el-button v-if="wizardStep < 3" @click="showConnectionGuide = false" link class="!text-gray-500">
                  {{ t('common.cancel') }}
               </el-button>
            </div>
         </div>
       </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import QrcodeVue from 'qrcode.vue'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import { v4 as uuidv4 } from 'uuid' // Need UUID for frontend session generation

// --- State ---
const { t, locale } = useI18n()
const sidebarOpen = ref(true)
const input = ref('')
const devices = ref<any[]>([])
const activeDeviceId = ref('')
const loadingDevices = ref(false)
const sending = ref(false)
const agentStatus = ref('idle')
const chatHistory = ref<any[]>([])
const latestScreenshot = ref('')
const wsConnected = ref(false)
const wsError = ref('')
const showConfig = ref(false)
const showPermissions = ref(false)
const devicePermissions = ref({
    install_app: false,
    payment: false,
    wechat_reply: false,
    send_sms: false,
    make_call: false
})

const openPermissions = async () => {
    if (!activeDeviceId.value) return
    try {
        const res = await api.get(`/devices/${activeDeviceId.value}/permissions`)
        devicePermissions.value = res.data
        showPermissions.value = true
    } catch (e) {
        console.error('Failed to load permissions', e)
        // Set defaults if failed
        devicePermissions.value = {
            install_app: false,
            payment: false,
            wechat_reply: false,
            send_sms: false,
            make_call: false
        }
        showPermissions.value = true
    }
}

const savePermissions = async () => {
    if (!activeDeviceId.value) return
    try {
        await api.post(`/devices/${activeDeviceId.value}/permissions`, devicePermissions.value)
        showPermissions.value = false
        ElMessage.success(t('settings.saved'))
    } catch (e) {
        console.error('Failed to save permissions', e)
        ElMessage.error(t('error.failed_save_permissions'))
    }
}
const showConnectionGuide = ref(false)
const isLandscape = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const clickEffects = ref<any[]>([])
const selectedProvider = ref('vllm')
const streamQuality = ref('auto')
const fps = ref(0)
let frameCount = 0
let lastFpsTime = Date.now()
const lastFrameTs = ref(0)
const isFetchingFrame = ref(false)
const isStreaming = ref(false)

const qualityOptions = [
    { key: '1080p' },
    { key: '720p' },
    { key: '480p' },
    { key: '360p' },
    { key: 'auto' }
]

// ... Interaction State ...---
let isDragging = false
let startX = 0
let startY = 0
let startTime = 0

// --- Wizard State ---
const wizardStep = ref(1)
const wizardType = ref<'usb' | 'wifi' | 'webrtc' | ''>('')
const checkingUsb = ref(false)
const usbStatus = ref<'found' | 'not_found' | ''>('')
const enablingWifi = ref(false)
const connectingWifi = ref(false)
const wifiIp = ref('')
const webrtcUrl = ref('')

const deviceAliases = ref<Record<string, string>>({})
const editingDeviceId = ref('')
const editName = ref('')

// --- Task State ---
const sessions = ref<any[]>([])
const visibleSessionCount = ref(5)
const visibleSessions = computed(() => sessions.value.slice(0, visibleSessionCount.value))

const handleSessionScroll = (e: Event) => {
    const target = e.target as HTMLElement
    // Check if scrolled near bottom (within 20px)
    if (target.scrollTop + target.clientHeight >= target.scrollHeight - 20) {
        if (visibleSessionCount.value < sessions.value.length) {
            visibleSessionCount.value += 5
        }
    }
}

const backgroundTasks = ref<any[]>([])
const activeTaskId = ref<string | null>(null)
const showTaskDialog = ref(false)
const hasMoreMessages = ref(true)
const isLoadingMore = ref(false)
const MESSAGES_PER_PAGE = 20
const newTask = ref({
    type: 'chat',
    name: '',
    role: '',
    details: ''
})

// Rename Task State
const showEditTaskDialog = ref(false)
const editTaskNameValue = ref('')
const taskToEdit = ref<any>(null)

// --- Input Enhancements ---
const availableApps = ref<Array<{name: string, package?: string, type: string}>>([])
const showAppSuggestions = ref(false)
const appSuggestionQuery = ref('')
const attachments = ref<any[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const inputRef = ref<any>(null)

// --- Config ---
const config = ref({
  baseUrl: 'http://localhost:8080/v1', // Model Server (vLLM)
  model: 'autoglm-phone-9b',
  apiKey: 'EMPTY'
})

// --- API ---
const isSecure = window.location.protocol === 'https:'
const hostname = window.location.hostname
const port = 8000 
const backendRootUrl = `${isSecure ? 'https' : 'http'}://${hostname}:${port}`

// Use relative path to leverage Vite Proxy (avoids CORS/SSL issues)
const apiBaseUrl = '/api'
const wsProtocol = isSecure ? 'wss:' : 'ws:'
// Use Vite Proxy for WebSocket to share the same certificate trust as the frontend
const wsBaseUrl = `${wsProtocol}//${window.location.host}/api/agent/ws`

const api = axios.create({ baseURL: apiBaseUrl }) // GUI Backend

// --- Computed ---
const filteredChatHistory = computed(() => chatHistory.value)

const activeTask = computed(() => {
    return sessions.value.find(s => s.id === activeTaskId.value) || 
           backgroundTasks.value.find(t => t.id === activeTaskId.value)
})

// --- Methods ---

const updateProviderConfig = (val: string) => {
  switch (val) {
    case 'vllm':
      config.value.baseUrl = 'http://localhost:8080/v1'
      config.value.model = 'autoglm-phone-9b'
      config.value.apiKey = 'EMPTY'
      break
    case 'ollama':
      config.value.baseUrl = 'http://localhost:11434/v1'
      config.value.model = 'autoglm-phone-9b'
      config.value.apiKey = 'ollama'
      break
    case 'bailian':
      config.value.baseUrl = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
      config.value.model = 'qwen-plus' 
      config.value.apiKey = '' 
      break
    case 'gemini':
      config.value.baseUrl = 'https://generativelanguage.googleapis.com/v1beta/openai/'
      config.value.model = 'gemini-1.5-flash'
      config.value.apiKey = ''
      break
    case 'claude':
      config.value.baseUrl = 'https://api.anthropic.com/v1'
      config.value.model = 'claude-3-haiku-20240307'
      config.value.apiKey = ''
      break
  }
}

const fetchDevices = async () => {
  loadingDevices.value = true
  try {
    const res = await api.get('/devices/')
    devices.value = res.data.map((d: any) => ({
        ...d,
        displayName: deviceAliases.value[d.id] || d.model
    }))
    if (devices.value.length > 0) {
      const current = devices.value.find((d: any) => d.id === activeDeviceId.value)
      if (!current || current.status === 'offline') {
         activeDeviceId.value = ''
         const next = devices.value.find((d: any) => d.status !== 'offline')
         if (next) {
            selectDevice(next)
         }
      }
    } else {
       activeDeviceId.value = ''
    }
  } catch (err) {
    ElMessage.error(t('error.failed_connect_backend'))
  } finally {
    loadingDevices.value = false
  }
}

const selectDevice = async (device: any) => {
  if (device.status === 'offline') {
      ElMessage.warning(t('error.cannot_select_offline'))
      return
  }
  try {
    await api.post('/devices/select', { device_id: device.id, type: device.type })
    activeDeviceId.value = device.id
  } catch (err) {
    ElMessage.error(t('error.failed_select_device'))
  }
}

const deleteDevice = async (device: any) => {
    try {
        await api.delete(`/devices/${device.id}`)
        devices.value = devices.value.filter(d => d.id !== device.id)
        if (activeDeviceId.value === device.id) {
            activeDeviceId.value = ''
        }
        ElMessage.success(t('success.device_removed'))
    } catch (err) {
        ElMessage.error(t('error.failed_remove_device'))
    }
}

const startEdit = (device: any) => {
    editingDeviceId.value = device.id
    editName.value = device.displayName || device.model || device.id
}

const cancelEdit = () => {
    editingDeviceId.value = ''
    editName.value = ''
}

const saveDeviceName = async (device: any) => {
    if (editName.value.trim()) {
        const newName = editName.value.trim()
        await db.saveDeviceAlias(device.id, newName)
        deviceAliases.value[device.id] = newName
        const idx = devices.value.findIndex(d => d.id === device.id)
        if (idx !== -1) {
            devices.value[idx].displayName = newName
        }
    }
    cancelEdit()
}

// --- Task Methods ---

const fetchData = async () => {
    if (!activeDeviceId.value) return
    
    // 1. Fetch Sessions from IndexedDB and filter by current device
    const allSessions = await db.getSessions()
    sessions.value = allSessions
        .filter((s: any) => s.deviceId === activeDeviceId.value)
        .sort((a: any, b: any) => (b.createdAt || 0) - (a.createdAt || 0))
    
    // 2. Fetch Tasks from Backend
    try {
        const res = await api.get(`/tasks/${activeDeviceId.value}`)
        backgroundTasks.value = res.data.filter((t: any) => t.type === 'background')
    } catch (e) {
        console.error('Failed to fetch tasks', e)
        backgroundTasks.value = []
        // Optional: ElMessage.error(t('error.failed_fetch_tasks'))
    }

    // Auto-select logic
    if (!activeTaskId.value) {
        // Check for an existing empty session
        let emptySession = null;
        
        // Check most recent sessions first
        for (const session of sessions.value) {
            const msgs = await db.getMessages(session.id);
            if (msgs.length === 0) {
                emptySession = session;
                break; 
            }
        }

        if (emptySession) {
            selectTask(emptySession);
        } else {
            // Create a new empty session
            await createDefaultSession();
        }
    }
}

const createDefaultSession = async () => {
    const id = uuidv4()
    const session = {
        id,
        name: `${t('debug.session_prefix')}${sessions.value.length + 1}`,
        type: 'chat',
        deviceId: activeDeviceId.value,
        createdAt: Date.now()
    }
    await db.addSession(session)
    sessions.value.unshift(session)
    selectTask(session)
}

const openCreateTaskDialog = (type = 'chat') => {
    newTask.value = { type, name: type === 'chat' ? `${t('debug.session_prefix')}${sessions.value.length + 1}` : t('debug.new_task'), role: '', details: '' }
    showTaskDialog.value = true
}

const createTask = async () => {
    if (!activeDeviceId.value) return

    if (newTask.value.type === 'chat') {
        // Create in IndexedDB
        const id = uuidv4()
        const session = {
            id,
            name: newTask.value.name,
            type: 'chat',
            deviceId: activeDeviceId.value,
            createdAt: Date.now()
        }
        await db.addSession(session)
        sessions.value.unshift(session)
        showTaskDialog.value = false
        selectTask(session)
    } else {
        // Create Background Task on Backend
        try {
            const res = await api.post('/tasks/', {
                device_id: activeDeviceId.value,
                ...newTask.value
            })
            showTaskDialog.value = false
            await fetchData() // Refresh lists
            selectTask(res.data.task)
            
            // Start immediately
            await api.post(`/tasks/${res.data.task.id}/start`)
            fetchData()
        } catch (e: any) {
            ElMessage.error(e.response?.data?.detail || t('error.failed_create_task'))
        }
    }
}

const selectTask = async (task: any) => {
    activeTaskId.value = task.id
    chatHistory.value = []
    hasMoreMessages.value = true
    
    if (task.type === 'chat') {
        // Load from DB (Paged)
        await loadMessages(task.id)
    } else {
        // Load from Backend
        try {
            const res = await api.get(`/tasks/detail/${task.id}`)
            const details = res.data.task
            chatHistory.value = convertLogsToChat(details.logs)
            if (details.details) {
                chatHistory.value.unshift({ role: 'user', content: details.details })
            }
        } catch (e) {
            console.error(e)
        }
    }
    scrollToBottom()
}

const loadMessages = async (sessionId: string, beforeId?: number) => {
    try {
        const msgs = await db.getMessages(sessionId, MESSAGES_PER_PAGE, beforeId)
        if (msgs.length < MESSAGES_PER_PAGE) {
            hasMoreMessages.value = false
        }
        
        if (beforeId) {
            chatHistory.value = [...msgs, ...chatHistory.value]
        } else {
            chatHistory.value = msgs
        }
    } catch (e) {
        console.error('Failed to load messages', e)
        // ElMessage.error(t('error.failed_load_messages'))
    }
}

const handleChatScroll = async (e: Event) => {
    const target = e.target as HTMLElement
    if (target.scrollTop === 0 && hasMoreMessages.value && !isLoadingMore.value && activeTaskId.value) {
        // Load more
        isLoadingMore.value = true
        // Capture the ID of the top message before loading
        const oldestId = chatHistory.value[0]?.id
        const oldScrollHeight = target.scrollHeight
        
        if (oldestId) {
            await loadMessages(activeTaskId.value, oldestId)
            
            // Wait for DOM update
            nextTick(() => {
                // Adjust scroll position to maintain stability
                const newScrollHeight = target.scrollHeight
                const diff = newScrollHeight - oldScrollHeight
                if (diff > 0) {
                    target.scrollTop = diff
                }
            })
        }
        isLoadingMore.value = false
    }
}

const convertLogsToChat = (logs: any[]) => {
    const history: any[] = []
    let lastMsg: any = null
    
    // Sort logs by timestamp
    logs.sort((a, b) => a.timestamp - b.timestamp)
    
    for (const log of logs) {
        if (log.level === 'thought') {
             if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
                 lastMsg.thought += log.message
             } else {
                 lastMsg = { role: 'agent', thought: log.message, isThinking: true }
                 history.push(lastMsg)
             }
        } else if (log.level === 'success') {
             if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
                 lastMsg.isThinking = false
                 lastMsg.content = log.message
             } else {
                 history.push({ role: 'agent', content: log.message })
             }
             lastMsg = null
        } else if (log.level === 'info') {
             if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
                 lastMsg.thought += '\n[INFO] ' + log.message
             }
        } else if (log.level === 'action') {
             if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
                 lastMsg.action = log.message
                 lastMsg.isThinking = false
             } else {
                 history.push({ role: 'agent', action: log.message })
                 lastMsg = null
             }
        } else if (log.level === 'error') {
             history.push({ role: 'agent', content: `${t('common.error_prefix')}${log.message}` })
             lastMsg = null
        }
    }
    return history
}

const deleteTask = async (task: any) => {
    if (task.type === 'chat') {
        await db.deleteSession(task.id)
        sessions.value = sessions.value.filter(s => s.id !== task.id)
        if (activeTaskId.value === task.id) {
            activeTaskId.value = null
            chatHistory.value = []
        }
        ElMessage.success(t('success.session_deleted'))
    } else {
        try {
            await api.delete(`/tasks/${task.id}`)
            backgroundTasks.value = backgroundTasks.value.filter(t => t.id !== task.id)
            if (activeTaskId.value === task.id) {
                activeTaskId.value = null
                chatHistory.value = []
            }
            ElMessage.success(t('success.task_deleted'))
        } catch (e) {
            ElMessage.error(t('error.failed_delete_task'))
        }
    }
}

// --- Renaming ---
const startEditTask = (task: any) => {
    taskToEdit.value = task
    editTaskNameValue.value = task.name
    showEditTaskDialog.value = true
}

const saveTaskName = async () => {
    if (!taskToEdit.value || !editTaskNameValue.value.trim()) return
    const newName = editTaskNameValue.value.trim()
    
    if (taskToEdit.value.type === 'chat') {
        await db.updateSession(taskToEdit.value.id, { name: newName })
        taskToEdit.value.name = newName // Update local ref
    } else {
        try {
            await api.put(`/tasks/${taskToEdit.value.id}`, { name: newName })
            taskToEdit.value.name = newName
        } catch (e) {
            ElMessage.error(t('error.failed_rename_task'))
        }
    }
    showEditTaskDialog.value = false
    ElMessage.success(t('success.renamed'))
}

// --- Input Enhancement Methods ---

const fetchDeviceApps = async (deviceId: string) => {
    try {
        const res = await api.get(`/devices/${deviceId}/apps`)
        // Filter out apps that are just in the static list but not actually installed
        // The backend returns {name, package, type}
        // If type is 'supported' it means it's in APP_PACKAGES and installed (or system)
        // If type is 'other' it means it's a user installed 3rd party app
        
        // We want ONLY installed apps. The backend logic for get_device_apps already does this:
        // It iterates user_packages and checks if they are in pkg_to_name.
        // It also adds supported system apps that are installed.
        // So the list returned by API *should* already be only installed apps.
        
        // However, if the user sees too many apps, maybe we should filter further?
        // But the requirement says "don't show built-in apps.py list", implying 
        // we shouldn't show apps that are NOT on the device.
        
        // The current implementation of fetchDeviceApps replaces availableApps.value completely.
        // But if fetchStaticApps was called before, availableApps might have static data.
        
        availableApps.value = res.data.apps
    } catch (e) {
        console.error('Failed to fetch device apps', e)
        // Do NOT fallback to static apps if device fetch fails, as requested
        availableApps.value = [] 
        // Optional: ElMessage.error(t('error.failed_fetch_apps'))
    }
}

const onInputChange = (val: string) => {
    const lastAt = val.lastIndexOf('@')
    if (lastAt !== -1) {
        const query = val.slice(lastAt + 1)
        if (!query.includes(' ')) {
             // Fetch apps dynamically if not already fetched for this device
             // AND ensure we are not using the static list (which might have been loaded initially)
             if (activeDeviceId.value) {
                 // Always fetch to ensure freshness and correctness, or check if we have "real" data
                 // For now, let's just fetch if empty or if we suspect it's stale/static
                 if (availableApps.value.length === 0 || availableApps.value.some(a => a.type === 'static')) {
                     fetchDeviceApps(activeDeviceId.value)
                 }
             }
             showAppSuggestions.value = true
             appSuggestionQuery.value = query.toLowerCase()
             return
        }
    }
    showAppSuggestions.value = false
}

const selectApp = (appName: string) => {
    const lastAt = input.value.lastIndexOf('@')
    if (lastAt !== -1) {
        input.value = input.value.slice(0, lastAt) + appName + ' '
    }
    showAppSuggestions.value = false
    nextTick(() => {
        if (inputRef.value) inputRef.value.focus()
    })
}

const triggerAppSelect = () => {
    if (showAppSuggestions.value) {
        showAppSuggestions.value = false
        return
    }
    const val = input.value
    if (!val.trim().endsWith('@')) {
        input.value += (val && !val.endsWith(' ') ? ' ' : '') + '@'
    }
    nextTick(() => {
        if (inputRef.value) {
            inputRef.value.focus()
        }
        onInputChange(input.value)
    })
}

const triggerUpload = (type: string) => {
    if (fileInput.value) {
        fileInput.value.accept = type === 'image' ? 'image/*' : 
                                 type === 'video' ? 'video/*' :
                                 type === 'audio' ? 'audio/*' : '*/*'
        fileInput.value.click()
    }
}

const handleFileSelect = (event: Event) => {
    const target = event.target as HTMLInputElement
    if (target.files && target.files.length > 0) {
        const file = target.files[0]
        attachments.value.push({
            name: file.name,
            type: file.type.split('/')[0],
            file: file,
            url: URL.createObjectURL(file)
        })
    }
    target.value = '' 
}

const removeAttachment = (index: number) => {
    attachments.value.splice(index, 1)
}

const handleCardAction = async (msg: any, option: any) => {
    msg.submitted = true
    msg.selectedValue = option.label
    if (msg.id) {
        await db.updateMessage(msg.id, { submitted: true, selectedValue: option.label })
    }
    
    // Send Interaction Response to Backend
    if (activeTaskId.value) {
        try {
            await api.post(`/tasks/${activeTaskId.value}/interaction`, {
                response: option.value
            })
        } catch (e) {
            console.error('Failed to send interaction response', e)
            ElMessage.error(t('error.failed_send_interaction'))
        }
    }
}

const handleCardInput = async (msg: any) => {
    if (!msg.inputValue) return
    msg.submitted = true
    if (msg.id) {
        await db.updateMessage(msg.id, { submitted: true, inputValue: msg.inputValue })
    }
    
    // Send Interaction Response to Backend
    if (activeTaskId.value) {
        try {
            await api.post(`/tasks/${activeTaskId.value}/interaction`, {
                response: msg.inputValue
            })
        } catch (e) {
            console.error('Failed to send interaction response', e)
            ElMessage.error(t('error.failed_send_interaction'))
        }
    }
}

const sendMessage = async () => {
  if (!input.value || !activeDeviceId.value || !activeTaskId.value) return

  // Debug/Test Commands for UI Cards
  if (input.value === '/debug-confirm') {
      input.value = ''
      const msg: any = {
          role: 'agent',
          type: 'confirm',
          title: 'Permission Request',
          content: 'The agent needs to install an application. Do you allow this?',
          options: [
              { label: 'Deny', value: 'No', type: 'danger' },
              { label: 'Allow', value: 'Yes', type: 'success' }
          ],
          sessionId: activeTaskId.value,
          submitted: false
      }
      chatHistory.value.push(msg)
      db.addMessage(msg).then(id => msg.id = id)
      scrollToBottom()
      return
  }
  if (input.value === '/debug-input') {
      input.value = ''
      const msg: any = {
          role: 'agent',
          type: 'input',
          title: 'SMS Verification',
          content: 'Please enter the verification code you received.',
          placeholder: '123456',
          sessionId: activeTaskId.value,
          submitted: false
      }
      chatHistory.value.push(msg)
      db.addMessage(msg).then(id => msg.id = id)
      scrollToBottom()
      return
  }
  
  const prompt = input.value
  input.value = ''
  sending.value = true
  
  // 1. Auto-rename session (IndexedDB)
  const currentTask = activeTask.value
  if (currentTask && currentTask.type === 'chat' && currentTask.name.startsWith(t('debug.session_prefix'))) {
      const newName = prompt.length > 20 ? prompt.substring(0, 20) + '...' : prompt
      await db.updateSession(currentTask.id, { name: newName })
      currentTask.name = newName
  }

  // 2. Save User Message to IndexedDB (linked to sessionId)
  const userMsg = { role: 'user', content: prompt, sessionId: activeTaskId.value }
  const id1 = await db.addMessage(userMsg)
  chatHistory.value.push({ ...userMsg, id: id1 })
  
  // 3. Add placeholder for agent
  const agentMsg = { 
      role: 'agent', 
      thought: '', 
      isThinking: true,
      sessionId: activeTaskId.value 
  }
  const id2 = await db.addMessage(agentMsg)
  chatHistory.value.push({ ...agentMsg, id: id2 })
  
  scrollToBottom()

  // 4. Trigger Backend
  try {
    // Ensure Backend Task Exists (Sync)
    try {
        await api.get(`/tasks/detail/${activeTaskId.value}`)
        // Task exists, update it with latest prompt/name
        await api.put(`/tasks/${activeTaskId.value}`, {
            name: currentTask?.name || t('debug.chat_sync'),
            details: prompt
        })
    } catch (e) {
        // Not found, create it (ephemeral or persistent depending on backend logic)
        await api.post('/tasks/', {
            id: activeTaskId.value,
            device_id: activeDeviceId.value,
            type: 'chat',
            name: currentTask?.name || t('debug.chat_sync'),
            details: prompt
        })
    }

    // Ensure apps are fetched so we can pass them to the agent
    if (availableApps.value.length === 0 && activeDeviceId.value) {
        await fetchDeviceApps(activeDeviceId.value)
    }

    // Start Execution
    await api.post(`/tasks/${activeTaskId.value}/start`, { 
        prompt,
        installed_apps: availableApps.value.map(a => ({ name: a.name, package: a.package }))
    })
    agentStatus.value = 'running'
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || t('error.failed_start_task')
    ElMessage.error(errorMsg)
    chatHistory.value.pop() 
    const errM = { role: 'agent', content: `${t('common.error_prefix')}${errorMsg}`, sessionId: activeTaskId.value }
    chatHistory.value.push(errM)
    db.addMessage(errM)
  } finally {
    sending.value = false
  }
}

const stopTask = async () => {
  if (activeTaskId.value) {
      await api.post(`/tasks/${activeTaskId.value}/stop`)
  } else {
      await api.post('/agent/stop')
  }
  agentStatus.value = 'idle'
  ElMessage.warning(t('success.task_stopped'))
}

// --- Wizard Methods ---
const checkUsbConnection = async () => {
  checkingUsb.value = true
  usbStatus.value = ''
  try {
    await fetchDevices()
    if (devices.value.length > 0) {
       usbStatus.value = 'found'
       setTimeout(() => wizardStep.value = 3, 1000)
    } else {
       usbStatus.value = 'not_found'
    }
  } catch (e) {
    usbStatus.value = 'not_found'
  } finally {
    checkingUsb.value = false
  }
}

const enableWifiMode = async () => {
  enablingWifi.value = true
  try {
    const res = await api.post('/devices/wifi/enable')
    ElMessage.success(t('success.wifi_enabled'))
    if (res.data.ip) {
      wifiIp.value = res.data.ip
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || t('error.failed_enable_wifi'))
  } finally {
    enablingWifi.value = false
  }
}

const connectWifi = async () => {
  connectingWifi.value = true
  try {
    await api.post('/devices/connect', { address: wifiIp.value, type: 'adb' })
    ElMessage.success(t('success.connected_wifi'))
    wizardStep.value = 3
    fetchDevices()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || t('error.connection_failed'))
  } finally {
    connectingWifi.value = false
  }
}

const connectWebRTC = async () => {
  try {
     const res = await api.post('/devices/webrtc/init')
     webrtcUrl.value = res.data.url
     const poll = setInterval(async () => {
        if (wizardStep.value !== 2 || wizardType.value !== 'webrtc') {
           clearInterval(poll)
           return
        }
         try {
             const res = await api.get('/devices/')
             devices.value = res.data
             const found = devices.value.find((d: any) => d.type === 'webrtc' && d.status !== 'offline')
             if (found) {
                ElMessage.success(t('success.webrtc_connected'))
                wizardStep.value = 3
                clearInterval(poll)
             }
         } catch (e) { }
     }, 2000)
   } catch (err: any) {
     console.error(err)
     ElMessage.error(t('error.failed_init_webrtc'))
   }
}

watch([wizardStep, wizardType], ([newStep, newType]) => {
   if (newStep === 2 && newType === 'webrtc') {
      connectWebRTC()
   }
})

const finishWizard = () => {
  showConnectionGuide.value = false
  wizardStep.value = 1
  wizardType.value = ''
  usbStatus.value = ''
  wifiIp.value = ''
  webrtcUrl.value = ''
}

const syncConfigToBackend = async () => {
    try {
        await api.post('/agent/config', {
            base_url: config.value.baseUrl,
            model: config.value.model,
            api_key: config.value.apiKey
        })
        console.log("Config synced to backend")
    } catch (e) {
        console.error("Failed to sync config", e)
    }
}

const saveConfig = async () => {
  const configToSave = { 
    ...config.value, 
    selectedProvider: selectedProvider.value 
  }
  await db.saveConfig(configToSave)
  await syncConfigToBackend()
  ElMessage.success(t('success.config_saved'))
  showConfig.value = false
}

const updateStreamQuality = async (key: string, silent = false) => {
    streamQuality.value = key
    let q = 60
    let w = 480
    
    switch (key) {
        case '1080p': q = 80; w = 1080; break
        case '720p': q = 70; w = 720; break
        case '480p': q = 60; w = 480; break
        case '360p': q = 50; w = 360; break
        case 'auto': q = 50; w = 360; break // Auto prioritizes speed, similar to 360p
    }
    
    try {
        await api.post('/control/stream/settings', { quality: q, max_width: w })
        if (!silent) {
            const label = t('mirror.quality_' + key)
            ElMessage.success(t('success.quality_set', { quality: label }))
        }
    } catch (e) {
        // ElMessage.error('Failed to update stream settings')
    }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// --- Screen Interaction ---
const getCoords = (event: MouseEvent) => {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const width = rect.width
  const height = rect.height
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  return {
      x: Math.max(0, Math.min(1, x / width)),
      y: Math.max(0, Math.min(1, y / height))
  }
}

const handleMouseDown = (event: MouseEvent) => {
    if (!activeDeviceId.value) return
    isDragging = true
    const coords = getCoords(event)
    startX = coords.x
    startY = coords.y
    startTime = Date.now()
}

const handleMouseMove = (event: MouseEvent) => { }

const handleMouseUp = async (event: MouseEvent) => {
    if (!isDragging) return
    isDragging = false
    const coords = getCoords(event)
    const endX = coords.x
    const endY = coords.y
    const duration = Date.now() - startTime
    const dx = endX - startX
    const dy = endY - startY
    const dist = Math.sqrt(dx*dx + dy*dy)
    
    if (dist < 0.02) {
        const clickId = Date.now()
        const target = event.currentTarget as HTMLElement
        const rect = target.getBoundingClientRect()
        const clientX = event.clientX - rect.left
        const clientY = event.clientY - rect.top
        clickEffects.value.push({ id: clickId, x: clientX, y: clientY })
        setTimeout(() => {
            clickEffects.value = clickEffects.value.filter(c => c.id !== clickId)
        }, 500)
        try {
            await api.post('/control/tap', { x: endX, y: endY })
            forceRefreshFrame()
        } catch (e) { console.error('Tap failed', e) }
    } else {
        try {
            await api.post('/control/swipe', { x1: startX, y1: startY, x2: endX, y2: endY, duration: duration })
            forceRefreshFrame()
        } catch (e) { console.error('Swipe failed', e) }
    }
}

const goHome = async () => { try { await api.post('/control/home'); forceRefreshFrame() } catch (e) { console.error(e) } }
const goBack = async () => { try { await api.post('/control/back'); forceRefreshFrame() } catch (e) { console.error(e) } }
const goRecent = async () => { try { await api.post('/control/recent'); forceRefreshFrame() } catch (e) { console.error(e) } }

// --- WebSocket ---
const connectWS = () => {
  console.log(`[Debug] Connecting WS to: ${wsBaseUrl}`)
  wsError.value = ''
  const ws = new WebSocket(wsBaseUrl)
  ws.onopen = () => { 
    console.log('[Debug] WS Connected')
    wsConnected.value = true 
    wsError.value = ''
    syncConfigToBackend()
  }
  ws.onclose = (e) => { 
    console.log('[Debug] WS Closed:', e.code, e.reason)
    wsConnected.value = false
    // Only set wsError if it's not a normal closure or if we want to show disconnect status
    // Use optional chaining or check existence
    if (!wsError.value) wsError.value = `Disconnected (Code: ${e.code})`
    setTimeout(connectWS, 3000) 
  }
  ws.onerror = (e) => { 
      console.error('[Debug] WS Error:', e)
      wsError.value = t('error.connection_blocked')
  }
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    handleWSMessage(data)
  }
}

const handleWSMessage = (data: any) => {
  if (data.type === 'log') {
    if (activeTaskId.value && data.taskId && data.taskId !== activeTaskId.value) {
        // Log is for another task (background)
        return
    }
    handleLog(data)
  } else if (data.type === 'screenshot') {
    // Legacy support or direct base64
    frameCount++
    const now = Date.now()
    if (now - lastFpsTime >= 1000) {
        fps.value = Math.round(frameCount * 1000 / (now - lastFpsTime))
        frameCount = 0
        lastFpsTime = now
    }
    latestScreenshot.value = `data:image/jpeg;base64,${data.data}`
    const img = new Image()
    img.onload = () => { isLandscape.value = img.width > img.height }
    img.src = latestScreenshot.value
  } else if (data.type === 'status') {
    agentStatus.value = data.data.state
    if (agentStatus.value !== 'running') {
       const lastMsg = chatHistory.value[chatHistory.value.length - 1]
       if (lastMsg && lastMsg.isThinking) lastMsg.isThinking = false
    }
  } else if (data.type === 'interaction') {
      const interactionMsg: any = {
          role: 'agent',
          type: data.data.type, // 'confirm' | 'input'
          title: data.data.title,
          content: data.data.content,
          options: data.data.options,
          placeholder: data.data.placeholder,
          sessionId: activeTaskId.value,
          submitted: false,
          inputValue: '',
          selectedValue: null
      }
      chatHistory.value.push(interactionMsg)
      db.addMessage(interactionMsg).then(id => interactionMsg.id = id)
      scrollToBottom()
  }
}

const startStreamLoop = async () => {
    isStreaming.value = true
    
    // Initial pre-fetch removed as per user request
    if (activeRequests === 0) {
        tryFetchFrame()
    }

    // Main loop: Just ensure we keep trying if buffer drains or errors
    // The actual "loop" is driven by tryFetchFrame calling itself or being re-triggered
    // But we need a supervisor to ensure liveness
    while (isStreaming.value && activeDeviceId.value) {
        if (activeRequests < MAX_CONCURRENT_REQUESTS) {
             tryFetchFrame()
        }
        await new Promise(resolve => setTimeout(resolve, 500)) // Check every 500ms
    }
}

// Semaphore for concurrency control
let activeRequests = 0
const MAX_CONCURRENT_REQUESTS = 1
const THROTTLE_MS = 200 // Minimum interval between frame fetches
let lastFetchStartTime = 0
let fetchController: AbortController | null = null
let currentETag: string | null = null

const forceRefreshFrame = () => {
    if (fetchController) {
        fetchController.abort()
    }
    lastFetchStartTime = 0 // Bypass throttle
    // Wait slightly for the abort to clear the active request semaphore
    setTimeout(() => tryFetchFrame(), 50)
}

const tryFetchFrame = async () => {
    // Basic throttle check (though daisy chain handles most of it, this ensures restart loop respects it)
    const now = Date.now()
    if (now - lastFetchStartTime < THROTTLE_MS && activeRequests === 0) {
        // If we are called too soon (e.g. by supervisor loop), just skip.
        // The daisy chain or next supervisor tick will handle it.
        return
    }

    if (activeRequests >= MAX_CONCURRENT_REQUESTS) return
    activeRequests++
    lastFetchStartTime = Date.now()
    
    fetchController = new AbortController()
    
    try {
        const response = await fetch(`${apiBaseUrl}/control/stream/latest`, {
            headers: { 'Cache-Control': 'no-cache' },
            signal: fetchController.signal
        })
        
        if (response.ok) {
            const tsHeader = response.headers.get('X-Timestamp')
            const currentTs = tsHeader ? parseInt(tsHeader, 10) : Date.now()
            
            // Only update if newer
            if (currentTs > lastFrameTs.value) {
                lastFrameTs.value = currentTs
                
                const blob = await response.blob()
                const url = URL.createObjectURL(blob)
                
                if (latestScreenshot.value && latestScreenshot.value.startsWith('blob:')) {
                    URL.revokeObjectURL(latestScreenshot.value)
                }
                
                latestScreenshot.value = url
                
                frameCount++
                const now = Date.now()
                if (now - lastFpsTime >= 1000) {
                    fps.value = Math.round(frameCount * 1000 / (now - lastFpsTime))
                    frameCount = 0
                    lastFpsTime = now
                }
                
                const img = new Image()
                img.onload = () => { 
                    isLandscape.value = img.width > img.height
                    
                    // CHAINING: Trigger next fetch ONLY after this one is successfully loaded and displayed
                    // AND enforce throttling
                    if (isStreaming.value && activeDeviceId.value) {
                        const elapsed = Date.now() - lastFetchStartTime
                        const delay = Math.max(0, THROTTLE_MS - elapsed)
                        setTimeout(() => tryFetchFrame(), delay)
                    }
                }
                img.onerror = () => {
                    console.error(t('debug.frame_load_failed'))
                    // Retry after short delay
                    if (isStreaming.value && activeDeviceId.value) {
                        setTimeout(() => tryFetchFrame(), 200)
                    }
                }
                img.src = url
            } else {
                // If frame was old, we still want to continue the loop!
                if (isStreaming.value && activeDeviceId.value) {
                    const elapsed = Date.now() - lastFetchStartTime
                    const delay = Math.max(0, THROTTLE_MS - elapsed)
                    setTimeout(() => tryFetchFrame(), Math.max(10, delay)) 
                }
            }
        } else if (response.status === 204) {
             // Unchanged frame (backend optimization)
             // Just wait throttle interval and retry
             if (isStreaming.value && activeDeviceId.value) {
                const elapsed = Date.now() - lastFetchStartTime
                const delay = Math.max(0, THROTTLE_MS - elapsed)
                setTimeout(() => tryFetchFrame(), Math.max(10, delay))
             }
        } else {
             // Response not OK (503 etc)
             if (isStreaming.value) {
                 if (response.status === 423) {
                     // Locked: Wait longer (e.g. 2s)
                     console.log('Device locked, waiting...')
                     setTimeout(() => tryFetchFrame(), 2000)
                 } else {
                     setTimeout(() => tryFetchFrame(), 200)
                 }
             }
        }
    } catch (e: any) {
        if (e.name === 'AbortError') return
        if (isStreaming.value) {
            // Check if error response status was 423 (axios throws on non-2xx, fetch doesn't throw on status)
            // But here we are using fetch. The catch block catches network errors.
            // Status codes are handled in the `else` block above.
            setTimeout(() => tryFetchFrame(), 200)
        }
    } finally {
        activeRequests--
        fetchController = null
    }
}

const handleLog = (data: any) => {
  const lastMsg = chatHistory.value[chatHistory.value.length - 1]
  
  if (data.level === 'thought') {
    if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
      lastMsg.thought += data.message
      if (lastMsg.id) db.updateMessage(lastMsg.id, { thought: lastMsg.thought })
    } else {
      const newMsg: any = { role: 'agent', thought: data.message, isThinking: true, sessionId: activeTaskId.value }
      chatHistory.value.push(newMsg)
      db.addMessage(newMsg).then(id => newMsg.id = id)
    }
  } else if (data.level === 'success') {
    if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
      lastMsg.isThinking = false
      lastMsg.content = data.message 
      if (lastMsg.id) db.updateMessage(lastMsg.id, { isThinking: false, content: lastMsg.content })
    } else {
      const newMsg: any = { role: 'agent', content: data.message, sessionId: activeTaskId.value }
      chatHistory.value.push(newMsg)
      db.addMessage(newMsg).then(id => newMsg.id = id)
    }
  } else if (data.level === 'info') {
       if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
         lastMsg.thought += (lastMsg.thought ? '\n' : '') + '[INFO] ' + data.message
         if (lastMsg.id) db.updateMessage(lastMsg.id, { thought: lastMsg.thought })
       }
  } else if (data.level === 'action') {
      if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
          lastMsg.action = data.message
          lastMsg.isThinking = false
          if (lastMsg.id) db.updateMessage(lastMsg.id, { isThinking: false, action: data.message })
      } else {
          const newMsg: any = { role: 'agent', action: data.message, sessionId: activeTaskId.value }
          chatHistory.value.push(newMsg)
          db.addMessage(newMsg).then(id => newMsg.id = id)
      }
      forceRefreshFrame()
  } else if (data.level === 'error') {
      ElMessage.error(data.message)
      const errorMsg: any = { role: 'agent', content: `${t('common.error_prefix')}${data.message}`, sessionId: activeTaskId.value }
      chatHistory.value.push(errorMsg)
      db.addMessage(errorMsg).then(id => errorMsg.id = id)

      if (lastMsg && lastMsg.isThinking) {
          lastMsg.isThinking = false
          if (lastMsg.id) db.updateMessage(lastMsg.id, { isThinking: false })
      }
  }
  
  scrollToBottom()
}

onMounted(async () => {
  const savedConfig = await db.getConfig()
  if (savedConfig) {
    config.value = { ...config.value, ...savedConfig }
    if (savedConfig.selectedProvider) selectedProvider.value = savedConfig.selectedProvider
    syncConfigToBackend()
  }

  // Initial Data Fetch happens in watcher after device load, or here if we want global sessions?
  // We need to fetch devices first.
  deviceAliases.value = await db.getDeviceAliases()
  fetchDevices()
  connectWS()
  
  // Init default stream settings
  // Use nextTick to ensure the method is available if order matters, though hoisting should handle it
  // But just in case of any weird scoping issue with <script setup>
  await nextTick()
  updateStreamQuality('auto', true)
  if (activeDeviceId.value) {
      startStreamLoop()
  }
})

watch(activeDeviceId, (newId) => {
    if (newId) {
        visibleSessionCount.value = 5
        activeTaskId.value = null 
        chatHistory.value = []
        fetchDeviceApps(newId)
        fetchData() // Replaces fetchTasks
        startStreamLoop() // Start polling
    } else {
        isStreaming.value = false // Stop polling
        sessions.value = []
        backgroundTasks.value = []
        activeTaskId.value = null
        chatHistory.value = []
        availableApps.value = []
    }
})
</script>

<style scoped>
/* Custom Styles for deep selectors */
:deep(.el-input__wrapper) {
  background-color: #161b22;
  box-shadow: none;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 12px 16px;
}
:deep(.el-input__wrapper.is-focus) {
  border-color: #58a6ff;
  box-shadow: 0 0 0 1px #58a6ff;
}
:deep(.el-input__inner) {
  color: #e6edf3;
}

/* Custom Dialog */
:deep(.custom-dialog) {
  background-color: #161b22;
  border: 1px solid #30363d;
  border-radius: 16px;
}
:deep(.dark-dialog) {
    background-color: #ffffff;
    border-radius: 12px;
}
:deep(.permissions-dialog .el-dialog__title) {
    color: #000000 !important;
    font-weight: 600;
}
:deep(.el-dialog__title) { color: #e6edf3; }
:deep(.el-form-item__label) { color: #8b949e; }
:deep(.el-dialog__headerbtn .el-dialog__close) { color: #8b949e; }

/* Transitions */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease-out;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(-20px);
  opacity: 0;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #58a6ff;
}
</style>
