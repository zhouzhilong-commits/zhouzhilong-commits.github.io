---
layout: single
title: "存储论文"
permalink: /paper-notes/storage/
author_profile: false
series: paper_storage
---


{% assign posts = site.posts | where: "series", "paper_storage" %}
{% if posts and posts.size > 0 %}
## 文章列表
{% for post in posts %}
- [{{ post.title }}]({{ post.url }})
{% endfor %}
{% else %}
暂无文章（后续新增文章时在 front matter 写 `series: paper_storage` 即可自动归类）。
{% endif %}

