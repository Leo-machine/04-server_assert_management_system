/**
 * 开发启动脚本：npm run dev 时自动拉起后端（8000）+ 前端（vite）。
 * 后端未运行则以分离进程启动（脱离本进程生命周期，终端退出后仍存活）。
 */
import { spawn } from 'node:child_process'
import { openSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const backendDir = path.resolve(frontendDir, '../backend')
const PY = path.join(backendDir, '.venv/bin/python')
const LOG = '/tmp/uvicorn_parts.log'

async function backendHealthy() {
  try {
    const r = await fetch('http://127.0.0.1:8000/api/health', { signal: AbortSignal.timeout(1500) })
    return r.ok
  } catch {
    return false
  }
}

async function ensureBackend() {
  if (await backendHealthy()) {
    console.log('[dev] 后端 8000 已在运行')
    return
  }
  console.log('[dev] 后端未运行，正在拉起 uvicorn…')
  const out = openSync(LOG, 'a')
  const child = spawn(PY, ['-m', 'uvicorn', 'app.main:app', '--reload', '--reload-dir', 'app', '--port', '8000'], {
    cwd: backendDir,
    detached: true,
    stdio: ['ignore', out, out],
  })
  child.unref()
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 500))
    if (await backendHealthy()) {
      console.log('[dev] 后端已就绪 ✅')
      return
    }
  }
  console.error(`[dev] 后端启动超时，日志见 ${LOG}`)
}

await ensureBackend()

// 前端（保持前台，Ctrl+C 退出）
const vite = spawn('npx', ['vite'], { cwd: frontendDir, stdio: 'inherit' })
vite.on('exit', (code) => process.exit(code ?? 0))
