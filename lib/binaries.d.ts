export declare const VENDOR_ROOT: string;
export interface BundleOptions {
    root?: string;
    platform?: string;
    arch?: string;
}
export interface BundleFile {
    component: string;
    bytes: number;
    sha256: string;
}
export declare function hashFile(path: string): Promise<string>;
export declare function contained(root: string, name: string): string;
export declare function verifyFile(root: string, name: string, entry: BundleFile): Promise<string>;
/** No downloads, extraction, installer hooks or automatic updates occur at runtime. */
export declare function bundledExecutable(name: string, options?: BundleOptions): Promise<string | null>;
