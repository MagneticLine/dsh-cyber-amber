export interface AmberConfig {
    outputDir: string;
    ffmpegPath: string;
    ffprobePath: string;
    gifskiPath: string;
    ytdlpPath: string;
    cookiesFile: string;
    proxy: string;
    sourceHeight: number;
    longEdge: number;
    fps: number;
    quality: number;
    motionQuality: number;
    maxClipSeconds: number;
    timeoutMs: number;
    maxPending: number;
    maxSourceMB: number;
    maxOutputMB: number;
}
export interface ConfigField {
    description: string;
    min?: number;
    max?: number;
    integer?: boolean;
}
export interface GifArguments {
    source?: unknown;
    url?: unknown;
    output_dir?: unknown;
    quality?: unknown;
    lossy_quality?: unknown;
    motion_quality?: unknown;
    min_quality?: unknown;
    start?: unknown;
    end?: unknown;
    max_size_mb?: unknown;
    long_edge?: unknown;
    fps?: unknown;
}
export interface GifOptions {
    start: number;
    end: number | null;
    quality: number;
    lossy_quality: number;
    motion_quality: number;
    long_edge: number;
    fps: number;
    min_quality: number;
    max_bytes: number;
    guard_bytes: number;
}
export interface ClipInfo {
    duration_seconds: number;
    width: number;
    height: number;
    fps: number;
}
export interface ClipOptions extends GifOptions {
    end: number;
    width: number;
    height: number;
    duration_seconds: number;
}
export interface CleanupError extends Error {
    code?: unknown;
    cleanupNotes?: string[];
    processesUnconfirmed?: boolean;
}
/** Read only known properties after narrowing an untrusted error/object. */
export declare function record(value: unknown): Record<string, unknown>;
export declare function errorCode(error: unknown): unknown;
export declare function cleanupNotes(error: unknown): string[];
export declare class AmberError extends Error {
    code: string;
    cleanupNotes?: string[];
    processesUnconfirmed?: boolean;
    constructor(code: string, message: string);
}
export declare const DEFAULTS: Readonly<AmberConfig>;
export declare const CONFIG_FIELDS: Readonly<Record<keyof AmberConfig, ConfigField>>;
export declare function number(value: unknown, name: string, min: number, max: number, integer?: boolean): number;
export declare function readConfig(raw?: unknown): Readonly<AmberConfig>;
/** Display provenance only. Never use this lossy value to request the media. */
export declare function displaySource(value: string): string;
export declare function addCleanup(error: unknown, message: string, unconfirmed?: boolean): CleanupError;
export declare function timecode(value: unknown, name?: string): number;
export declare function sourceInput(value: unknown, cwd: string | null | undefined, localAllowed?: boolean): {
    kind: 'url' | 'local';
    value: string;
};
export declare function gifOptions(args: GifArguments, cfg: Readonly<AmberConfig>): GifOptions;
export declare function fitClip(options: GifOptions, info: ClipInfo, maxSeconds: number): ClipOptions;
export declare function downloadArgs(url: string, folder: string, cfg: Readonly<AmberConfig> & {
    resolvedFfmpeg?: string;
}, videoOnly: boolean): string[];
