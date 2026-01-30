---
layout: single
title: "对象存储笔记：元数据服务：对象索引与列目录"
series: object_storage
categories: [storage]
tags: [存储, 对象存储]
permalink: /object-storage-note-010-post/
redirect_from:
  - /object-storage-note-073-post/
---

本文围绕「对象存储笔记：元数据服务：对象索引与列目录」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![对象存储笔记：元数据服务：对象索引与列目录](/images/diagrams/object-storage-metadata-index.svg)
## 1. 元数据服务在对象存储中的位置

payload 放数据节点，元数据负责：key→location/version/etag，以及目录/索引能力。

## 2. 两条链路

- GET：单 key 元数据命中 → 定位数据
- LIST：目录/前缀索引（更容易滞后，且更容易热点倾斜）

## 3. 排障顺序

先看元数据 QPS/延迟与缓存命中，再看热点 key/prefix 与分区策略，最后看一致性与版本化设计。
