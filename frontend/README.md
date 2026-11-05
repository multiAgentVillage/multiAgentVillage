# 前端工程骨架

使用固定版本的React、TypeScript、Vite、Ant Design、TanStack Query和Zustand。依赖锁定在`package-lock.json`，安装使用`npm ci`。

```powershell
npm ci
npm run dev
npm run typecheck
npm run build
```

开发地址为`http://localhost:5173`。Vite从仓库根目录读取`VITE_*`变量，`VITE_PROXY_TARGET`默认为`http://localhost:8000`；浏览器始终请求相对`/api`路径。后端密钥不能使用`VITE_`前缀。

`src/app`组合Provider；`src/api`定义API传输和健康契约；`src/features/system`显示实际API及依赖状态；`src/stores`保存界面选择；`src/styles`保存全局样式。业务状态由TanStack Query管理，不写入Zustand。

Docker使用多阶段构建，nginx在80端口提供静态文件，并代理`/api/*`到`api:8000/*`。`/ws/*`预留相同方式的WebSocket代理，尚无仿真接口。`/healthz`仅检查静态服务；首页调用`/api/health/ready`检查后端与数据库依赖，两者口径不同。

完整六服务启动方式见仓库根目录README。`npm run preview`用于查看构建产物；API联调使用Vite开发服务或Docker Compose。
