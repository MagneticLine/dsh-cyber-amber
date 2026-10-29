import type { BundleOptions } from './binaries.js';
import type { CollectedReader, EncodeParams, ProcessHandle, ProcessStdio, RuntimeContext, SubprocessAdapter } from './runtime-types.js';
export type { CollectedReader, EncodeParams, ProcessHandle, RuntimeContext, SubprocessAdapter } from './runtime-types.js';
export declare function collectedText(reader?: CollectedReader): string;
export declare class Runtime {
    readonly subprocess: SubprocessAdapter;
    readonly bundleOptions: BundleOptions;
    constructor(subprocess: SubprocessAdapter, bundleOptions?: BundleOptions);
    executable(configured: string | undefined, name: string, signal: AbortSignal): Promise<string>;
    spawn(argv: readonly (string | number)[], cwd: string, signal: AbortSignal, stdio?: ProcessStdio): ProcessHandle;
    stop(handle?: ProcessHandle): Promise<void>;
    run(argv: string[], { cwd, signal, stage }: RuntimeContext & {
        stage: string;
    }): Promise<string>;
    encode(ffmpeg: string, gifski: string, source: string, output: string, params: EncodeParams, { cwd, signal }: RuntimeContext): Promise<void>;
}
interface QueueItem {
    resolve(): void;
    signal: AbortSignal;
    abort(): void;
}
export declare class JobQueue {
    readonly limit: number;
    count: number;
    active: boolean;
    waiting: QueueItem[];
    constructor(limit?: number);
    release(): void;
    run<T>(signal: AbortSignal, body: () => T | Promise<T>): Promise<T>;
}
