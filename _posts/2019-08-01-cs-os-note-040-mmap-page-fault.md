---
layout: single
title: "操作系统笔记：mmap 与 page fault：一次缺页到底发生了什么"
series: cs_os
categories: [cs]
tags: [计算机基础, 操作系统, 虚拟内存, mmap, page-fault]
date: 2019-08-01
permalink: /cs-os-note-040-mmap-page-fault/
---

`mmap` 把“文件”与“内存地址空间”连接起来：读写文件内容可以变成对内存的 load/store。它常用于：

- 零拷贝式的文件读（减少 read 系统调用与拷贝）
- 大文件随机访问（按需缺页加载）
- 共享内存（跨进程共享页）

但 mmap 的工程难点也集中在 page fault：**缺页会把“访问内存”变成一次内核路径 + IO**，尾延迟可能被 page fault 放大。本文把一次缺页拆成可理解的步骤。

---

## 1. mmap 的两种直觉：文件映射与匿名映射

### 1.1 文件映射（file-backed）

```
fd = open(file)
addr = mmap(fd)
read bytes by: *(addr + offset)
```

底层含义：虚拟页表项指向“该文件某个 offset 的页”，实际物理页可能尚未加载。

### 1.2 匿名映射（anonymous）

```
addr = mmap(MAP_ANON)
```

用于堆/栈之外的大块内存分配（也可能是共享匿名页）。它通常与 swap/零页等机制相关。

---

## 2. 缺页（page fault）发生时：从 CPU trap 到页就绪

当 CPU 访问某个虚拟地址 VA：

1) TLB miss -> 查页表
2) 页表项不存在或权限不满足 -> 触发 page fault 异常（trap）
3) 内核 page fault handler 接管

抽象路径：

```
CPU load/store VA
  -> page fault trap
    -> kernel: handle_mm_fault()
        - find VMA
        - check permissions
        - allocate page or locate file page
        - schedule IO if needed
        - install PTE
  -> return to user
  -> retry instruction
```

---

## 3. 文件映射缺页：从 page cache 找或从磁盘读

文件映射缺页的关键问题：该页是否已经在 page cache 中。

### 3.1 命中 page cache（minor fault）

若文件对应的页已经在 page cache：

- 只需要建立 PTE 映射到该物理页
- 不需要磁盘 IO

这类 fault 常被称为 minor fault（仍有内核开销，但较小）。

### 3.2 未命中 page cache（major fault）

若 page cache 没有该页：

- 内核需要发起磁盘读，把数据读入 page cache
- 等 IO 完成后再建立 PTE

这类是 major fault，延迟可能从微秒到毫秒，取决于存储与并发。

```
major fault:
  allocate page -> submit read -> wait -> mark uptodate -> map
```

---

## 4. 写时复制（COW）：为什么 fork 很快

`fork()` 之后父子进程逻辑上拥有相同的地址空间，但物理上并不会立刻复制所有页。常见做法：

- 父子共享同一物理页
- 页表项标记为只读
- 当任一方尝试写入该页时触发 fault
- 内核复制一份新页给写入方（copy-on-write）

示意：

```
fork:
  parent PTE -> page X (RO)
  child  PTE -> page X (RO)

child writes:
  fault -> allocate page Y
  copy X -> Y
  child PTE -> Y (RW)
```

工程含义：

- fork 本身快（只复制页表元数据）
- 第一次写入某页会触发 COW，可能造成延迟尖刺

---

## 5. mmap 写回：脏页与 msync

对文件映射进行写入，通常会：

- 修改 page cache 中的页
- 把页标记为 dirty
- 后台 writeback 把脏页写回磁盘

若需要更强的持久性语义：

- `msync()` 可请求把映射范围写回（但成本高）
- 或采用“WAL + fsync”类方案保证提交点

关键直觉：mmap 写并不等价于“立即写盘”，与 buffered write 类似，同样受 writeback 策略影响。

---

## 6. 性能与尾延迟：mmap 常见坑

### 6.1 第一次访问抖：page fault 放大尾延迟

如果访问模式是随机跳跃：

- 每次跳到新页都可能触发 major fault
- 延迟与 IO 绑定，P99 会被放大

缓解手段：

- `madvise(MADV_WILLNEED)`：预取提示（不保证）
- 顺序访问配合 readahead（或应用层批量访问）
- 热路径避免第一次触页（预热）

### 6.2 页抖动：工作集超过内存

当工作集远大于可用内存时：

- page cache 与匿名页争用
- 频繁回收/换入换出（swap）或频繁回收 page cache
-> 形成抖动（thrashing）

### 6.3 NUMA 与大页（THP）

在 NUMA 机器上，page fault 还决定了“页分配在哪个 NUMA 节点”，会影响后续访问延迟；THP（透明大页）也会改变 fault 与 TLB 行为。

---

## 7. 观测与排查

建议关注：

- minor/major faults 计数与速率
- major fault 的 IO 延迟分布
- readahead 命中率（若可观测）
- 系统内存压力：page cache 与匿名页比例、回收速率

常见定位路径：

- P99 抖动与 major fault 同步上升：说明热路径在触发磁盘读
- fault 上升但 IO 不高：可能是 page cache 命中（minor fault），瓶颈在内核路径/锁竞争

---

## 8. 小结

mmap 的工程优势来自“把 IO 变成地址空间访问”，但 page fault 把这种访问的成本从纳秒级拉到了微秒/毫秒级。把 fault 分成 minor/major、理解 page cache 的角色、明确 COW 与 writeback 的语义，才能把 mmap 用在正确的路径上并解释尾延迟。

