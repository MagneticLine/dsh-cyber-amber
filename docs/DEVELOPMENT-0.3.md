# 0.3 开发说明

源码位于 `src/`，使用 TypeScript 严格模式。`lib/` 是随仓库和安装包保留的编译产物；修改源码后重新编译，不直接编辑生成文件。

## 环境与检查

使用 `package.json` 声明的 Node 版本和 npm，构建依赖由 `package-lock.json` 固定。
DSH SDK 仅作为开发依赖提供类型；安装包运行时仍使用宿主服务。

```powershell
npm ci --legacy-peer-deps --ignore-scripts --no-audit --no-fund
npm run typecheck
npm test
python -m unittest discover -s test -p 'test_*.py' -v
```

`--legacy-peer-deps` 与生成锁文件时一致，避免在开发环境自动安装整套宿主服务。
TypeScript 5.9.3 编译为 ES2022 ESM；输出 JS、类型声明和 source map。
安装包包含对应 TS 源码，使用者无需安装 TypeScript 或在安装时编译。

从新检出的仓库运行实际编码测试前，先执行 `python scripts/vendor.py` 恢复固定版本的内置程序。
已具备内置程序时可直接使用，不重复下载。

## 制作候选包

```powershell
npm run build
npm pack --pack-destination dist
python scripts/verify-package.py dist/dsh-cyber-amber-0.3.0.tgz .
```

完整的源码附件与隔离宿主验证沿用现有 `prepare-candidate.py`、`verify-host.py`；前者现在会先编译源码。
已有 0.2.1 文档和安装包保留为历史资料；0.3.0 的本地安装与验证结果见 `releases/0.3.0-review.md`。
公开发布、推送和市场提交仍须用户审核。
