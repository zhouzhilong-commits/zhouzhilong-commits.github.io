---
layout: single
title: "对象存储笔记：多区域容灾：RPO/RTO 与复制链路"
series: object_storage
categories: [storage]
tags: [存储, 对象存储]
permalink: /object-storage-note-045-rpo-rto/
---

本文围绕「对象存储笔记：多区域容灾：RPO/RTO 与复制链路」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![对象存储笔记：多区域容灾：RPO/RTO 与复制链路](/images/diagrams/rpo-rto-tradeoff.svg)
## 1. RPO / RTO 是什么

- RPO：最多能丢多少数据
- RTO：最多能停多久

## 2. 工程权衡

同步复制更小 RPO 但更贵；异步复制吞吐更高但有窗口。

## 3. 排障顺序

先确认业务目标，再把系统拆成：复制链路延迟、故障检测与切换时间、恢复/重建速度。
