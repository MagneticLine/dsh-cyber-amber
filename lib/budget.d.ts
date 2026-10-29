export interface BudgetParams {
    quality: number;
    lossy_quality: number;
    motion_quality: number;
    min_quality: number;
    width: number;
    height: number;
    fps: number;
    max_bytes: number;
}
export interface BudgetAttempt {
    quality: number;
    lossy_quality: number;
    motion_quality: number;
    bytes: number;
}
export interface BudgetSuggestion {
    change: 'long_edge' | 'fps' | 'quality_and_lossy_quality';
    value: number;
    verified: false;
    explanation: string;
}
export interface BudgetAdjustment {
    status: 'needs_adjustment';
    limit_bytes: number;
    smallest_bytes: number;
    attempts: BudgetAttempt[];
    suggestions: BudgetSuggestion[];
}
export interface BudgetCompleted<T> {
    status: 'completed';
    result: T;
    attempts: BudgetAttempt[];
}
export type BudgetResult<T> = BudgetCompleted<T> | BudgetAdjustment;
export declare function suggestions(params: Pick<BudgetParams, 'width' | 'height' | 'fps' | 'quality' | 'lossy_quality'>, bytes: number, limit: number): BudgetSuggestion[];
/** Size is measured, never inferred from an MP4 bitrate. At most ten distinct encodes. */
export declare function fitBudget<P extends BudgetParams, T extends {
    bytes: number;
}>(params: P, encode: (settings: P) => Promise<T>, remove: (result: T) => Promise<unknown>): Promise<BudgetResult<T>>;
