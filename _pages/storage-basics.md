---
layout: single
title: "存储基础"
permalink: /storage-basics/
author_profile: false
series: storage_basics
---


{% assign posts = site.posts | where: "series", "storage_basics" %}
{% if posts and posts.size > 0 %}
## 文章列表
{% for post in posts %}
- [{{ post.title }}]({{ post.url }})
{% endfor %}
{% else %}
暂无文章（先在 `_posts/` 里新增并设置 `series: storage_basics` 即可）。
{% endif %}

