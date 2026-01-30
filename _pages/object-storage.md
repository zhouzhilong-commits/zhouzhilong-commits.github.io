---
layout: single
title: "对象存储"
permalink: /object-storage/
author_profile: false
series: object_storage
---


{% assign posts = site.posts | where: "series", "object_storage" %}
{% if posts and posts.size > 0 %}
## 文章列表
{% for post in posts %}
- [{{ post.title }}]({{ post.url }})
{% endfor %}
{% else %}
暂无文章（先在 `_posts/` 里新增并设置 `series: object_storage` 即可）。
{% endif %}

