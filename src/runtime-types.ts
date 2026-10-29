import type { Readable, Writable } from 'node:stream'
import type { SubprocessRuntime, SubprocessSpawnSpec, SubprocessStdio } from '@deepseek-ai/dsh-subprocess'

/** The bounded reader forms accepted from DSH and the test subprocess adapter. */
export interface CollectedReader {
  readFrom(offset: number): string | { text?: string; lossy?: boolean } | undefined
}

export interface ProcessHandle {
  stdin?: Writable | null
  stdout?: Readable | null
  collected?: { stdout?: CollectedReader; stderr?: CollectedReader }
  done: Promise<{ exitCode: number | null }>
  terminate(): void
  waitForExit(): Promise<unknown>
}

export type ProcessStdio = Partial<SubprocessStdio>

/** Only the host subprocess operations consumed by this plugin. */
export interface SubprocessAdapter extends Pick<SubprocessRuntime, 'resolveExecutable'> {
  spawn(spec: SubprocessSpawnSpec): ProcessHandle
}

export interface RuntimeContext {
  cwd: string
  signal: AbortSignal
}

export interface EncodeParams {
  quality: number
  motion_quality: number
  lossy_quality: number
  fps: number
  width: number
  height: number
  start: number
  duration_seconds: number
}
