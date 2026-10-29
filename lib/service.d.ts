import { AmberError } from './options.js';
import type { AmberConfig, ClipInfo, ClipOptions, GifArguments } from './options.js';
import type { BudgetAdjustment, BudgetAttempt } from './budget.js';
import { JobQueue, Runtime } from './runtime.js';
import type { SubprocessRuntime } from '@deepseek-ai/dsh-subprocess';
import type { WorkingDirectoryService } from '@deepseek-ai/dsh-working-directory';
export interface ServiceContext {
    subprocess: Pick<SubprocessRuntime, 'spawn' | 'resolveExecutable'>;
    workingDirectory: Pick<WorkingDirectoryService, 'ensure'>;
}
export interface ExecutionContext {
    agent?: Parameters<WorkingDirectoryService['ensure']>[0];
    signal?: AbortSignal;
}
export interface JobContext {
    cwd: string | null;
    outputDir: string;
    work: string;
    signal: AbortSignal;
}
export interface Programs {
    ffmpeg: string;
    ffprobe: string;
    gifski?: string;
}
export interface GifPrograms extends Programs {
    gifski: string;
}
export interface MediaInfo extends ClipInfo {
    bytes: number;
    frame_count: number;
    has_audio: boolean;
    audio_codec?: string;
}
export interface AcquiredMedia {
    path: string;
    title: string;
    source: string;
}
export interface GifMedia {
    path: string;
    width: number;
    height: number;
    bytes: number;
    frame_count: number;
    duration_seconds: number;
    fps: number;
    quality: number;
    motion_quality: number;
    lossy_quality: number;
    start: number;
    end: number;
    loop: 0;
    mode: 'normal';
}
export interface JobWarnings {
    warnings?: string[];
}
export interface DownloadResult extends MediaInfo, AcquiredMedia, JobWarnings {
    status: 'downloaded';
}
export interface GifCompleted extends GifMedia, AcquiredMedia, JobWarnings {
    status: 'completed';
    attempts: BudgetAttempt[];
}
export interface GifAdjustment extends BudgetAdjustment, JobWarnings {
    source: string;
    width: number;
    height: number;
    fps: number;
    start: number;
    end: number;
}
export type GifResult = GifCompleted | GifAdjustment;
export type CompletedResult = GifCompleted;
export type NeedsAdjustmentResult = GifAdjustment;
export declare class AmberService {
    ctx: ServiceContext;
    config: Readonly<AmberConfig>;
    runtime: Runtime;
    queue: JobQueue;
    shutdown: AbortController;
    jobs: Set<Promise<unknown>>;
    constructor(ctx: ServiceContext, config?: unknown);
    close(): Promise<void>;
    cleanup(work: string, root: string): Promise<void>;
    failure(error: unknown, timeout: AbortSignal, signal: AbortSignal): AmberError;
    job<T extends object>(args: GifArguments, exec: ExecutionContext, operation: (context: JobContext) => Promise<T>): Promise<T & JobWarnings>;
    programs(work: string, signal: AbortSignal, gif: true): Promise<GifPrograms>;
    programs(work: string, signal: AbortSignal, gif: false): Promise<Programs>;
    programs(work: string, signal: AbortSignal, gif: boolean): Promise<Programs>;
    probe(path: string, programs: Programs, context: Pick<JobContext, 'work' | 'signal'>, gif?: boolean, checkHdr?: boolean): Promise<MediaInfo>;
    sourceFile(path: string): Promise<string>;
    acquire(url: string, programs: Programs, context: JobContext, videoOnly: boolean): Promise<AcquiredMedia>;
    publish(source: string, title: string, suffix: string, context: JobContext): Promise<string>;
    download(args: GifArguments, exec?: ExecutionContext): Promise<DownloadResult>;
    validateGif(path: string, params: ClipOptions, programs: Programs, context: JobContext): Promise<GifMedia>;
    makeGif(args: GifArguments, exec?: ExecutionContext): Promise<GifResult>;
}
