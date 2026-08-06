# 腾讯云 SCF 云函数 - HiFiNi 自动签到部署指南

## 优势

- ✅ **国内 IP**，100% 能访问 HiFiNi（已本地验证签到成功）
- ✅ **永久免费**（每月 100 万次调用免费，签到每天只需 1 次）
- ✅ **自带定时触发器**（替代 GitHub Actions cron）
- ✅ **不需要电脑开机**（云端全自动运行）
- ✅ **纯 Python 标准库**（无需安装任何依赖包）

## 部署步骤（约 5 分钟）

### 第 1 步：登录腾讯云

访问 [腾讯云云函数控制台](https://console.cloud.tencent.com/scf/list) ，使用微信扫码登录。

### 第 2 步：创建云函数

1. 点击 **「新建」**
2. 创建方式：选择 **「从头开始」**
3. 基础配置：
   - 函数名称：`hifini-checkin`
   - 地域：选择 **广州** 或 **上海**（国内地域均可）
   - 运行环境：**Python 3.9**
   - 函数代码：选择 **「在线编辑」**
4. 将 `scf/index.py` 的全部代码粘贴到在线编辑器中
5. 执行方法设为：`index.main_handler`

### 第 3 步：配置环境变量

在「高级配置」→「环境变量」中添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `HIFIHI_COOKIE` | `bbs_sid=xxx; bbs_token=xxx` | HiFiNi Cookie（最重要） |
| `HIFINI_USERNAME` | `yfming93` | 用户名（Cookie 失效时备用） |
| `HIFINI_PASSWORD` | `你的密码` | 密码（Cookie 失效时备用） |
| `WXPUSHER_APP_TOKEN` | `AT_qRDXs7tySLf9gIV6dTEawsDVqkAJUJa4` | WxPusher AppToken |
| `WXPUSHER_UID` | `UID_dC7k857XvOhGTdetiAHJdGUvDQKV` | WxPusher UID |

### 第 4 步：配置执行超时

在「高级配置」中：
- 执行超时时间：**60 秒**（默认 3 秒太短，需改大）
- 内存：**64 MB**（够用）

### 第 5 步：创建定时触发器

1. 点击 **「触发器配置」** → **「创建触发器」**
2. 触发方式：**定时触发**
3. 触发周期：**自定义触发周期**
4. Cron 表达式：`0 0 2 * * * *`（每天凌晨 02:00 执行）
5. 点击 **「提交」**

### 第 6 步：手动测试

1. 回到函数代码页面
2. 点击 **「测试」** 按钮
3. 查看执行日志，确认输出 `✅ 签到成功`

## 完成！

部署完成后，腾讯云 SCF 会每天凌晨 2 点自动执行签到，并通过 WxPusher 推送结果到你的微信。

## 注意事项

- Cookie 有效期有限，失效后会自动尝试用账号密码登录
- 如果账号密码也无法登录，需要手动更新 Cookie 环境变量
- 可以在 [云函数控制台](https://console.cloud.tencent.com/scf/list) 查看每次执行的日志
