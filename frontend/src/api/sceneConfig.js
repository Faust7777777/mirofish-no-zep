import service from './index'

/**
 * 列出所有已保存的场景配置摘要
 */
export const listSceneConfigs = () => {
  return service.get('/api/scene-config/list')
}

/**
 * 读取指定场景配置
 * @param {string} sceneName
 */
export const getSceneConfig = (sceneName) => {
  return service.get(`/api/scene-config/${encodeURIComponent(sceneName)}`)
}

/**
 * 保存（新建/覆盖）场景配置
 * @param {Object} payload - { scene_name, scene_description, scene_event, actors, initial_posts }
 */
export const saveSceneConfig = (payload) => {
  return service.post('/api/scene-config/save', payload)
}

/**
 * 删除指定场景配置
 * @param {string} sceneName
 */
export const deleteSceneConfig = (sceneName) => {
  return service.delete(`/api/scene-config/${encodeURIComponent(sceneName)}`)
}
