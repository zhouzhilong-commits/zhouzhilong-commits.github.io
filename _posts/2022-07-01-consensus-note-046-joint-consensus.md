---
layout: single
title: "一致性笔记：成员变更：joint consensus 的必要性"
series: consensus
categories: [distributed]
tags: [分布式, 一致性]
permalink: /consensus-note-046-joint-consensus/
---

本文围绕「一致性笔记：成员变更：joint consensus 的必要性」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![一致性笔记：成员变更：joint consensus 的必要性](/images/diagrams/raft-joint-consensus.svg)
## 1. joint consensus 解决什么

成员变更时避免“新旧配置各自形成多数派”，用联合多数派保证安全。

## 2. 工程关注点

成员变更是高风险操作：需要明确状态机、回滚策略与观测告警。
