import { registerHooks } from 'node:module'
// Only substitute the two host imports; the real registry is verified separately in DSH.
registerHooks({ resolve(specifier, context, next) {
  if (specifier === '@deepseek-ai/dsh-tools') return {
    url: 'data:text/javascript,export const defineTool = value => value', shortCircuit: true,
  }
  if (specifier === '@deepseek-ai/schemastery') return {
    url: 'data:text/javascript,' + encodeURIComponent('const type=()=>({default:value=>({default:value})}); export default {number:type,string:type,object:shape=>({shape})}'),
    shortCircuit: true,
  }
  return next(specifier, context)
} })
