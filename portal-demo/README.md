# 我的工具门户 - 设计文档

## 项目概述

统一的门户网站入口，用于展示和访问各个子系统。支持搜索和分类筛选，点击卡片在新标签页打开对应系统。

---

## 技术方案

### 技术栈
- **前端**：纯 HTML + CSS + JavaScript（无框架依赖）
- **部署**：Linux + Nginx 静态文件服务

### 文件结构

```
portal/
├── index.html      # 主页面（包含所有代码）
├── config.json     # 配置文件（备份，实际配置在HTML内）
└── README.md       # 说明文档
```

---

## 功能特性

### 1. 搜索功能
- 支持搜索系统名称、描述、分类
- 实时搜索，无需按回车
- 无结果时显示提示

### 2. 分类筛选
- 全部 / AI工具 / 效率工具 / 技术资讯
- 点击快速切换

### 3. 卡片展示
- 系统图标 + 名称 + 描述
- 分类标签
- 热门标记（HOT）
- 悬停动画效果
- 点击新标签页打开

---

## 如何添加新系统

### 方法一：修改 index.html 中的 CONFIG 对象（推荐）

打开 `index.html`，找到 `CONFIG` 对象，在 `systems` 数组中添加：

```javascript
{
    id: "new-system",           // 唯一标识
    name: "新系统名称",          // 显示名称
    icon: "🔧",                 // Emoji图标
    description: "系统功能描述", // 简要描述
    category: "tools",          // 分类：ai / tools / news
    url: "https://example.com", // 跳转URL
    hot: false                  // 是否热门
}
```

### 方法二：添加新分类

在 `categories` 数组中添加：

```javascript
{ id: "other", name: "其他", icon: "📌" }
```

然后在卡片样式中添加对应渐变色：

```css
.card.other .card-gradient {
    background: linear-gradient(135deg, #颜色1 0%, #颜色2 100%);
}
```

---

## 部署指南

### 1. 上传文件

将 `index.html` 上传到服务器：

```bash
# 创建目录
sudo mkdir -p /var/www/portal

# 上传文件（本地执行）
scp index.html user@server:/var/www/portal/
```

### 2. Nginx 配置

创建配置文件 `/etc/nginx/sites-available/portal`：

```nginx
server {
    listen 80;
    server_name portal.example.com;  # 修改为你的域名

    root /var/www/portal;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # 开启gzip压缩
    gzip on;
    gzip_types text/html text/css application/javascript;
}
```

### 3. 启用站点

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/portal /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载Nginx
sudo nginx -s reload
```

### 4. 配置HTTPS（推荐）

```bash
# 安装certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d portal.example.com
```

---

## 自定义配置

### 修改Logo和标语

在 `CONFIG.portal` 中修改：

```javascript
portal: {
    title: "你的门户名称",
    tagline: "你的标语",
    version: "1.0.0"
}
```

同时修改HTML中的对应内容：

```html
<div class="logo">🚀 你的门户名称</div>
<div class="tagline">你的标语</div>
```

### 修改配色

在 `<style>` 中修改：

```css
/* 背景渐变 */
body {
    background: linear-gradient(135deg, #新颜色1 0%, #新颜色2 100%);
}

/* AI分类卡片渐变 */
.card.ai .card-gradient {
    background: linear-gradient(135deg, #新颜色1 0%, #新颜色2 100%);
}
```

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2024-04-30 | 初始版本 |

---

## 联系方式

如有问题，请联系管理员。