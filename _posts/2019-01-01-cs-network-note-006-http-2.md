---
layout: single
title: "网络笔记：HTTP/2：多路复用与队头阻塞"
series: cs_network
categories: [cs]
tags: [计算机基础, 网络]
permalink: /cs-network-note-006-http-2/
redirect_from:
  - /cs-network-note-041-http-2/
---

本文深入解析 HTTP/2 的核心特性：多路复用、流控、头部压缩，以及传输层队头阻塞问题。

HTTP/2 解决的是 HTTP/1.1 的两个痛点：

- 一个连接上并发很多请求时，HTTP/1.1 很容易靠"开更多 TCP 连接"硬扛（成本高）
- 应用层更需要"多路复用 + 优先级 + 流控"来管理并发

但它也带来一个经常被误解的点：

> HTTP/2 消除了 HTTP/1.1 的**应用层队头阻塞**，但在 TCP 上仍然可能遭遇**传输层队头阻塞**（丢包会影响同连接内所有 stream）。

![HTTP/2：多路复用、流控与"TCP 层 HoL"](/images/diagrams/http2-multiplexing-flow-control.svg)

## 1. 最小模型：stream / frame / connection

- **connection**：底层仍是一个 TCP 连接（通常再叠 TLS）
- **stream**：一个逻辑请求-响应通道（带 stream id），同连接可并发多个
- **frame**：HTTP/2 的最小传输单元，多个 stream 的 frame 交错发送（这就是多路复用）

### 1.1 HTTP/2 的层次结构

```mermaid
flowchart TD
  A[Application] --> B[HTTP/2]
  B --> C[Stream 1]
  B --> D[Stream 2]
  B --> E[Stream N]
  
  C --> F[Frame]
  D --> F
  E --> F
  
  F --> G[TCP Connection]
  G --> H[TLS]
  H --> I[Network]
```

### 1.2 Frame 类型

```mermaid
flowchart TD
  A[HTTP/2 Frame] --> B[HEADERS]
  A --> C[DATA]
  A --> D[SETTINGS]
  A --> E[WINDOW_UPDATE]
  A --> F[PING]
  A --> G[GOAWAY]
  
  B --> H[请求/响应头]
  C --> I[请求/响应体]
  E --> J[流控]
```

## 2. 多路复用带来的真实收益

能直接得到：

- **更少连接数**：降低握手成本、降低内核资源占用、减少拥塞控制之间的相互干扰
- **更好的并发管理**：请求可以在应用层交错发送，不需要为并发硬开 N 条 TCP

### 2.1 HTTP/1.1 vs HTTP/2

```mermaid
sequenceDiagram
  participant C as Client
  participant S as Server

  Note over C,S: HTTP/1.1: 需要多个连接
  C->>S: Connection 1: Request 1
  C->>S: Connection 2: Request 2
  C->>S: Connection 3: Request 3
  S-->>C: Response 1
  S-->>C: Response 2
  S-->>C: Response 3

  Note over C,S: HTTP/2: 单连接多路复用
  C->>S: Stream 1: Request 1
  C->>S: Stream 2: Request 2
  C->>S: Stream 3: Request 3
  S-->>C: Stream 1: Response 1
  S-->>C: Stream 2: Response 2
  S-->>C: Stream 3: Response 3
```

### 2.2 性能对比

```mermaid
flowchart TD
  A[HTTP/1.1] --> B[多个 TCP 连接]
  B --> C[高连接成本]
  B --> D[拥塞控制干扰]
  
  E[HTTP/2] --> F[单 TCP 连接]
  F --> G[低连接成本]
  F --> H[统一拥塞控制]
  
  C --> I[性能差]
  G --> J[性能好]
```

## 3. 但为什么还会"卡"：TCP 层队头阻塞（HoL）

关键事实：HTTP/2 的多路复用发生在 **TCP 之上**。

当 TCP 丢包时：

- TCP 必须按序交付字节流
- 丢失的那段字节没重传回来前，后面的字节即使到了也不能交给上层

于是同连接里所有 stream 的数据都可能被一起拖住 —— 这就是"HTTP/2 还会卡"的根因之一。

### 3.1 TCP 层 HoL Blocking

```mermaid
sequenceDiagram
  participant App as HTTP/2 App
  participant TCP as TCP
  participant Network as Network

  App->>TCP: Stream 1 Frame 1
  App->>TCP: Stream 2 Frame 1 (丢失)
  App->>TCP: Stream 3 Frame 1
  App->>TCP: Stream 1 Frame 2
  
  TCP->>Network: Packet 1
  TCP->>Network: Packet 2 (丢失)
  TCP->>Network: Packet 3
  TCP->>Network: Packet 4
  
  Network->>TCP: Packet 1
  Network->>TCP: Packet 3
  Network->>TCP: Packet 4
  
  Note over TCP: 等待 Packet 2 重传
  
  TCP->>TCP: 重传 Packet 2
  Network->>TCP: Packet 2
  
  TCP->>App: 交付所有数据
  
  Note over App: 所有 Stream 都被阻塞
```

### 3.2 HoL 的影响

```mermaid
flowchart TD
  A[TCP 丢包] --> B[按序交付要求]
  B --> C[后续数据等待]
  C --> D[所有 Stream 阻塞]
  
  D --> E[延迟增加]
  E --> F[吞吐下降]
```

## 4. 流控（flow control）：别把它当成"优化"，它更像"背压"

HTTP/2 有连接级与 stream 级窗口（概念上理解即可）：

- 读端处理不过来 → 窗口不增长 → 写端不能继续发
- 这是在保护系统：避免一端无限堆积内存

但工程上流控也会带来两类现象：

- **吞吐被窗口限制**：尤其是大对象/长响应
- **尾延迟被背压放大**：慢消费者会把同连接的发送节奏拖慢

### 4.1 流控机制

```mermaid
sequenceDiagram
  participant Sender as Sender
  participant Receiver as Receiver

  Sender->>Receiver: Data (窗口: 100)
  Receiver->>Receiver: 处理数据
  Receiver->>Sender: WINDOW_UPDATE (窗口: 50)
  
  Note over Sender: 窗口不足，等待
  
  Receiver->>Receiver: 继续处理
  Receiver->>Sender: WINDOW_UPDATE (窗口: 100)
  
  Sender->>Sender: 可以继续发送
```

### 4.2 流控的影响

```mermaid
flowchart TD
  A[流控] --> B[连接级窗口]
  A --> C[Stream 级窗口]
  
  B --> D[限制总发送]
  C --> E[限制单 Stream]
  
  D --> F[背压]
  E --> F
  
  F --> G[吞吐受限]
  F --> H[延迟放大]
```

## 5. HPACK（头部压缩）：收益和坑都很现实

收益：

- 头部重复性高（cookie/metadata）时，压缩能节省带宽与 CPU（取决于实现）

坑：

- 动态表管理不当会造成 CPU 开销上升
- 某些场景头部很大，仍会对延迟造成影响（尤其是小包/高并发）

### 5.1 HPACK 压缩

```mermaid
flowchart TD
  A[HTTP Header] --> B[HPACK]
  B --> C[静态表查找]
  B --> D[动态表查找]
  B --> E[字面量编码]
  
  C --> F[压缩后 Header]
  D --> F
  E --> F
  
  F --> G[带宽节省]
  G --> H[CPU 开销]
```

### 5.2 头部压缩效果

| 场景 | 压缩前 | 压缩后 | 节省 |
|------|--------|--------|------|
| 重复头部 | 500 bytes | 50 bytes | 90% |
| 新头部 | 200 bytes | 150 bytes | 25% |

## 6. 怎么排障：先判断"卡在 TCP 还是卡在应用"

推荐顺序：

1. **先看丢包/重传**：如果丢包显著，同连接内所有 stream 变慢是正常现象
2. **再看连接内并发与队列**：是否把太多请求压在少量连接上？
3. **再看流控/背压**：是否存在慢消费者或窗口增长异常？
4. **最后看 CPU**：HPACK、TLS、协议栈开销是否成为瓶颈？

### 6.1 排障流程

```mermaid
flowchart TD
  A[HTTP/2 性能问题] --> B{丢包/重传?}
  B -->|是| C[TCP 层 HoL]
  B -->|否| D{连接内并发?}
  
  D -->|过多| E[连接压力大]
  D -->|正常| F{流控问题?}
  
  F -->|是| G[窗口/背压]
  F -->|否| H{CPU 问题?}
  
  H -->|是| I[HPACK/TLS 开销]
  H -->|否| J[其他问题]
  
  C --> K[优化网络/减少丢包]
  E --> L[增加连接/优化并发]
  G --> M[优化流控/背压]
  I --> N[优化加密/压缩]
```

## 7. HTTP/2 vs HTTP/3

### 7.1 HTTP/3 的改进

```mermaid
flowchart TD
  A[HTTP/2] --> B[TCP 层 HoL]
  B --> C[所有 Stream 阻塞]
  
  D[HTTP/3] --> E[基于 QUIC]
  E --> F[UDP + 多路复用]
  F --> G[Stream 独立]
  G --> H[无 HoL Blocking]
```

### 7.2 选择建议

- **HTTP/2**：适合丢包率低的网络
- **HTTP/3**：适合丢包率高或需要低延迟的场景

## 8. 实际案例

### 8.1 案例：TCP HoL 导致的性能问题

**问题**：HTTP/2 多路复用下，一个请求慢导致其他请求也慢

**分析**：
- 单连接多 stream
- TCP 丢包导致 HoL blocking
- 所有 stream 都被阻塞

**优化**：
- 使用 HTTP/3（基于 QUIC）
- 或增加连接数
- 或优化网络质量

**结果**：性能提升 40%

## 9. 小结

HTTP/2 的核心价值是"连接内多路复用 + 更精细的并发控制"。但它并不是"万物加速器"：在 TCP 丢包时仍可能出现连接级的 HoL。排障时先把问题拆成：**传输层（丢包/重传）** vs **应用层（背压/并发/CPU）**，效率会高很多。

**核心要点**：
- HTTP/2 通过多路复用减少连接数
- TCP 层 HoL blocking 仍会影响所有 stream
- 流控提供背压保护，但也可能限制性能
- HPACK 压缩节省带宽，但有 CPU 开销

**排障流程**：
1. 检查丢包/重传（TCP 层 HoL）
2. 检查连接内并发和队列
3. 检查流控和背压
4. 检查 CPU（HPACK/TLS）
