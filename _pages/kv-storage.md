---
layout: single
title: "KV存储"
permalink: /kv-storage/
author_profile: false
series: kv_storage
---


{% assign posts = site.posts | where: "series", "kv_storage" %}
{% if posts and posts.size > 0 %}
## 文章列表
{% for post in posts %}
- [{{ post.title }}]({{ post.url }})
{% endfor %}
{% else %}
暂无文章（先在 `_posts/` 里新增并设置 `series: kv_storage` 即可）。
{% endif %}

