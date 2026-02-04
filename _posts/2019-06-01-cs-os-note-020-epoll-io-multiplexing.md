---
layout: single
title: "操作系统笔记：IO 多路复用：select/poll/epoll 的代价模型"
series: cs_os
categories: [cs]
tags: [计算机基础, 操作系统, 网络, epoll, IO]
date: 2019-06-01
permalink: /cs-os-note-020-epoll-io-multiplexing/
---

这篇笔记把 IO 多路复用当作一个“代价模型”问题：**在大量连接/FD 下，如何以更低的 CPU 成本判断哪些 FD 可读/可写**。常见路径：

- `select`：用户态传 fdset，内核每次线性扫描
- `poll`：用户态传数组，内核每次线性扫描
- `epoll`：注册 + 事件驱动，把“谁就绪”的集合增量维护

重点不在 API，而在“为什么 epoll 在高并发下更省 CPU、但仍会踩坑（ET/LT、惊群、回压）”。

---

## 1. 问题抽象：大量 FD 的就绪检测

假设有 100K 连接，绝大多数时刻只有很少连接有数据：

```
FD count: 100000
ready per tick: ~几十
```

如果每次循环都扫描全部 FD，CPU 会浪费在“检查不就绪”的工作上。

---

## 2. select/poll：每轮 O(N) 扫描

### 2.1 select 的代价

- 受 fdset 大小限制（历史原因）
- 每次调用都要把 fdset 从用户态拷贝到内核态
- 内核要线性扫描所有 bit/FD

### 2.2 poll 的代价

poll 去掉了 fdset 限制，但本质仍是：

- 每次把 `pollfd[]` 拷贝到内核
- 内核线性扫描数组，检查每个 FD 的状态

结论：当 FD 很多、就绪很少时，`select/poll` 的 CPU 成本随 N 线性增长。

---

## 3. epoll：注册 + 就绪队列（增量维护）

### 3.1 基本模型

epoll 把工作拆成两步：

1) **注册**：把 FD 加入 epoll 实例，并声明关心的事件
2) **等待**：内核维护一个“已就绪列表”，`epoll_wait` 直接返回就绪集合

```
epoll_ctl(ADD, fd, events)
...
ready = epoll_wait(epfd)
for fd in ready:
  handle(fd)
```

### 3.2 为什么能避免 O(N) 扫描

关键在于“事件到来时谁负责把 fd 放入就绪队列”：

- 当网卡收包、协议栈把数据放入 socket 接收队列时
- 内核把这个 socket 对应的 fd 标记为就绪，并加入 epoll ready list

所以 `epoll_wait` 不必扫描所有 fd，而是消费 ready list。

---

## 4. LT vs ET：边沿触发的正确使用方式

### 4.1 LT（Level Triggered）

只要 fd 仍然可读/可写，就会持续被返回。

优点：不易漏事件；缺点：若处理不彻底，可能反复被唤醒。

### 4.2 ET（Edge Triggered）

只有从“不可读→可读”这样的边沿变化时才通知一次。

优点：减少重复通知；缺点：若一次没把数据读干净，会“卡住”（不再收到通知）。

ET 的关键纪律：**必须读到 `EAGAIN`**。

```
on readable event:
  while true:
    n = read(fd, buf)
    if n > 0: continue
    if n == 0: close
    if errno == EAGAIN: break   // drained
```

---

## 5. 惊群（thundering herd）与 accept 竞争

多进程/多线程同时 `epoll_wait`，同一监听 socket 就绪时，可能出现：

- 多个 worker 同时被唤醒
- 只有一个能 accept 成功，其他被唤醒后又睡回去

缓解思路：

- `SO_REUSEPORT`：让内核在多个监听 socket 之间分配连接
- accept mutex：在用户态串行化 accept（代价是潜在瓶颈）
- 合理的 worker 数量：避免过度并发等待同一资源

---

## 6. 回压（backpressure）：可写事件不等于“无限可写”

常见误用：把 EPOLLOUT 当作“可以一直写”，导致：

- 用户态不断写满 socket buffer
- 系统调用频率高
- 队列堆积导致尾延迟上升

工程落点：

- 只在有待发送数据时监听 EPOLLOUT
- 发送队列清空后及时取消监听
- 配合应用层限流与队列长度上限

---

## 7. 观测与排查

常见症状：

- CPU 高但吞吐不高：可能是 wakeup 过多或空转扫描
- 延迟抖动：可能是惊群/队列堆积/写放大

建议指标：

- 每轮 `epoll_wait` 返回事件数分布（平均/长尾）
- 可读事件的“读到 EAGAIN”比例（ET 是否正确 draining）
- accept 失败/重试次数（惊群信号）
- 发送队列长度与 EPOLLOUT 触发频率（回压是否生效）

---

## 8. 小结

IO 多路复用的核心不是“多路”，而是**把就绪检测从每轮 O(N) 扫描，变成事件到来时的增量维护**。`epoll` 在高并发下更省 CPU，但 ET/LT、惊群与回压的工程细节决定了最终的尾延迟与稳定性。

