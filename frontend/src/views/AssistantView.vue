<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'; import { api } from '../api'
const sessions=ref<any[]>([]);const current=ref<any>();const input=ref('');const sending=ref(false)
async function load(){sessions.value=(await api.get('/chats')).data.data;if(sessions.value.length)current.value=sessions.value[0]}
async function create(){current.value=(await api.post('/chats',{title:'合同法务咨询'})).data.data;sessions.value.unshift(current.value)}
async function send(){if(!input.value.trim()||!current.value)return;const text=input.value;input.value='';sending.value=true;try{current.value=(await api.post(`/chats/${current.value.id}/messages`,{message:text})).data.data.session;await nextTick()}finally{sending.value=false}}
onMounted(load)
</script>
<template><div class="assistant-layout"><aside class="sessions"><el-button type="primary" class="full" @click="create">新建对话</el-button><button v-for="s in sessions" :key="s.id" :class="{active:current?.id===s.id}" @click="current=s">{{s.title}}</button></aside><section class="conversation"><div v-if="!current" class="empty-chat"><h1>AI 法务助手</h1><p>解释条款、识别风险、生成修改意见和补充条款</p><el-button type="primary" @click="create">开始对话</el-button></div><template v-else><header><h2>{{current.title}}</h2><span>上下文连续对话</span></header><div class="messages"><div v-for="m in current.messages" :key="m.id" :class="['message',m.role]"><b>{{m.role==='user'?'你':'衡契 AI'}}</b><p>{{m.content}}</p></div><div v-if="sending" class="message assistant"><b>衡契 AI</b><p>正在分析合同上下文...</p></div></div><footer><el-input v-model="input" type="textarea" :rows="2" resize="none" placeholder="询问某个风险、法律术语或要求生成条款" @keydown.ctrl.enter="send"/><el-button type="primary" :loading="sending" @click="send">发送</el-button></footer></template></section></div></template>
