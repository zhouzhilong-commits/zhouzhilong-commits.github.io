---
layout: single
title: "KV存储笔记：反熵（anti-entropy）、read-repair 与一致性修复"
series: kv_storage
categories: [storage]
tags: [存储, kv存储, 反熵, 修复, 一致性]
date: 2021-09-18
permalink: /kv-storage-note-003-anti-entropy-repair/
---

复制系统长期运行一定会产生副本分歧（divergence）。原因不是“实现有 bug”，而是现实世界的常态：

- 副本短暂不可用、超时、网络抖动
- coordinator 在达到 W 之前返回失败，但部分副本已经写入
- 后台 compaction/flush 引起尾延迟，使得写入在不同副本上完成时间不同

因此必须有一套“**修复（repair）**”机制让系统最终收敛。

本文把修复拆成两条路径：

- **read-repair**：读路径发现不一致，顺手修复
- **anti-entropy**：后台周期性对比并回补（常见 Merkle tree/差分同步）

---

## 1. 分歧的类型：落后、缺失、并发冲突

### 1.1 落后（stale）

某副本缺少最近一段写入（例如短暂不可用期间没收到写），但缺失的是“最新版本”，没有并发冲突。

### 1.2 缺失（missing fragment）

某些 key 在副本上完全缺失（例如磁盘坏块/数据文件丢失），需要从其他副本完整回补。

### 1.3 并发冲突（concurrent）

同一 key 产生并发写，版本不可比较（向量时钟会体现为 siblings）。修复机制只能“搬运版本”，不能自动合并语义。

---

## 2. read-repair：把修复挂在读路径上

### 2.1 基本流程

以 N=3，R=2 为例：

```
read(key):
  1) read from 2 replicas in parallel
  2) compare versions:
       - pick winner (latest) or return multiple versions
  3) if mismatch:
       - send repair write to stale replica(s) (sync or async)
  4) return result
```

### 2.2 同步修复 vs 异步修复

- **同步修复**：读请求等待 repair 完成再返回。优点是收敛快；缺点是读延迟被拖慢。
- **异步修复**：读先返回，repair 在后台执行。优点是读延迟更稳；缺点是收敛慢，且 repair 队列可能积压。

工程常见选择：异步为主 + 针对关键表/关键路径提供同步开关。

### 2.3 read-repair 的边界

read-repair 依赖“有人读”。对于冷 key：

- 很少被读 → 很难被 read-repair 修复
- 这时需要 anti-entropy 兜底

---

## 3. anti-entropy：后台对比与差分同步

### 3.1 为什么需要

anti-entropy 解决两个问题：

- 冷 key 也能最终收敛
- 大规模分歧可以用批量方式修复，而不是把每次读都变成修复触发器

### 3.2 Merkle tree 的直觉

把一个 key range 做成树形摘要：

- 叶子是某个范围内 key 的 hash 聚合（或版本聚合）
- 父节点是子节点 hash 的 hash

对比两副本的 Merkle tree：

- 根相同 → 整个范围一致，无需继续
- 根不同 → 递归下探直到定位到不一致的子范围

示意：

```
Range [A..Z]
          root
        /      \
   [A..M]      [N..Z]
    /  \        /  \
 [A..F][G..M] [N..T][U..Z]
```

对比时只有“不同的子树”需要进一步拉取或回补，避免全量扫描。

### 3.3 anti-entropy 的输出：差分回补

定位到不一致的子范围后，常见两种回补方式：

- **pull**：缺失方拉取 key/value（或 value 的某个版本）
- **push**：拥有方推送差分

同时要考虑：

- tombstone（删除标记）也必须参与一致性，否则会出现“删了又回来”
- 多版本冲突需要完整同步版本集合（或按系统策略裁剪）

---

## 4. 修复与资源：修复本质是后台 IO 工作负载

修复会消耗：

- 网络带宽（拉取/推送）
- 磁盘带宽（读旧数据、写回补数据）
- CPU（hash/压缩/解码）

如果修复不受控，会反过来拖垮前台读写。典型需要：

- 修复限速（bytes/s）
- 修复并发度（每节点同时修复多少 range）
- 前台优先级（IO 调度/线程优先级）

---

## 5. 一致性语义与修复：哪些系统性坑必须规避

### 5.1 tombstone 必须被修复传播

删除如果只在部分副本生效，未命中副本会“复活”旧值。删除语义必须与写入语义同等对待。

### 5.2 修复与 compaction/GC 的竞态

如果系统有 TTL/过期清理：

- 一个副本已经把某版本 GC 掉，另一个副本仍保留
- 修复时必须知道“是否允许回补已 GC 的版本”

否则可能出现：

- 回补把已过期数据重新引入
- 或缺失版本导致冲突合并失败

这通常需要把“版本保留策略”变成全局一致的规则，并让修复在规则内运行。

---

## 6. 观测指标（建议）

- read-repair：触发次数、成功率、平均/尾部耗时、异步队列长度
- anti-entropy：每轮扫描覆盖范围、Merkle 对比耗时、差分条目数、回补流量
- 分歧程度：版本落后分布（lag）、key 缺失率（可抽样）、冲突（siblings）数量
- 资源影响：修复带宽与前台延迟的相关性

---

## 7. 小结

复制系统的“一致性”不是静态属性，而是“写入 + 版本 + 修复”共同作用的动态过程：

- read-repair 让热点 key 收敛快
- anti-entropy 让冷 key 最终收敛
- tombstone/版本保留策略决定了修复是否会引入“复活”和“回补过期”的系统性问题

下一篇会把“版本与冲突解决”展开：向量时钟、LWW 与多值返回的工程取舍。

