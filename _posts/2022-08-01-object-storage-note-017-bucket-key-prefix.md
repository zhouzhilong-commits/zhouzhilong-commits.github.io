---
layout: single
title: "对象存储笔记：对象存储的命名空间：bucket、key、prefix 的含义"
series: object_storage
categories: [storage]
tags: [存储, 对象存储]
permalink: /object-storage-note-017-bucket-key-prefix/
redirect_from:
  - /object-storage-note-066-bucket-key-prefix/
---

本文围绕「对象存储笔记：对象存储的命名空间：bucket、key、prefix 的含义」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![对象存储笔记：对象存储的命名空间：bucket、key、prefix 的含义](/images/diagrams/object-storage-bucket-prefix-partition.svg)
## 1. bucket/prefix 与分区

对象存储常按 bucket/prefix 做分区/路由；热点 prefix 会导致元数据或目录服务倾斜。

## 2. 工程建议

- 让 key 更均匀（hash 前缀/打散）
- 目录服务做分片与缓存

## 3. 排障顺序

先确认热点 prefix，再看元数据服务的 QPS/延迟与缓存命中，最后优化 key 设计或分区策略。
