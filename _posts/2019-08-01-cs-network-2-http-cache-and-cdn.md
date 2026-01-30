---
layout: single
title: "网络（2）：HTTP 缓存与 CDN"
series: cs_network
permalink: /cs/network/http-cache-and-cdn/
tags: [计算机网络]
---

这篇用最短路径理解两件事：

- HTTP 缓存为什么能显著降低延迟与带宽成本
- CDN 为什么能把“离用户更近”变成确定收益

## 1. HTTP 缓存的目标

让相同资源的重复请求尽量不回源：

- **减少 RTT**：就近命中更快
- **减少带宽**：节省回源流量
- **减轻源站压力**：提升稳定性

## 2. 两类缓存：强缓存 vs 协商缓存

- **强缓存**：在有效期内，客户端/中间缓存直接用本地副本
  - 典型：`Cache-Control: max-age=...`
- **协商缓存**：过期后向服务器确认“资源有没有变”
  - 典型：`ETag` / `If-None-Match`，或 `Last-Modified` / `If-Modified-Since`

没变就返回 304（不带 body），省流量也省时间。

## 3. CDN 的核心：就近分发 + 多级缓存

CDN 通过边缘节点把内容缓存到离用户近的地方：

- 静态资源（图片/JS/CSS）收益最稳定
- 动态内容也能通过边缘计算/缓存策略部分加速

## 4. 实战关注点

- 缓存键（URL/Query/Header）设计不当会导致命中率差
- 过长 TTL 会带来更新不及时，需要配合 purge/版本号（hash）策略

