---
layout: single
title: "计算机组成"
permalink: /cs/architecture/
author_profile: false
series: cs_arch
---

{% assign posts = site.posts | where: "series", "cs_arch" %}
{% if posts and posts.size > 0 %}
## 文章列表
{% for post in posts %}
- [{{ post.title }}]({{ post.url }})
{% endfor %}
{% else %}
暂无文章（新增文章时在 front matter 写 `series: cs_arch` 即可）。
{% endif %}

