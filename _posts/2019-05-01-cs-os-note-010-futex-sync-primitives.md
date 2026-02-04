---
layout: single
title: "操作系统笔记：同步原语：mutex、futex 与条件变量"
series: cs_os
categories: [cs]
tags: [计算机基础, 操作系统, 并发, futex, mutex]
date: 2019-05-01
permalink: /cs-os-note-010-futex-sync-primitives/
---

这篇笔记整理三类经常一起出现的同步原语：**mutex、futex、条件变量**。重点不是 API 记忆，而是把“为什么快 / 为什么慢 / 为什么会卡住”拆成可观测的机制：

- **fast path**：无竞争时几乎不进内核
- **slow path**：竞争时进入内核睡眠/唤醒
- **调度与唤醒**：唤醒风暴、惊群、优先级反转
- **工程排查**：如何从现象定位到“锁争用 / 锁持有过长 / 唤醒策略错误”

全文不用 Mermaid，示意用 ASCII。

---

## 1. mutex 的目标：把竞争变成“有界的等待”

mutex 提供的不是“并行”，而是**互斥**：同一时刻只允许一个线程进入临界区，避免数据竞争。

要理解 mutex 的性能，关键是区分两条路径：

- **无竞争**：只做用户态原子操作（CAS），几十纳秒级
- **有竞争**：需要阻塞等待，涉及内核调度，微秒到毫秒级

```
lock():
  if fast_path_try_lock_success:
      enter critical section
  else:
      slow path: sleep (kernel) -> wake -> retry
```

---

## 2. futex：Fast Userspace Mutex 的直觉

Linux futex 的设计点：**把“是否需要睡眠”判断留在用户态，把“睡眠/唤醒”放到内核**。

### 2.1 futex 的两个操作

- `futex_wait(addr, expected)`：仅当 `*addr == expected` 时进入睡眠，否则直接返回
- `futex_wake(addr, n)`：唤醒等待在 `addr` 上的最多 n 个线程

它依赖一个用户态地址 `addr` 作为“等待键”。

### 2.2 为什么叫 Fast Userspace

无竞争时，只需要 CAS 把锁从 0 改为 1，不需要系统调用：

```
uaddr (int):
  0 = unlocked
  1 = locked, no waiters (常见实现会有更多状态)
  2 = locked, has waiters
```

有竞争时，失败线程才会调用 `futex_wait()` 进入内核队列。

---

## 3. 一个典型实现：pthread mutex 的“用户态 + futex”组合（抽象）

### 3.1 加锁（简化伪代码）

```c
// state: 0=unlocked, 1=locked(no waiters), 2=locked(has waiters)
int lock(int* state) {
  if (cas(state, 0, 1)) return 0;             // fast path

  // slow path
  for (;;) {
    int s = atomic_load(state);
    if (s == 0 && cas(state, 0, 2)) return 0; // 抢到锁并标记有等待者
    if (s != 2) atomic_store(state, 2);       // 标记：有等待者（避免丢唤醒）
    futex_wait(state, 2);                     // 只有 state==2 才睡
  }
}
```

### 3.2 解锁（简化伪代码）

```c
int unlock(int* state) {
  int prev = atomic_exchange(state, 0);
  if (prev == 2) futex_wake(state, 1);        // 有等待者才唤醒
  return 0;
}
```

这类实现的关键点：

- **避免无谓 syscall**：无竞争时完全用户态
- **避免丢唤醒**：用状态位把“有人在等”编码出来
- **控制唤醒数**：一般唤醒 1 个，避免惊群

---

## 4. 条件变量：把“等待某个条件成立”与“互斥”组合起来

条件变量的语义不是互斥，而是**等待某个条件**。经典用法：

```
producer:
  lock(m)
  push(item)
  signal(cv)
  unlock(m)

consumer:
  lock(m)
  while queue empty:
      wait(cv, m)   // 原子地：释放 m 并睡眠；醒来后重新持有 m
  pop(item)
  unlock(m)
```

### 4.1 为什么必须用 while 而不是 if

因为会出现：

- 虚假唤醒（spurious wakeup）
- 多消费者竞争：一个 signal 唤醒多个，只有一个拿到资源
- 条件在醒来前又被其他线程改变

因此必须在醒来后重新检查条件。

---

## 5. 常见性能坑：锁持有过长、惊群、优先级反转

### 5.1 锁持有过长

临界区里做 IO、做大对象分配、做复杂计算，会把 mutex 变成“串行化点”，吞吐和尾延迟都会变差。

症状：

- CPU 利用率不高但延迟高
- 线程大量阻塞在同一把锁

### 5.2 惊群（thundering herd）

错误用法：每次状态变化都 `broadcast` 唤醒所有等待者。

后果：

- 大量线程被唤醒又睡回去
- 发生频繁上下文切换，cache/TLB 受损

建议：

- 能 `signal` 就不要 `broadcast`
- 唤醒数量与资源数量匹配

### 5.3 优先级反转（priority inversion）

低优先级线程持锁，高优先级线程等待锁，中优先级线程抢占 CPU，导致高优先级线程“被中优先级间接阻塞”。

常见缓解：

- 优先级继承（priority inheritance，部分 mutex 支持）
- 缩短临界区
- 避免跨 CPU 的长时间持锁

---

## 6. 从现象到定位：工程排查清单

### 6.1 现象分类

- **锁争用**：等待线程多，持锁时间中等
- **长临界区**：等待线程多，持锁时间很长
- **唤醒策略问题**：大量 wakeup 但进展很少（wakeup->sleep 循环）

### 6.2 可观测指标

- 每把锁的：平均/最大持锁时间、争用次数、等待队列长度
- futex：`futex_wait` 次数、`futex_wake` 次数、唤醒失败（wake 0）
- 调度：上下文切换次数（voluntary/involuntary）、runqueue 长度

### 6.3 工具方向（抽象）

- 采样剖析：看线程阻塞栈是否集中在同一把锁
- 事件追踪：统计 futex wait/wake 的热点地址
- 业务指标关联：某锁争用与 P99 延迟是否同步上升

---

## 7. 小结

mutex/futex/条件变量这套组合的工程直觉可以浓缩成一句话：

> 竞争少时全用户态，竞争多时让内核帮忙睡眠与唤醒；条件变量负责“等条件”，mutex 负责“保护条件的检查与更新”。

把性能问题拆成“fast path 失败频率”和“slow path 睡眠/唤醒成本”，再用持锁时间与唤醒策略来解释尾延迟，排查路径会清晰很多。

