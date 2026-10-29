import type { Context } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { type InferValue } from '@deepseek-ai/dsh-tools';
import { type AmberConfig } from './options.js';
export declare const name = "cyber-amber";
export declare const inject: string[];
type ConfigShape = {
    [K in keyof AmberConfig]: z<AmberConfig[K], AmberConfig[K], 'defined'>;
};
export declare const Config: z<Schemastery.ObjectS<NoInfer<ConfigShape>>, Schemastery.ObjectT<NoInfer<ConfigShape>>, "plain">;
export declare const resultSchema: {
    readonly type: "object";
    readonly additionalProperties: false;
    readonly properties: {
        readonly status: {
            readonly type: "string";
            readonly enum: readonly ["downloaded", "completed", "needs_adjustment"];
            readonly required: true;
        };
        readonly path: {
            readonly type: "string";
        };
        readonly title: {
            readonly type: "string";
        };
        readonly source: {
            readonly type: "string";
            readonly required: true;
        };
        readonly width: {
            readonly type: "number";
            readonly required: true;
        };
        readonly height: {
            readonly type: "number";
            readonly required: true;
        };
        readonly fps: {
            readonly type: "number";
            readonly required: true;
        };
        readonly bytes: {
            readonly type: "number";
        };
        readonly duration_seconds: {
            readonly type: "number";
        };
        readonly frame_count: {
            readonly type: "number";
        };
        readonly start: {
            readonly type: "number";
        };
        readonly end: {
            readonly type: "number";
        };
        readonly has_audio: {
            readonly type: "boolean";
        };
        readonly audio_codec: {
            readonly type: "string";
        };
        readonly warnings: {
            readonly type: "array";
            readonly items: {
                readonly type: "string";
            };
        };
        readonly quality: {
            readonly type: "number";
        };
        readonly motion_quality: {
            readonly type: "number";
        };
        readonly lossy_quality: {
            readonly type: "number";
        };
        readonly loop: {
            readonly type: "number";
        };
        readonly mode: {
            readonly type: "string";
        };
        readonly limit_bytes: {
            readonly type: "number";
        };
        readonly smallest_bytes: {
            readonly type: "number";
        };
        readonly attempts: {
            readonly type: "array";
            readonly items: {
                readonly type: "object";
                readonly additionalProperties: false;
                readonly properties: {
                    readonly quality: {
                        readonly type: "number";
                        readonly required: true;
                    };
                    readonly lossy_quality: {
                        readonly type: "number";
                        readonly required: true;
                    };
                    readonly motion_quality: {
                        readonly type: "number";
                        readonly required: true;
                    };
                    readonly bytes: {
                        readonly type: "number";
                        readonly required: true;
                    };
                };
            };
        };
        readonly suggestions: {
            readonly type: "array";
            readonly items: {
                readonly type: "object";
                readonly additionalProperties: false;
                readonly properties: {
                    readonly change: {
                        readonly type: "string";
                        readonly required: true;
                    };
                    readonly value: {
                        readonly type: "number";
                        readonly required: true;
                    };
                    readonly verified: {
                        readonly type: "boolean";
                        readonly required: true;
                    };
                    readonly explanation: {
                        readonly type: "string";
                        readonly required: true;
                    };
                };
            };
        };
    };
};
export declare function render(_args: unknown, value: InferValue<typeof resultSchema>): {
    type: "text";
    text: string;
}[];
export declare function apply(ctx: Context, config: Partial<AmberConfig>): void;
export {};
