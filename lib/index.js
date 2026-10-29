import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AmberService } from './service.js';
import { CONFIG_FIELDS, DEFAULTS } from './options.js';
export const name = 'cyber-amber';
export const inject = ['tools', 'subprocess', 'workingDirectory'];
const configShape = Object.fromEntries(Object.entries(DEFAULTS).map(([key, value]) => {
    const field = CONFIG_FIELDS[key];
    let schema = typeof value === 'number'
        ? z.number().min(field.min).max(field.max).default(value)
        : z.string().default(value);
    if (field.integer)
        schema = schema.step(1);
    if (['cookiesFile', 'proxy'].includes(key))
        schema = schema.role('secret');
    return [key, schema.description(field.description)];
}));
export const Config = z.object(configShape);
const attempt = { type: 'object', additionalProperties: false, properties: {
        quality: { type: 'number', required: true }, lossy_quality: { type: 'number', required: true },
        motion_quality: { type: 'number', required: true }, bytes: { type: 'number', required: true },
    } };
const suggestion = { type: 'object', additionalProperties: false, properties: {
        change: { type: 'string', required: true }, value: { type: 'number', required: true },
        verified: { type: 'boolean', required: true }, explanation: { type: 'string', required: true },
    } };
export const resultSchema = { type: 'object', additionalProperties: false, properties: {
        status: { type: 'string', enum: ['downloaded', 'completed', 'needs_adjustment'], required: true },
        path: { type: 'string' }, title: { type: 'string' }, source: { type: 'string', required: true },
        width: { type: 'number', required: true }, height: { type: 'number', required: true },
        fps: { type: 'number', required: true }, bytes: { type: 'number' }, duration_seconds: { type: 'number' },
        frame_count: { type: 'number' }, start: { type: 'number' }, end: { type: 'number' },
        has_audio: { type: 'boolean' }, audio_codec: { type: 'string' },
        warnings: { type: 'array', items: { type: 'string' } },
        quality: { type: 'number' }, motion_quality: { type: 'number' }, lossy_quality: { type: 'number' },
        loop: { type: 'number' }, mode: { type: 'string' }, limit_bytes: { type: 'number' }, smallest_bytes: { type: 'number' },
        attempts: { type: 'array', items: attempt }, suggestions: { type: 'array', items: suggestion },
    } };
// Keep the existing wire schema for saved tool records. AmberService supplies
// the status-specific required fields; the schema predates that typed union.
export function render(_args, value) {
    const warnings = (value.warnings || []).map(text => `注意：${text}`).join('\n');
    if (value.status === 'needs_adjustment')
        return [{ type: 'text', text: `GIF尚未满足体积上限：目标≤${value.limit_bytes}字节，已尝试的最小结果为${value.smallest_bytes}字节。未交付超限文件。\n`
                    + `尺寸${value.width}×${value.height}，${value.fps}fps，范围${value.start}–${value.end}秒。\n`
                    + `实测尝试：${JSON.stringify(value.attempts)}\n`
                    + value.suggestions.map(item => item.explanation).join('\n')
                    + '\n选取舍时：文字/UI优先保留尺寸，动作优先保留帧率；基本静态画面降帧不保证更小。若未看过原片，不应猜测画面类型。'
                    + '\n以上建议尚未编码验证，不保证达标。请让用户选择尺寸、帧率或质量的取舍后再调用；不要自行重试或声称已完成。'
                    + (warnings ? `\n${warnings}` : '') }];
    return [{ type: 'text', text: `${value.status === 'downloaded' ? '视频已下载' : 'GIF已制作'}：${value.path}\n`
                + `${value.width}×${value.height} · ${value.duration_seconds.toFixed(2)}秒 · ${value.bytes}字节`
                + (value.status === 'completed' ? ` · ${value.fps}fps · Q${value.quality}/M${value.motion_quality}/L${value.lossy_quality}` : '')
                + (value.status === 'downloaded' ? ` · ${value.has_audio ? `音轨${value.audio_codec || '存在'}` : '无音轨'}` : '')
                + `\n来源：${value.source}\n文件仅保存在本地，未上传或发布。` + (warnings ? `\n${warnings}` : '') }];
}
export function apply(ctx, config) {
    const service = new AmberService(ctx, config);
    ctx.effect(() => () => service.close());
    const output = { schema: resultSchema, render };
    const outputDir = { type: 'string', description: '可选输出目录；默认会话工作目录下cyber-amber。没有会话时须提供绝对目录。' };
    ctx.tools.register(defineTool({
        name: 'amber_download_video',
        description: '下载单个视频并保留原片，返回本地绝对路径、来源、时长及尺寸，供用户或其他工具使用。支持yt-dlp可解析的视频页面链接和BV号；默认取1080p以内最佳格式和可用音轨，未知分辨率下载后报告实际尺寸。使用插件内置的yt-dlp、FFmpeg、ffprobe，无需外部安装；登录与平台限制仍适用，不下载播放列表，不发布内容。只要GIF时直接调用amber_make_gif，无需先调用本工具。',
        parameters: {
            url: { type: 'string', required: true, description: '单个视频页面HTTP(S)链接或BV号。' },
            output_dir: outputDir,
        }, output,
        async execute(args, exec) { return service.download(args, exec); },
    }));
    const time = (label) => ({ oneOf: [{ type: 'number' }, { type: 'string' }],
        description: `${label}；接受秒、小数秒、分:秒、时:分:秒，中英文冒号均可。越界自动贴合原片。` });
    const quality = (label) => ({ type: 'integer', description: `${label}，1至100。` });
    ctx.tools.register(defineTool({
        name: 'amber_make_gif',
        description: '将视频链接、BV号或本地视频的一段制作成高质量GIF并返回本地路径；链接输入时内部下载，临时原片随后清理，本地输入不改动。默认长边640、20fps、Q75/M75/L75、normal、无限循环，不放大或补帧；未给范围取整片，默认最多30秒，超长需询问片段。未指定大小时直接制作一次，不先要求确认。指定max_size_mb时工具自动实测、只降低联动Q/L，默认最低50，最多10次；保留尺寸、帧率、M和时间范围。独立指定不同Q/L时不自动调整。needs_adjustment表示尚未满足上限，须请用户选择建议后再试，不能自行降低尺寸/帧率或声称成功。不上传、不发布、不分析视频。',
        parameters: {
            source: { type: 'string', required: true, description: '视频页面链接、BV号，或实际存在的本地视频绝对/会话相对路径。' },
            start: time('起点，默认0秒'), end: time('终点，不填取片尾'),
            long_edge: { type: 'integer', description: '等比缩放后的最长边，128至1920，默认640，不放大原片。' },
            fps: { type: 'integer', description: '采样帧率1至30，默认20，且不超过原片平均帧率。' },
            quality: quality('Q，默认75；未给lossy_quality时L跟随Q'),
            motion_quality: quality('M，默认75，独立于Q/L'),
            lossy_quality: quality('L，默认跟随Q；明确指定不同Q/L时保留其组合，不自动改写'),
            min_quality: quality('体积搜索最低Q/L，默认50；用户主动选择低于50时尊重初始值。只有用户同意时才调低此下限'),
            max_size_mb: { type: 'number', description: '可选成品上限，1MB=1000000字节，必须大于0；不填不设目标、不自动降质。' },
            output_dir: outputDir,
        }, output,
        async execute(args, exec) { return service.makeGif(args, exec); },
    }));
}
//# sourceMappingURL=index.js.map