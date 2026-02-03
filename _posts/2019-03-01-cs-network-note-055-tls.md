---
layout: single
title: "网络笔记：TLS 握手：延迟优化与会话复用"
series: cs_network
categories: [cs]
tags: [计算机基础, 网络]
permalink: /cs-network-note-055-tls/
redirect_from:
  - /cs-network-note-020-tls/
---

本文深入解析 TLS 握手的工作原理、延迟来源、会话复用机制和工程优化实践。

![网络笔记：TLS 握手：延迟优化与会话复用](/images/diagrams/tls-handshake-keys.svg)

## 1. TLS 给你什么：不仅是"加密"，更是"身份 + 完整性"

工程语义上，TLS 主要提供三件事：

- **机密性**：第三方拿不到明文（对称加密）
- **完整性**：内容被篡改能被发现（MAC/AEAD）
- **身份认证**：你连到的是"对的服务器"（证书链验证）

### 1.1 TLS 的安全目标

```mermaid
flowchart TD
  A[TLS 安全目标] --> B[机密性]
  A --> C[完整性]
  A --> D[身份认证]
  
  B --> E[对称加密]
  C --> F[MAC/AEAD]
  D --> G[证书链验证]
```

### 1.2 TLS 的层次结构

```mermaid
flowchart TD
  A[Application] --> B[TLS]
  B --> C[Handshake]
  B --> D[Record]
  
  C --> E[密钥交换]
  C --> F[身份验证]
  
  D --> G[加密]
  D --> H[完整性保护]
  
  B --> I[TCP]
```

## 2. 握手为什么会慢：两个硬成本（RTT + CPU）

### 2.1 RTT 成本：跨地域一切都慢

握手需要若干次往返（取决于版本与是否恢复会话）。因此：

- **跨地域 RTT 高** → 握手延迟天然高
- 丢包/重传/队列化 → 会把握手的 P99 拉得更长

```mermaid
sequenceDiagram
  participant C as Client
  participant S as Server

  C->>S: ClientHello
  S-->>C: ServerHello + Certificate + ServerKeyExchange
  C->>S: ClientKeyExchange + ChangeCipherSpec + Finished
  S-->>C: ChangeCipherSpec + Finished
  
  Note over C,S: Full Handshake: 2 RTT
```

### 2.2 CPU 成本：密钥交换与证书链验证

握手阶段的 CPU 开销主要来自：

- 密钥交换（例如 ECDHE）
- 证书链验证（签名验证、证书链构建；OCSP/CRL 取决于实现）

如果在高 QPS 下频繁"新建连接"，CPU 会非常快地被握手打满。

```mermaid
flowchart TD
  A[TLS 握手 CPU 开销] --> B[密钥交换]
  A --> C[证书验证]
  
  B --> D[ECDHE 计算]
  C --> E[签名验证]
  C --> F[证书链构建]
  C --> G[OCSP/CRL 检查]
  
  D --> H[CPU 密集]
  E --> H
  F --> H
  G --> I[网络请求]
```

### 2.3 握手延迟分解

```mermaid
flowchart TD
  A[TLS 握手延迟] --> B[网络 RTT]
  A --> C[CPU 计算]
  A --> D[其他开销]
  
  B --> E[2-4 RTT]
  C --> F[密钥交换]
  C --> G[证书验证]
  
  E --> H[总延迟]
  F --> H
  G --> H
```

## 3. 会话复用/会话恢复：把"握手成本"从热路径搬走

工程上最关心的不是 TLS 理论，而是：**如何让业务请求尽量不在热路径上做完整握手**。

常见手段：

- **连接复用（keep-alive / 连接池）**：让多个请求共享同一条 TLS 连接
- **会话恢复（session resumption）**：新连接尽量走恢复路径（减少 RTT 与 CPU）

如果看到"握手占比很高"，大概率是连接复用没做好（或者被短连接/负载均衡策略破坏了）。

### 3.1 连接复用

```mermaid
sequenceDiagram
  participant C as Client
  participant S as Server

  C->>S: Full Handshake (第一次)
  S-->>C: 建立连接
  
  Note over C,S: 复用连接
  
  C->>S: Request 1 (复用)
  S-->>C: Response 1
  C->>S: Request 2 (复用)
  S-->>C: Response 2
  
  Note over C,S: 无额外握手开销
```

### 3.2 会话恢复

```mermaid
sequenceDiagram
  participant C as Client
  participant S as Server

  C->>S: ClientHello + Session ID
  S-->>C: ServerHello + Session ID + ChangeCipherSpec + Finished
  C->>S: ChangeCipherSpec + Finished
  
  Note over C,S: Session Resumption: 1 RTT
```

### 3.3 性能对比

| 方式 | RTT | CPU | 适用场景 |
|------|-----|-----|---------|
| Full Handshake | 2 RTT | 高 | 首次连接 |
| Session Resumption | 1 RTT | 低 | 会话恢复 |
| Connection Reuse | 0 RTT | 无 | 连接复用 |

```mermaid
flowchart TD
  A[握手方式] --> B[Full Handshake]
  A --> C[Session Resumption]
  A --> D[Connection Reuse]
  
  B --> E[2 RTT + 高 CPU]
  C --> F[1 RTT + 低 CPU]
  D --> G[0 RTT + 无 CPU]
  
  E --> H[性能差]
  F --> I[性能中]
  G --> J[性能好]
```

## 4. 应当观测什么（比"平均握手耗时"更有用）

- **握手延迟分位数**：P50/P95/P99，而不是平均值
- **握手失败率**：证书/协议/时间/中间盒子问题往往体现在失败率
- **新建连接比例**：是否异常偏高（连接复用是否有效）
- **CPU（尤其是单核热点）**：握手/加解密是否把某些核打爆

### 4.1 观测指标

```mermaid
flowchart TD
  A[TLS 观测指标] --> B[握手延迟]
  A --> C[握手失败率]
  A --> D[新建连接比例]
  A --> E[CPU 使用]
  
  B --> F[P50/P95/P99]
  C --> G[失败原因]
  D --> H[复用效率]
  E --> I[单核热点]
```

### 4.2 测量工具

```bash
# 查看 TLS 握手信息
openssl s_client -connect server:443 -showcerts

# 使用 tcpdump 分析
tcpdump -i eth0 -w tls.pcap 'tcp port 443'

# 应用层指标
# 握手延迟、失败率、连接复用率
```

## 5. 排障顺序（握手慢/失败/CPU 高）

1. **先看 RTT 与丢包/重传**：网络层面的长尾会直接放大握手 P99
2. **再看新建连接比例**：是否被短连接/错误的 LB 策略导致频繁 full handshake
3. **再看证书链与配置**：证书链过长、错误的中间证书、过期/时间偏差等
4. **最后看 CPU 与加密套件**：是否需要更合适的加密套件/硬件加速/线程模型调整

### 5.1 排障流程

```mermaid
flowchart TD
  A[TLS 性能问题] --> B{RTT/丢包?}
  B -->|是| C[网络问题]
  B -->|否| D{新建连接多?}
  
  D -->|是| E[连接复用问题]
  D -->|否| F{证书问题?}
  
  F -->|是| G[证书链/配置]
  F -->|否| H{CPU 问题?}
  
  H -->|是| I[加密套件/硬件加速]
  H -->|否| J[其他问题]
  
  C --> K[优化网络]
  E --> L[优化连接复用]
  G --> M[优化证书配置]
  I --> N[优化加密/硬件]
```

## 6. TLS 1.3 的改进

### 6.1 TLS 1.3 vs TLS 1.2

```mermaid
flowchart TD
  A[TLS 1.2] --> B[2 RTT Full Handshake]
  A --> C[1 RTT Resumption]
  
  D[TLS 1.3] --> E[1 RTT Full Handshake]
  D --> F[0 RTT Resumption]
  
  B --> G[慢]
  E --> H[快]
  C --> I[中]
  F --> J[最快]
```

### 6.2 TLS 1.3 的优势

- **更快的握手**：1 RTT full handshake
- **0 RTT 恢复**：会话恢复无需 RTT
- **更强的安全性**：移除不安全的加密套件
- **更少的 CPU**：优化的密钥交换

## 7. 实际案例

### 7.1 案例：连接复用导致的性能问题

**问题**：TLS 握手 CPU 占用高

**分析**：
- 新建连接比例 > 80%
- 连接池配置不当
- 负载均衡策略导致连接频繁断开

**优化**：
- 优化连接池配置
- 调整负载均衡策略
- 启用会话恢复

**结果**：
- 新建连接比例降到 10%
- CPU 占用降低 70%

### 7.2 案例：证书链过长导致的延迟问题

**问题**：TLS 握手 P99 延迟高

**分析**：
- 证书链包含 4 个证书
- 证书链传输和验证耗时
- 网络 RTT 正常

**优化**：
- 优化证书链（移除不必要的中间证书）
- 使用 OCSP stapling
- 启用 TLS 1.3

**结果**：P99 延迟降低 40%

## 8. 设计原则与最佳实践

### 8.1 优化原则

1. **优先连接复用**：减少握手次数
2. **启用会话恢复**：减少握手 RTT 和 CPU
3. **优化证书配置**：缩短证书链
4. **使用 TLS 1.3**：更快的握手

### 8.2 最佳实践

```mermaid
flowchart TD
  A[TLS 最佳实践] --> B[连接复用]
  A --> C[会话恢复]
  A --> D[证书优化]
  A --> E[TLS 1.3]
  
  B --> F[连接池]
  C --> G[Session Ticket]
  D --> H[短证书链]
  E --> I[更快握手]
```

## 9. 小结

TLS 性能优化的主线很清晰：**优先把 full handshake 从热路径移走（复用/恢复）**，其次才是抠 CPU（套件/实现/硬件）。排障时抓住 RTT、连接新建比例、失败率这三个信号，基本就能把问题快速归因。

**核心要点**：
- TLS 提供机密性、完整性、身份认证
- 握手延迟来自 RTT 和 CPU 计算
- 连接复用和会话恢复是关键优化
- TLS 1.3 提供更快的握手

**优化策略**：
1. 优先连接复用（连接池）
2. 启用会话恢复（Session Ticket）
3. 优化证书配置（短证书链）
4. 使用 TLS 1.3
