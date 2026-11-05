# 服务器实际验证记录：通过

验证区间：2026-11-04—2026-11-05（Asia/Shanghai）。联合验收时间：2026-11-05T00:09:02.644785+08:00。

目标：在用户授权的Ubuntu服务器上验证第一阶段镜像构建和六服务实际启动。本次未修改应用业务代码、Dockerfile或依赖版本。

## 环境与隔离项目

- 服务器：`ubuntu@SERVER_HOST:22`；Ubuntu 26.04 LTS，x86_64，2核，约3.6GiB内存。
- Docker Engine：29.1.3；Docker Compose：2.40.3；Buildx：0.30.1。
- 项目目录：`/path/to/multiAgentVillage`。
- Compose项目名：`campus-verify-bcb02f6b`。
- 后端镜像：`campus-sandbox-backend:verify-bcb02f6b`；frontend、api、runtime、cognition、postgres、redis共6个服务。
- 独立命名卷；应用和数据端口仅绑定`127.0.0.1`。数据库密码在服务器生成，`.env`权限为600，不写入报告。

## 构建与环境调整

初次构建因Docker Hub连接超时失败。用户随后明确批准在`/etc/docker/daemon.json`配置腾讯云官方镜像源并重启Docker，配置已生效：`https://mirror.ccs.tencentyun.com/`。[腾讯云官方说明](https://intl.cloud.tencent.com/zh/document/product/213/8623)

前端通过原Compose配置完成`npm ci`、TypeScript检查、Vite构建及Nginx镜像导出；`nginx -t`通过。后端直连官方PyPI下载缓慢，因此在项目目录增加仅用于构建的`docker-compose.build-proxy.yml`，通过SSH临时代理访问同一官方PyPI，使用host构建网络，最终构建退出码为0。该覆盖文件不参与运行阶段。

后端构建命令：

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.build-proxy.yml --progress plain build api
```

本次未改Dockerfile或依赖版本，也未切换Python包索引。临时SSH代理通道已关闭，服务器127.0.0.1:18080端口已拒绝连接，后端镜像配置未保留HTTP_PROXY/HTTPS_PROXY/ALL_PROXY。腾讯云Docker镜像源按用户授权持续保留。

构建相关的7个文件SHA256与本地一致，具体哈希见[机器可读证据](server-verification-2026-11-05.json)。原始源码包SHA256为`b256b478a5e586a1c61f9cab66ef55a7e3732f663749b409e26d4f4c6ee2e975`。

## 六服务启动与稳定性

实际执行：

```bash
sudo docker compose --progress plain up --no-build --pull never -d --wait --wait-timeout 120
```

| 服务 | 容器状态 | 探针状态 | 自动重启次数 |
| --- | --- | --- | --- |
| frontend | running | healthy | 0 |
| api | running | healthy | 0 |
| runtime | running | not_configured | 0 |
| cognition | running | not_configured | 0 |
| postgres | running | healthy | 0 |
| redis | running | healthy | 0 |

Runtime和Cognition本阶段没有健康探针，分别验证其持续running、启动日志及重启计数；未将Compose的等待提示当作Worker业务健康证明。

30秒稳定观察前后，6个容器ID保持一致，自动重启次数均为0。API、Runtime、Cognition的镜像ID完全一致：

`sha256:32ec45ab7993160376392ed5db0534643728b83cc427691e904c08c3532dfcfa`

随后主动重启Runtime与Cognition，约3.8秒完成检查。两个Worker都记录正常stopped和重新started，容器ID不变，重启后running、自动重启次数仍为0。当前仍保留六个容器运行。

## 联合验收结果

| 检查项 | 实际结果 |
| --- | --- |
| Compose配置 | `docker compose config --quiet`通过 |
| API存活 | HTTP 200，`{"status":"ok","service":"api"}` |
| API真实依赖就绪 | HTTP 200，PostgreSQL和Redis均为ok |
| Nginx代理 | `/api/health/ready`与API直接请求结果一致 |
| 前端静态服务 | `/healthz`返回ok；HTML与构建JS/CSS返回200，MIME类型正确，未被SPA回退误判 |
| Alembic实际迁移 | PostgreSQL中`alembic_version`为`0001_baseline` |
| Redis | PING返回PONG |
| 非root后端 | API进程UID为999 |
| 容器内pytest | 5 passed，耗时0.61秒 |
| 共享后端镜像 | 三个入口的镜像ID完全一致 |
| Worker退出/重启 | 两个Worker均正常退出并重新运行 |
| 临时代理清理 | 通道已关闭，镜像不含代理环境变量 |

pytest输出包含3条非阻断警告（Starlette/AnyIO弃用提示与非root环境pytest缓存不可写）；未改变容器权限，详细输出保存在JSON。上述检查覆盖基础框架和短时稳定性，仿真业务、事件消费和模型调用仍是后续阶段接口占位。

## 查看已运行的页面

在本机打开SSH隧道并保持该终端运行：

```bash
ssh -p 22 -L 15173:127.0.0.1:33931 -L 18000:127.0.0.1:49631 ubuntu@SERVER_HOST
```

随后访问[基础页面](http://localhost:15173)、[API文档](http://localhost:18000/docs)。服务器本机端口为frontend=33931、api=49631、postgres=37727、redis=40959；没有开放应用公网监听。

## 保留当前镜像与数据的维护命令

```bash
cd /path/to/multiAgentVillage
sudo docker compose ps
sudo docker compose up -d --no-build --pull never --wait
sudo docker compose logs --tail=100 api runtime cognition
```

日常暂停使用`sudo docker compose stop`；`sudo docker compose down`也保留命名卷。继续使用现有`.env`和Compose项目名，以连接同一组数据卷。

代码更新后再构建镜像，并一起更新API、Runtime和Cognition。普通`up`可能因API的`pull_policy: build`触发重建；使用现有镜像时采用上面的`--no-build --pull never`命令。临时构建代理配置需要重新建立相应通道才能复用，常规运行不依赖该通道。
