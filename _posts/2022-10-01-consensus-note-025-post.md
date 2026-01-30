---
layout: single
title: "一致性笔记：脑裂：什么时候会发生，怎么避免"
series: consensus
categories: [distributed]
tags: [分布式, 一致性]
permalink: /consensus-note-025-post/
redirect_from:
  - /consensus-note-074-post/
---

本文围绕「一致性笔记：脑裂：什么时候会发生，怎么避免」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![一致性笔记：脑裂：什么时候会发生，怎么避免](/images/diagrams/consensus-split-brain.svg)
## 1. 脑裂是什么：同一时刻出现两个“主”

常见根因：网络分区 + 错误的主选举/租约边界/仲裁缺失。

## 2. 工程上怎么避免

- 明确仲裁：quorum/多数派/外部仲裁
- 明确 lease 边界与时钟假设
- 降低误判：心跳与超时要结合 RTT 分布

## 3. 观测与排障

优先看：选主频率、心跳 RTT 分布、分区事件（丢包/重传/抖动），以及是否出现双写迹象。
