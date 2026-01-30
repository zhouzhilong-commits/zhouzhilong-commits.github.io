---
layout: single
title: "分布式一致性"
permalink: /consensus/
author_profile: false
series: consensus
---


{% assign posts = site.posts | where: "series", "consensus" %}
{% if posts and posts.size > 0 %}
## 文章列表
{% for post in posts %}
- [{{ post.title }}]({{ post.url }})
{% endfor %}
{% else %}
暂无文章（先在 `_posts/` 里新增并设置 `series: consensus` 即可）。
{% endif %}

