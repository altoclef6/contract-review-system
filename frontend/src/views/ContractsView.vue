<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { api } from '../api'
const items=ref<any[]>([]); const search=ref(''); const loading=ref(false)
async function load(){loading.value=true;try{items.value=(await api.get('/contracts',{params:{search:search.value,page_size:50}})).data.data.items}catch{}finally{loading.value=false}}
onMounted(load)
const category:any={procurement:'采购合同',sales:'销售合同',labor:'劳动合同',lease:'租赁合同',nda:'保密协议',service:'服务合同',other:'其他'}
</script>
<template><div class="page-head"><div><h1>合同中心</h1><p>统一管理合同分类、版本、状态与归档</p></div><router-link to="/review"><el-button type="primary">上传合同</el-button></router-link></div><div class="toolbar"><el-input v-model="search" placeholder="搜索合同名称、相对方或标签" clearable @keyup.enter="load"/><el-button @click="load">查询</el-button></div><section class="panel table-panel"><el-table v-loading="loading" :data="items"><el-table-column prop="title" label="合同名称" min-width="220"/><el-table-column label="分类" width="110"><template #default="s">{{category[s.row.category]}}</template></el-table-column><el-table-column prop="counterparty" label="相对方" min-width="160"/><el-table-column prop="status" label="状态" width="110"/><el-table-column label="标签" min-width="150"><template #default="s"><el-tag v-for="tag in s.row.tags" :key="tag" size="small">{{tag}}</el-tag></template></el-table-column><el-table-column prop="updated_at" label="更新时间" width="190"/></el-table></section></template>
