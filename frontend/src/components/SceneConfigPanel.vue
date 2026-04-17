<template>
  <transition name="modal">
    <div v-if="visible" class="scene-config-overlay" @click.self="close">
      <div class="scene-config-modal">
        <header class="modal-header">
          <div class="title-block">
            <span class="title-deco">◆</span>
            <h2 class="title">场景配置（热配置）</h2>
            <span class="subtitle">编辑角色与触发事件，让平台支持任意哲学场景</span>
          </div>
          <button class="close-btn" @click="close">×</button>
        </header>

        <!-- 场景选择器 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <label class="field-label">已有场景</label>
            <select v-model="selectedScene" class="select" @change="onSelectScene">
              <option value="">— 新建场景 —</option>
              <option v-for="s in sceneList" :key="s.file_name" :value="s.scene_name">
                {{ s.scene_name }}（{{ s.actors_count }} 角色）
              </option>
            </select>
            <button class="ghost-btn" @click="reloadScenes" :disabled="loading">
              ↻ 刷新
            </button>
          </div>
          <div class="toolbar-right">
            <button
              v-if="selectedScene"
              class="ghost-btn danger"
              @click="onDelete"
              :disabled="saving"
            >
              删除该场景
            </button>
          </div>
        </div>

        <div class="content-grid">
          <!-- 左：场景元信息 + 初始帖子 -->
          <section class="left-col">
            <div class="card">
              <h3 class="card-title">场景基本信息</h3>
              <div class="field">
                <label class="field-label">场景名称 *</label>
                <input
                  v-model.trim="form.scene_name"
                  class="input"
                  placeholder="如：明朝大礼议事件——廷议风暴"
                />
              </div>
              <div class="field">
                <label class="field-label">场景描述/模拟提示词 *</label>
                <textarea
                  v-model="form.scene_description"
                  class="textarea"
                  rows="4"
                  placeholder="描述该哲学/历史/社会实验的背景设定，会作为 Agent 的世界观"
                />
              </div>
              <div class="field">
                <label class="field-label">触发事件描述</label>
                <textarea
                  v-model="form.scene_event"
                  class="textarea"
                  rows="3"
                  placeholder="模拟启动时的核心事件，决定初始帖子的方向"
                />
              </div>
            </div>

            <div class="card">
              <div class="card-title-row">
                <h3 class="card-title">初始帖子（1–5 条）</h3>
                <button
                  class="ghost-btn small"
                  :disabled="form.initial_posts.length >= 5"
                  @click="addPost"
                >
                  + 新增帖子
                </button>
              </div>
              <div v-if="form.initial_posts.length === 0" class="empty-state">
                暂无初始帖子，点击右上角“新增帖子”添加。
              </div>
              <div
                v-for="(post, i) in form.initial_posts"
                :key="i"
                class="post-item"
              >
                <div class="post-row">
                  <span class="post-idx">#{{ i + 1 }}</span>
                  <select v-model="post.poster_type" class="select small">
                    <option value="">— 任选发布者 —</option>
                    <option v-for="lbl in availableLabels" :key="lbl" :value="lbl">
                      {{ lbl }}
                    </option>
                  </select>
                  <select v-model="post.platform" class="select small">
                    <option value="both">双平台</option>
                    <option value="twitter">Twitter (Info Plaza)</option>
                    <option value="reddit">Reddit (Topic Community)</option>
                  </select>
                  <button class="icon-btn" @click="removePost(i)" title="删除">×</button>
                </div>
                <textarea
                  v-model="post.content"
                  class="textarea"
                  rows="2"
                  placeholder="帖子内容，将在模拟启动时由对应类型的角色发出"
                />
              </div>
            </div>
          </section>

          <!-- 右：角色列表 -->
          <section class="right-col">
            <div class="card actors-card">
              <div class="card-title-row">
                <h3 class="card-title">角色列表（{{ form.actors.length }}）</h3>
                <button class="ghost-btn small" @click="addActor">+ 新增角色</button>
              </div>
              <div v-if="form.actors.length === 0" class="empty-state">
                请至少添加一个角色。
              </div>
              <div
                v-for="(actor, i) in form.actors"
                :key="i"
                class="actor-card"
              >
                <div class="actor-row">
                  <input
                    v-model.trim="actor.name"
                    class="input small"
                    placeholder="角色名称 *"
                  />
                  <input
                    v-model.trim="actor.label"
                    class="input small"
                    placeholder="阶层/类型 *（如 Philosopher）"
                  />
                  <input
                    v-model.trim="actor.personality"
                    class="input small"
                    placeholder="性格关键词"
                  />
                  <button class="icon-btn" @click="removeActor(i)" title="删除">×</button>
                </div>
                <textarea
                  v-model="actor.summary"
                  class="textarea"
                  rows="2"
                  placeholder="背景简介（1-2 句话）"
                />
              </div>
            </div>
          </section>
        </div>

        <!-- 底部状态 / 操作 -->
        <footer class="modal-footer">
          <div class="footer-msg">
            <span v-if="errorMsg" class="msg error">⚠ {{ errorMsg }}</span>
            <span v-else-if="successMsg" class="msg success">✓ {{ successMsg }}</span>
          </div>
          <div class="footer-actions">
            <button class="ghost-btn" @click="close">取消</button>
            <button class="primary-btn" :disabled="saving" @click="onSave">
              {{ saving ? '保存中…' : '保存配置' }}
            </button>
            <button
              class="primary-btn dark"
              :disabled="saving || !form.scene_name"
              @click="onApply"
            >
              应用到模拟
            </button>
          </div>
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  listSceneConfigs,
  getSceneConfig,
  saveSceneConfig,
  deleteSceneConfig,
} from '../api/sceneConfig'

const props = defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'apply'])

const sceneList = ref([])
const selectedScene = ref('')
const form = ref(emptyForm())
const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

function emptyForm() {
  return {
    scene_name: '',
    scene_description: '',
    scene_event: '',
    actors: [],
    initial_posts: [],
  }
}

const availableLabels = computed(() => {
  return [...new Set(form.value.actors.map(a => (a.label || '').trim()).filter(Boolean))]
})

watch(
  () => props.visible,
  (v) => {
    if (v) {
      reloadScenes()
      errorMsg.value = ''
      successMsg.value = ''
    }
  },
)

async function reloadScenes() {
  loading.value = true
  try {
    const res = await listSceneConfigs()
    sceneList.value = res?.data || []
    // 默认选中第一个场景，便于"加载已有"
    if (!selectedScene.value && sceneList.value.length > 0) {
      selectedScene.value = sceneList.value[0].scene_name
      await onSelectScene()
    }
  } catch (e) {
    errorMsg.value = `加载场景列表失败：${e.message || e}`
  } finally {
    loading.value = false
  }
}

async function onSelectScene() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!selectedScene.value) {
    form.value = emptyForm()
    return
  }
  try {
    const res = await getSceneConfig(selectedScene.value)
    const data = res?.data
    if (data) {
      form.value = {
        scene_name: data.scene_name || '',
        scene_description: data.scene_description || '',
        scene_event: data.scene_event || '',
        actors: (data.actors || []).map(a => ({ ...a })),
        initial_posts: (data.initial_posts || []).map(p => ({
          content: p.content || '',
          poster_type: p.poster_type || '',
          platform: p.platform || 'both',
        })),
      }
    }
  } catch (e) {
    errorMsg.value = `加载场景失败：${e.message || e}`
  }
}

function addActor() {
  form.value.actors.push({ name: '', label: '', summary: '', personality: '' })
}

function removeActor(idx) {
  form.value.actors.splice(idx, 1)
}

function addPost() {
  if (form.value.initial_posts.length >= 5) return
  form.value.initial_posts.push({
    content: '',
    poster_type: '',
    platform: 'both',
  })
}

function removePost(idx) {
  form.value.initial_posts.splice(idx, 1)
}

async function onSave() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!form.value.scene_name.trim()) {
    errorMsg.value = '场景名称不能为空'
    return
  }
  if (form.value.actors.length === 0) {
    errorMsg.value = '请至少添加一个角色'
    return
  }
  saving.value = true
  try {
    const res = await saveSceneConfig({
      scene_name: form.value.scene_name.trim(),
      scene_description: form.value.scene_description,
      scene_event: form.value.scene_event,
      actors: form.value.actors,
      initial_posts: form.value.initial_posts,
    })
    successMsg.value = `已保存：${res.data.scene_name}`
    selectedScene.value = res.data.scene_name
    await reloadScenes()
  } catch (e) {
    errorMsg.value = `保存失败：${e.message || e}`
  } finally {
    saving.value = false
  }
}

async function onDelete() {
  if (!selectedScene.value) return
  if (!confirm(`确定删除场景「${selectedScene.value}」？`)) return
  try {
    await deleteSceneConfig(selectedScene.value)
    successMsg.value = '已删除'
    selectedScene.value = ''
    form.value = emptyForm()
    await reloadScenes()
  } catch (e) {
    errorMsg.value = `删除失败：${e.message || e}`
  }
}

async function onApply() {
  // 应用前先保存（确保后端有最新版本）
  await onSave()
  if (errorMsg.value) return
  emit('apply', form.value.scene_name)
  close()
}

function close() {
  emit('close')
}
</script>

<style scoped>
.scene-config-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.scene-config-modal {
  background: #fff;
  width: min(1080px, 100%);
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  border-radius: 6px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid #ececec;
}
.title-block { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.title-deco { color: #FF6B35; font-size: 14px; }
.title { margin: 0; font-size: 18px; letter-spacing: 0.05em; }
.subtitle { color: #888; font-size: 12px; }
.close-btn {
  border: none; background: transparent; font-size: 26px; cursor: pointer; color: #999;
  line-height: 1;
}
.close-btn:hover { color: #000; }

.toolbar {
  padding: 14px 24px;
  border-bottom: 1px solid #f2f2f2;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-left, .toolbar-right { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  padding: 16px 24px;
  overflow-y: auto;
  flex: 1;
}
@media (max-width: 880px) {
  .content-grid { grid-template-columns: 1fr; }
}

.card {
  background: #fafafa;
  border: 1px solid #ececec;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.card-title { margin: 0 0 12px; font-size: 14px; letter-spacing: 0.05em; }
.card-title-row {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
}

.field { margin-bottom: 12px; }
.field-label {
  display: block;
  font-size: 12px;
  color: #777;
  margin-bottom: 4px;
  letter-spacing: 0.04em;
}

.input, .select, .textarea {
  width: 100%;
  border: 1px solid #ddd;
  background: #fff;
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  color: #222;
  box-sizing: border-box;
  border-radius: 3px;
  outline: none;
  transition: border-color 0.15s;
}
.input:focus, .select:focus, .textarea:focus { border-color: #FF6B35; }
.input.small, .select.small { padding: 6px 8px; font-size: 12px; }
.textarea { resize: vertical; min-height: 60px; line-height: 1.5; }

.empty-state {
  padding: 12px;
  text-align: center;
  color: #999;
  font-size: 12px;
  background: #fff;
  border: 1px dashed #e0e0e0;
}

.post-item, .actor-card {
  background: #fff;
  border: 1px solid #ececec;
  padding: 10px;
  margin-bottom: 8px;
}
.post-row, .actor-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.post-idx {
  font-family: 'JetBrains Mono', monospace;
  color: #999;
  font-size: 12px;
  min-width: 28px;
}
.actor-row .input { flex: 1; min-width: 100px; }
.post-row .select { flex: 1; min-width: 120px; }

.icon-btn {
  width: 28px;
  height: 28px;
  border: 1px solid #eee;
  background: #fff;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  color: #999;
}
.icon-btn:hover { border-color: #C5283D; color: #C5283D; }

.modal-footer {
  border-top: 1px solid #ececec;
  padding: 14px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.footer-msg { flex: 1; }
.msg { font-size: 12px; }
.msg.error { color: #C5283D; }
.msg.success { color: #1A936F; }
.footer-actions { display: flex; gap: 10px; }

.ghost-btn {
  border: 1px solid #ddd;
  background: #fff;
  padding: 7px 14px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  letter-spacing: 0.04em;
  border-radius: 3px;
}
.ghost-btn:hover:not(:disabled) { border-color: #000; }
.ghost-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn.small { padding: 5px 10px; font-size: 11px; }
.ghost-btn.danger { color: #C5283D; border-color: #f0d4d8; }
.ghost-btn.danger:hover:not(:disabled) { border-color: #C5283D; background: #fff5f5; }

.primary-btn {
  background: #FF6B35;
  color: #fff;
  border: none;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  border-radius: 3px;
}
.primary-btn:hover:not(:disabled) { background: #E55A26; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.primary-btn.dark { background: #000; }
.primary-btn.dark:hover:not(:disabled) { background: #333; }

/* 进出场动画 */
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
