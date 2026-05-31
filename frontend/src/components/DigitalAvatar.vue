<template>
  <div class="digital-avatar" :class="status">
    <div class="avatar-wrap">
      <svg viewBox="0 0 140 170" class="robot-svg">
        <defs>
          <!-- 金属机身渐变 -->
          <linearGradient id="metalGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#f5f7fa" />
            <stop offset="40%" stop-color="#e4e7ed" />
            <stop offset="100%" stop-color="#c0c4cc" />
          </linearGradient>
          <!-- 头部金属 -->
          <linearGradient id="headMetal" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#ffffff" />
            <stop offset="50%" stop-color="#e8ecf1" />
            <stop offset="100%" stop-color="#b8c0c9" />
          </linearGradient>
          <!-- 屏幕 -->
          <radialGradient id="screenGrad" cx="0.5" cy="0.5" r="0.6">
            <stop offset="0%" stop-color="#1a2a3a" />
            <stop offset="100%" stop-color="#0d1b2a" />
          </radialGradient>
          <!-- LED 发光 -->
          <radialGradient id="ledGrad" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%" stop-color="#67c23a" />
            <stop offset="60%" stop-color="#4a9e22" />
            <stop offset="100%" stop-color="#2d6b12" />
          </radialGradient>
          <!-- 天线球发光 -->
          <radialGradient id="antennaGrad" cx="0.3" cy="0.3" r="0.6">
            <stop offset="0%" stop-color="#ff6b6b" />
            <stop offset="100%" stop-color="#c0392b" />
          </radialGradient>
          <!-- 阴影 -->
          <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <!-- 身体/底座 -->
        <g class="body">
          <!-- 主躯干 -->
          <rect x="35" y="125" width="70" height="35" rx="12" fill="url(#metalGrad)" stroke="#909399" stroke-width="1.5" />
          <!-- 胸口面板 -->
          <rect x="48" y="133" width="44" height="20" rx="4" fill="#2c3e50" stroke="#409eff" stroke-width="1" />
          <!-- 胸口指示灯 -->
          <circle cx="58" cy="143" r="3" fill="#67c23a" class="chest-led" />
          <circle cx="70" cy="143" r="3" fill="#e6a23c" class="chest-led" />
          <circle cx="82" cy="143" r="3" fill="#f56c6c" class="chest-led" />
          <!-- 机械纹理 -->
          <line x1="40" y1="138" x2="44" y2="138" stroke="#909399" stroke-width="1.5" stroke-linecap="round" />
          <line x1="96" y1="138" x2="100" y2="138" stroke="#909399" stroke-width="1.5" stroke-linecap="round" />
          <line x1="40" y1="148" x2="44" y2="148" stroke="#909399" stroke-width="1.5" stroke-linecap="round" />
          <line x1="96" y1="148" x2="100" y2="148" stroke="#909399" stroke-width="1.5" stroke-linecap="round" />
        </g>

        <!-- 脖子 -->
        <rect x="60" y="115" width="20" height="14" fill="#c0c4cc" stroke="#909399" stroke-width="1" rx="3" />
        <line x1="58" y1="120" x2="82" y2="120" stroke="#909399" stroke-width="1" />
        <line x1="58" y1="124" x2="82" y2="124" stroke="#909399" stroke-width="1" />

        <!-- 头部 -->
        <g class="head">
          <!-- 主轮廓 -->
          <rect x="25" y="30" width="90" height="88" rx="28" fill="url(#headMetal)" stroke="#909399" stroke-width="2" />
          <!-- 顶部装饰条 -->
          <rect x="35" y="36" width="70" height="6" rx="3" fill="#c0c4cc" stroke="#909399" stroke-width="0.5" />
          <!-- 侧边螺丝 -->
          <circle cx="32" cy="55" r="2.5" fill="#c0c4cc" stroke="#909399" stroke-width="1" />
          <circle cx="108" cy="55" r="2.5" fill="#c0c4cc" stroke="#909399" stroke-width="1" />
          <circle cx="32" cy="95" r="2.5" fill="#c0c4cc" stroke="#909399" stroke-width="1" />
          <circle cx="108" cy="95" r="2.5" fill="#c0c4cc" stroke="#909399" stroke-width="1" />

          <!-- 面部屏幕 -->
          <rect x="38" y="48" width="64" height="56" rx="16" fill="url(#screenGrad)" stroke="#34495e" stroke-width="2" />

          <!-- 眼睛 -->
          <g class="eyes">
            <!-- 左眼 -->
            <circle cx="55" cy="72" r="10" fill="url(#ledGrad)" class="eye-left" filter="url(#glow)" />
            <circle cx="55" cy="72" r="4" fill="#a8e063" opacity="0.8" />
            <circle cx="57" cy="70" r="2" fill="#fff" opacity="0.9" />
            <!-- 右眼 -->
            <circle cx="85" cy="72" r="10" fill="url(#ledGrad)" class="eye-right" filter="url(#glow)" />
            <circle cx="85" cy="72" r="4" fill="#a8e063" opacity="0.8" />
            <circle cx="87" cy="70" r="2" fill="#fff" opacity="0.9" />
          </g>

          <!-- 嘴巴/音波面板 -->
          <g class="mouth-group">
            <!-- 默认线条 -->
            <line x1="62" y1="94" x2="78" y2="94" stroke="#67c23a" stroke-width="2.5" stroke-linecap="round" class="mouth-line" />
            <!-- 音波条（speaking） -->
            <rect x="55" y="90" width="4" height="8" rx="2" fill="#67c23a" class="bar bar-1" />
            <rect x="62" y="87" width="4" height="14" rx="2" fill="#85ce61" class="bar bar-2" />
            <rect x="69" y="89" width="4" height="10" rx="2" fill="#67c23a" class="bar bar-3" />
            <rect x="76" y="86" width="4" height="16" rx="2" fill="#95d475" class="bar bar-4" />
            <rect x="83" y="91" width="4" height="6" rx="2" fill="#67c23a" class="bar bar-5" />
          </g>
        </g>

        <!-- 天线 -->
        <g class="antenna">
          <line x1="70" y1="30" x2="70" y2="12" stroke="#c0c4cc" stroke-width="3" stroke-linecap="round" />
          <circle cx="70" cy="10" r="6" fill="url(#antennaGrad)" stroke="#a93226" stroke-width="1" class="antenna-ball" />
          <!-- 天线底座 -->
          <ellipse cx="70" cy="30" rx="8" ry="3" fill="#c0c4cc" stroke="#909399" stroke-width="1" />
        </g>
      </svg>

      <!-- 状态标签 -->
      <div class="status-tag">{{ statusText }}</div>
    </div>

    <!-- 声波动画 -->
    <div class="sound-waves" v-if="showWaves">
      <span v-for="i in 5" :key="i" :style="{ animationDelay: `${i * 0.1}s` }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'listening', 'thinking', 'speaking'].includes(v)
  }
})

const statusText = computed(() => {
  const map = {
    idle: '小餐',
    listening: '聆听中',
    thinking: '思考中',
    speaking: '说话中'
  }
  return map[props.status] || '小餐'
})

const showWaves = computed(() => props.status === 'listening' || props.status === 'speaking')
</script>

<style scoped>
.digital-avatar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.avatar-wrap {
  position: relative;
  width: 55px;
  height: 64px;
}

.robot-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 3px 10px rgba(0, 0, 0, 0.12));
  overflow: visible;
}

/* ========== idle：呼吸灯 + 胸口灯闪烁 ========== */
.idle .avatar-wrap {
  animation: breathe 3s ease-in-out infinite;
}

.idle .eyes circle:first-child {
  animation: ledPulse 2.5s ease-in-out infinite;
}

.idle .chest-led:nth-child(1) {
  animation: chestBlink 2s ease-in-out infinite;
}
.idle .chest-led:nth-child(2) {
  animation: chestBlink 2s ease-in-out infinite 0.3s;
}
.idle .chest-led:nth-child(3) {
  animation: chestBlink 2s ease-in-out infinite 0.6s;
}

.idle .mouth-line {
  opacity: 1;
}
.idle .bar {
  opacity: 0;
}

@keyframes breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

@keyframes ledPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

@keyframes chestBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* ========== listening：天线闪烁 + 头部微转 ========== */
.listening .avatar-wrap {
  animation: tilt 1.5s ease-in-out infinite alternate;
}

.listening .antenna-ball {
  animation: antennaBlink 0.6s ease-in-out infinite alternate;
}

.listening .mouth-line {
  opacity: 1;
}
.listening .bar {
  opacity: 0;
}

@keyframes tilt {
  from { transform: rotate(-2deg); }
  to { transform: rotate(2deg); }
}

@keyframes antennaBlink {
  from { opacity: 1; filter: brightness(1); }
  to { opacity: 0.5; filter: brightness(1.5); }
}

/* ========== thinking：眼睛快速闪烁 + 震动 ========== */
.thinking .avatar-wrap {
  animation: shake 0.3s ease-in-out infinite;
}

.thinking .eyes circle:first-child {
  animation: ledFastBlink 0.4s ease-in-out infinite alternate;
}

.thinking .mouth-line {
  opacity: 1;
  stroke: #e6a23c;
}
.thinking .bar {
  opacity: 0;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-1px); }
  75% { transform: translateX(1px); }
}

@keyframes ledFastBlink {
  from { opacity: 1; }
  to { opacity: 0.4; }
}

/* ========== speaking：音波条动画 + 点头 ========== */
.speaking .avatar-wrap {
  animation: nod 0.6s ease-in-out infinite alternate;
}

.speaking .mouth-line {
  opacity: 0;
}
.speaking .bar {
  opacity: 1;
}

.speaking .bar-1 { animation: barWave 0.5s ease-in-out infinite alternate; }
.speaking .bar-2 { animation: barWave 0.5s ease-in-out infinite alternate 0.1s; }
.speaking .bar-3 { animation: barWave 0.5s ease-in-out infinite alternate 0.2s; }
.speaking .bar-4 { animation: barWave 0.5s ease-in-out infinite alternate 0.15s; }
.speaking .bar-5 { animation: barWave 0.5s ease-in-out infinite alternate 0.05s; }

@keyframes nod {
  from { transform: translateY(0); }
  to { transform: translateY(1.5px); }
}

@keyframes barWave {
  from { transform: scaleY(0.4); opacity: 0.5; }
  to { transform: scaleY(1); opacity: 1; }
}

/* 嘴型过渡 */
.mouth-group line,
.mouth-group rect {
  transition: opacity 0.15s ease;
  transform-origin: center;
}

/* 状态标签 */
.status-tag {
  position: absolute;
  bottom: 0px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.72);
  color: #fff;
  font-size: 10px;
  padding: 2px 10px;
  border-radius: 10px;
  white-space: nowrap;
  letter-spacing: 0.5px;
}

/* ========== 声波动画 ========== */
.sound-waves {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 18px;
}

.sound-waves span {
  display: block;
  width: 3.5px;
  background: linear-gradient(to top, #67c23a, #95d475);
  border-radius: 2px;
  animation: wave 0.7s ease-in-out infinite;
}

@keyframes wave {
  0%, 100% { height: 5px; opacity: 0.5; }
  50% { height: 18px; opacity: 1; }
}
</style>
