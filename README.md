# 周智龙的个人博客（Jekyll）

这个仓库是一个基于 Jekyll（GitHub Pages 兼容）的个人博客站点。

## 如何新增一篇博客文章（放在 `_posts/`）

- **1）创建文件**：在 `_posts/` 下新建 Markdown 文件，命名格式：
  - `YYYY-MM-DD-英文-slug.md`
  - 例如：`2026-01-29-storage-basics-6-something.md`

- **2）写 Front Matter（必须）**：文件顶部写：

```yaml
---
title: "文章标题"
series: storage_basics
tags: [存储, LSM]
categories: [storage]
---
```

- **3）写正文**：Front Matter 下面开始正常写 Markdown 内容即可。

### 关于 `series`（决定侧边栏属于哪个系列）

本仓库用 `series` 把文章归到某个系列，并在侧边栏显示该系列导航树。

常用值（可按需扩展）在 `_data/navigation.yml` 里定义过：
- `storage_basics`（存储基础）
- `rocksdb`
- `object_storage`
- `consensus`
- `paper_storage` / `paper_databases` / `paper_distributed`
- `cs_os` / `cs_network` / `cs_arch`

> 经验法则：**新增文章时，`series` 要填对；想让侧边栏出现这篇文章，还需要把它加到 `_data/navigation.yml` 对应的 children 列表里。**

## 如何把文章加入侧边栏导航（推荐做法）

编辑 `_data/navigation.yml`：
- 找到对应系列（例如 `storage_basics:`）
- 在 `children:` 下新增一项：

```yaml
- title: "存储基础（6）：XXX"
  url: /storage-basics-6-xxx/
```

然后在文章里把 `permalink`（可选）对齐这个 url：

```yaml
permalink: /storage-basics-6-xxx/
```

> 不写 `permalink` 也可以，但为了 URL 稳定、和侧边栏一致，建议显式写。

## 本地预览（不跳转到线上域名）

本地预览建议用开发配置覆盖线上 `url`：

```bash
bundle exec jekyll serve --config _config.yml,_config.dev.yml
```

- 默认访问：`http://localhost:4000/`
- **首页分页**：`/page2/`、`/page3/` ...

> 注意：修改 `_config.yml` 后需要重启 `jekyll serve`（Jekyll 不会热加载 config）。

## 标签 / 分类页

标签页和分类页分别在：
- `_pages/tag-archive.html`（`/tags/`）
- `_pages/category-archive.html`（`/categories/`）

文章里设置了 `tags` / `categories` 后，对应入口会自动聚合展示。

