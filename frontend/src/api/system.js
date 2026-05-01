import api from './index'

export function getStartupTime() {
  return api.get('/system/startup')
}
