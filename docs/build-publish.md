# Fork 镜像构建与 GHCR 发布

本 Fork 的 `.github/workflows/build_ci.yml` 只构建 **Debian / linux/amd64**，
只向 GHCR 发布，不登录 Docker Hub，也不发布上游命名空间。
镜像名为 `ghcr.io/<小写 repository_owner>/steam-headless`；在 lxfee 的 Fork 中是
`ghcr.io/lxfee/steam-headless`。不需要配置 Docker Hub 或个人访问令牌。

## 触发与标签

| 事件 | 行为 | 发布标签 |
| --- | --- | --- |
| push 到 `master` | 测试、构建、发布 | `latest`、`debian`、`sha-<完整 commit SHA>` |
| push Git tag（任意 tag） | 测试、构建、发布 | `debian-<Git tag>`、`sha-<完整 commit SHA>` |
| Actions → Build and publish to GHCR → Run workflow | 测试、构建、发布所选 ref | SHA 标签；master 另有 `latest` / `debian`，tag ref 另有版本标签 |
| PR 到 `master`（含外部 Fork） | 测试及完整构建 | **不登录、不发布** |

Git tag 经 docker/metadata-action 规范化为合法的 Docker 标签。
版本发布不更新 `latest` / `debian`，这两个滚动标签仅跟随 master。
SHA 标签使用完整 commit SHA，不使用容易冲突的短 SHA，也不随后续提交移动。
但 GHCR 本身不强制标签不可覆盖：同一提交重新构建可能因基础镜像或下载依赖变化而产生不同镜像。
需要严格不可变部署时，请使用发布日志中的 `@sha256:<digest>` 固定镜像。
手动在非 master 分支运行会发布 SHA 标签，但不会更新滚动标签。

## 启用发布与使用

1. 在 Fork 的 Actions 页面启用工作流，并允许工作流使用 `GITHUB_TOKEN` 写入 Packages。
   CI 使用 `contents: read` 和 `packages: write`；PR 不执行 registry login 或 push。
2. push master、push tag，或手动运行工作流。
3. 在仓库/用户的 **Packages → steam-headless → Package settings** 检查可见性。
   GHCR 首次发布可能为私有；如需匿名拉取，手动设为 public。
   如果包已存在，确认它关联当前 Fork，并在 Manage Actions access 中授权当前仓库写入。
   OCI `org.opencontainers.image.source` 始终指向当前仓库，而不是上游。
4. 将部署配置中的 image 替换为本 Fork 的镜像，例如：
   ```sh
   docker pull ghcr.io/lxfee/steam-headless:debian
   # 固定到某次提交时使用 sha-<40 位完整 SHA>，严格固定则使用 digest。
   ```
   保留现有设备、环境变量及 home 挂载，重新创建容器。
   私有包拉取需要登录 GHCR，并使用有 `read:packages` 权限的凭据。

## 本地构建与验证

```sh
bash -n overlay/usr/bin/configure-input-method.sh overlay/usr/bin/start-desktop.sh overlay/usr/bin/start-dumb-udev.sh tests/input-method.sh
bash tests/input-method.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_uinput.py' -v
docker build -f Dockerfile.debian -t steam-headless:local .
git diff --check
```

CI 在构建前执行同样的 Bash 语法检查、无显示服务器的输入法测试和 uinput 回归测试。
PR 也完整构建 Dockerfile，但不进行桌面、GPU 或远程串流实测。

## dumb-udev 输入热插拔的职责

镜像负责输入热插拔兼容，不由部署启动钩子修改镜像内部源码：

- `overlay/usr/bin/start-dumb-udev.sh` 直接保留 legacy `xorg-restarted` marker，
  在输入设备断连、长时间消失和 watcher 重启后均不清除；不重启 Xorg，避免连带停止 Sunshine。
  marker 位于容器临时 `/run`，重建容器会重新初始化。旧 debounce 环境变量不再使用。
- Debian 和 Arch Dockerfile 固定 `DUMB_UDEV_VERSION=64d1427`，构建时通过 Python
  模块发现安装路径，再运行独立 `scripts/patch-dumb-udev.py`。
  补丁将键盘、鼠标、触屏、笔及回退手柄分类写入 udev data，修正 subsystem/device-type
  hash 的网络字节序。完整上游源码 SHA-256 和替换块均检查，输出先编译验证；
  未知版本、漂移或部分补丁必须导致构建失败，不能静默跳过。
- `tests/test_uinput.py` 属于镜像仓库：离线 fixture 验证分类、header hash 字节序、
  失败闭合及 helper marker 行为；Docker 构建还验证实际安装的 service 等于测试输出。
  构建脚本与测试临时目录在成功后删除，不安装运行时补丁 hook。
- 升级 dumb-udev 时同步评审补丁、源码校验值、fixture 和测试，不仅修改版本参数。
  Arch 同步接入补丁是因为共享 overlay；发布 CI 仍只构建 Debian/amd64。

GitOps 只负责部署镜像、设备权限、71 虚拟显示器及 Sunshine 配置。
先完成新镜像构建并成功发布 `latest`，再推送删除旧 72 hook 的 GitOps 变更；
GitOps 的 Pod template `image-revision` annotation 用于触发拉取 `latest` 的 rollout，
不是不可变镜像版本或发布凭证。

## Hosted runner 磁盘与缓存

镜像较大，CI 在 Buildx 启动前清理不用的 .NET、Android、GHC、hosted tool cache、
Boost 和 PowerShell 预装目录，输出清理前后的磁盘用量；不删除 Docker 或 `/var/lib/docker`。
构建不 `load` 到本地 Docker，发布直接由 BuildKit 推送，避免额外加载一份大镜像。
使用 GitHub Actions cache（`type=gha`，固定 Debian scope，`mode=min`）复用最终镜像层，
降低缓存体积；缓存导出失败不阻断发布。PR 缓存受 GitHub 的分支访问隔离限制。
缓存配额、上游下载及 runner 剩余空间仍可能影响构建；清理并不保证所有构建都能容纳，
若仍遇到空间不足，应使用更大磁盘的 runner，而不是删除正在使用的 Docker 数据。
