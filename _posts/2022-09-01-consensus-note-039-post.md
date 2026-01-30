---
layout: single
title: "一致性笔记：线性一致性：从客户端视角理解"
series: consensus
categories: [distributed]
tags: [分布式, 一致性]
permalink: /consensus-note-039-post/
---

本文围绕「一致性笔记：线性一致性：从客户端视角理解」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![一致性笔记：线性一致性：从客户端视角理解](/images/diagrams/consensus-linearizability-client.svg)
## 1. 线性一致性的直觉：像“单机按时间排序”

从客户端视角：所有操作看起来在某个全局时间线中依次发生。

## 2. 你为什么会关心

涉及强读、交易、配置变更、幂等与去重时，语义边界非常关键。

## 3. 验证与排障

先把语义说清楚（读写承诺），再看实现是否满足（leader 路径、quorum、读屏障/lease）。
