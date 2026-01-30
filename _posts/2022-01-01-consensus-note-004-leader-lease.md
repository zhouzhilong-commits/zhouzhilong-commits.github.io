---
layout: single
title: "一致性笔记：Leader 选举：租约（lease）与心跳"
series: consensus
categories: [distributed]
tags: [分布式, 一致性]
permalink: /consensus-note-004-leader-lease/
redirect_from:
  - /consensus-note-067-leader-lease/
---

本文围绕「一致性笔记：Leader 选举：租约（lease）与心跳」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![一致性笔记：Leader 选举：租约（lease）与心跳](/images/diagrams/leader-lease-timeline.svg)
## 1. lease 的直觉

用时间窗口减少读路径的共识成本：在 lease 有效期内，leader 可以更快回答读（取决于系统语义）。

## 2. 风险

时钟与网络抖动会影响 lease 的正确性边界；要谨慎定义“读的承诺”。

## 3. 排障顺序

先确认你要的读语义（线性/顺序/最终），再看时钟漂移与 RTT 分布，最后决定是否使用 lease。
