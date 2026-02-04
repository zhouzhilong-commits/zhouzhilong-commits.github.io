---
layout: single
title: "PolarDB：云原生数据库架构（论文笔记）"
series: paper_notes
permalink: /paper-notes/storage/polardb/
tags: [PolarDB, 云原生数据库, 存储计算分离, 论文笔记]
date: 2022-05-01
---

> 论文：PolarDB: A Cloud-Native Database Designed for the Cloud（Wang et al., SIGMOD 2022）

PolarDB 是阿里云开发的云原生数据库系统，采用存储计算分离架构，实现了高性能、高可用和弹性扩展。本文深入解析 PolarDB 的架构设计、核心机制和工程实践。

## 1. PolarDB 的设计目标与挑战

### 1.1 云原生数据库的需求

传统数据库在云环境下面临的挑战：

- **弹性扩展**：计算和存储需要独立扩展
- **高可用性**：需要自动故障恢复，减少 RTO
- **成本优化**：按需付费，避免资源浪费
- **性能要求**：保持接近本地数据库的性能

**传统架构 vs 云原生架构**：

```
传统架构：
┌─────────────────┐
│  Database Node  │
│  ┌───────────┐  │
│  │  Compute  │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │  Storage  │  │
│  └───────────┘  │
└─────────────────┘
问题：计算和存储耦合，难以独立扩展

云原生架构（PolarDB）：
┌─────────────┐     ┌─────────────┐
│  Compute   │────▶│  Storage    │
│  Nodes     │     │  Cluster    │
└─────────────┘     └─────────────┘
优势：计算和存储分离，独立扩展
```

### 1.2 核心设计目标

PolarDB 的设计目标：

1. **存储计算分离**：计算节点和存储集群解耦，独立扩展
2. **高性能**：接近本地数据库的性能，延迟 < 1ms
3. **高可用**：自动故障恢复，RTO < 30s
4. **弹性扩展**：计算节点和存储容量独立扩展
5. **兼容性**：兼容 MySQL/PostgreSQL 协议

## 2. PolarDB 的架构设计

### 2.1 整体架构

PolarDB 采用三层架构：

```
┌─────────────────────────────────────────┐
│         Application Layer                │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│      Compute Layer (Read/Write Nodes)    │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ Primary  │  │ Replica1 │  │Replica2││
│  └──────────┘  └──────────┘  └────────┘│
└─────────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │   PolarFS (RDMA)    │
         └──────────┬──────────┘
                    │
┌─────────────────────────────────────────┐
│      Storage Layer (PolarStore)         │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ Chunk 1  │  │ Chunk 2  │  │Chunk 3 ││
│  └──────────┘  └──────────┘  └────────┘│
└─────────────────────────────────────────┘
```

**架构组件**：

- **Compute Layer**：读写节点，处理 SQL 查询和事务
- **PolarFS**：分布式文件系统，提供 RDMA 访问
- **Storage Layer**：存储集群，管理数据块和日志

### 2.2 存储计算分离的优势

**传统架构的问题**：

```cpp
// 传统架构：计算和存储耦合
class TraditionalDB {
    LocalStorage storage;  // 本地存储
    void query() {
        // 查询需要访问本地存储
        // 扩展时需要同时扩展计算和存储
    }
};
```

**PolarDB 的分离架构**：

```cpp
// PolarDB：存储计算分离
class PolarDB {
    ComputeNode compute;  // 计算节点
    RemoteStorage storage;  // 远程存储
    
    void query() {
        // 通过 PolarFS 访问远程存储
        // 计算节点和存储可以独立扩展
    }
};
```

**分离架构的优势**：

1. **独立扩展**：计算节点和存储容量独立扩展
2. **资源共享**：多个计算节点共享同一份存储
3. **快速恢复**：计算节点故障时，新节点可以快速接入
4. **成本优化**：按需扩展，避免资源浪费

## 3. PolarFS：分布式文件系统

### 3.1 PolarFS 的设计

PolarFS 是 PolarDB 的核心组件，提供高性能的分布式文件访问：

**设计特点**：

- **RDMA 网络**：使用 RDMA 实现低延迟访问（< 1ms）
- **日志结构**：采用日志结构存储，优化写入性能
- **多副本**：数据多副本存储，保证高可用
- **一致性**：强一致性保证，支持事务语义

**PolarFS 架构**：

```
┌─────────────┐
│ Compute Node│
│  ┌────────┐ │
│  │PolarFS  │ │
│  │ Client  │ │
│  └────┬────┘ │
└───────┼──────┘
        │ RDMA
┌───────┼──────┐
│  ┌────▼────┐ │
│  │PolarFS  │ │
│  │ Metadata│ │
│  └────┬────┘ │
│       │      │
│  ┌────▼────┐ │
│  │ Chunk   │ │
│  │ Servers │ │
│  └─────────┘ │
└──────────────┘
```

### 3.2 RDMA 优化

PolarFS 使用 RDMA 实现高性能网络访问：

**RDMA vs 传统网络**：

- **传统 TCP/IP**：延迟 100-500μs，CPU 开销大
- **RDMA**：延迟 < 10μs，零拷贝，CPU 开销小

**RDMA 的优势**：

1. **低延迟**：绕过内核，直接访问内存
2. **高吞吐**：支持高带宽网络（100Gbps+）
3. **低 CPU 开销**：减少 CPU 参与，提高效率

**RDMA 工作原理**：

```
传统 TCP/IP 路径：
Application → Kernel → Network Stack → NIC → Network
问题：多次拷贝，内核参与，延迟高

RDMA 路径：
Application → RDMA NIC → Network → Remote Memory
优势：零拷贝，绕过内核，延迟低
```

**实现细节**：

```cpp
// RDMA 访问示例
class PolarFSClient {
    struct RDMAConnection {
        ibv_qp* queue_pair;      // 队列对
        ibv_mr* memory_region;   // 内存区域
        uint64_t remote_addr;    // 远程地址
        uint32_t rkey;           // 远程键
    };
    
    void read_block(uint64_t block_id, void* buffer) {
        // 1. 准备 RDMA Read 操作
        struct ibv_sge sge;
        sge.addr = (uint64_t)buffer;
        sge.length = BLOCK_SIZE;
        sge.lkey = local_mr->lkey;
        
        struct ibv_send_wr wr;
        wr.sg_list = &sge;
        wr.num_sge = 1;
        wr.opcode = IBV_WR_RDMA_READ;
        wr.send_flags = IBV_SEND_SIGNALED;
        wr.wr.rdma.remote_addr = remote_addr + block_id * BLOCK_SIZE;
        wr.wr.rdma.rkey = remote_rkey;
        
        // 2. 提交到 RDMA 队列
        struct ibv_send_wr* bad_wr;
        ibv_post_send(queue_pair, &wr, &bad_wr);
        
        // 3. 等待完成（轮询或事件驱动）
        wait_for_completion();
        
        // 零拷贝，数据直接写入 buffer
    }
};
```

**RDMA 性能分析**：

**延迟对比**：
- **TCP/IP**：100-500μs（内核处理 + 网络延迟）
- **RDMA**：< 10μs（硬件直接访问）

**吞吐对比**：
- **TCP/IP**：受限于 CPU 处理能力
- **RDMA**：接近网络带宽上限（100Gbps+）

**CPU 开销对比**：
- **TCP/IP**：每个数据包需要 CPU 处理
- **RDMA**：CPU 只参与设置，数据传输由硬件完成

**RDMA 的挑战与解决方案**：

1. **内存管理**：
   - **挑战**：需要预先注册内存区域
   - **解决**：使用内存池，预先注册常用内存

2. **错误处理**：
   - **挑战**：RDMA 错误处理复杂
   - **解决**：完善的错误检测和恢复机制

3. **网络分区**：
   - **挑战**：网络分区时 RDMA 连接可能中断
   - **解决**：自动重连和故障转移

## 4. 存储层设计：PolarStore

### 4.1 数据组织

PolarStore 采用 Chunk 作为基本存储单位：

**Chunk 设计**：

- **大小**：64MB 或 128MB
- **多副本**：每个 Chunk 有 3 个副本
- **分布**：Chunk 分布在不同的存储节点上

**数据布局**：

```
Chunk 1 (Primary)     Chunk 2 (Primary)     Chunk 3 (Primary)
    │                      │                      │
    ├── Replica 1          ├── Replica 1          ├── Replica 1
    ├── Replica 2          ├── Replica 2          ├── Replica 2
    └── Replica 3          └── Replica 3          └── Replica 3
```

### 4.2 日志结构存储

PolarStore 采用日志结构存储（Log-Structured Storage）：

**设计原理**：

- **追加写**：所有写入都是追加操作
- **顺序写入**：提高写入性能
- **后台合并**：定期合并和压缩数据

**日志结构 vs 就地更新**：

```
就地更新（传统方式）：
Block 1: [Data A] → Update → [Data A']
问题：随机写入，性能差

日志结构（PolarStore）：
Log: [Data A] → Append → [Data A'] [Data A]
优势：顺序写入，性能好
后台：定期合并，回收空间
```

### 4.3 一致性保证

PolarStore 保证强一致性：

**多副本一致性**：

- **Primary-Replica**：主副本负责写入，副本同步
- **Quorum 写入**：写入需要多数副本确认
- **读取一致性**：读取时检查副本一致性

**一致性协议**：

```
Write Request:
1. Primary 接收写入请求
2. Primary 写入本地日志
3. Primary 同步到 Replicas（Quorum）
4. 等待多数确认
5. 返回成功

Read Request:
1. 从 Primary 或 Replica 读取
2. 检查数据版本
3. 返回最新数据
```

**一致性保证的实现细节**：

**写入流程详细分析**：

```cpp
// PolarStore 写入流程伪代码
class PolarStore {
    struct WriteRequest {
        uint64_t chunk_id;
        uint64_t offset;
        void* data;
        size_t size;
        uint64_t version;  // 版本号
    };
    
    Status Write(const WriteRequest& req) {
        // 1. 选择 Primary Chunk
        Chunk* primary = get_primary_chunk(req.chunk_id);
        
        // 2. 写入 Primary 本地日志
        LogEntry entry;
        entry.version = req.version;
        entry.data = req.data;
        entry.size = req.size;
        primary->append_log(entry);
        
        // 3. 同步到 Replicas（Quorum）
        vector<Chunk*> replicas = get_replicas(req.chunk_id);
        int quorum = (replicas.size() + 1) / 2 + 1;  // 多数派
        int success_count = 1;  // Primary 已写入
        
        for (auto* replica : replicas) {
            if (replica->replicate(entry)) {
                success_count++;
                if (success_count >= quorum) {
                    break;  // 达到 Quorum，可以返回
                }
            }
        }
        
        // 4. 检查是否达到 Quorum
        if (success_count < quorum) {
            return Status::QuorumNotReached();
        }
        
        // 5. 提交到存储
        primary->commit(entry.version);
        
        // 6. 异步通知其他 Replicas 提交
        async_commit_replicas(replicas, entry.version);
        
        return Status::OK();
    }
};
```

**读取一致性保证**：

```cpp
// 读取一致性检查
class PolarStore {
    Status Read(uint64_t chunk_id, uint64_t offset, void* buffer, size_t size) {
        // 1. 选择读取源（Primary 或 Replica）
        Chunk* source = select_read_source(chunk_id);
        
        // 2. 读取数据
        ReadResult result = source->read(offset, size);
        
        // 3. 检查数据版本一致性
        uint64_t expected_version = get_latest_version(chunk_id);
        if (result.version < expected_version) {
            // 数据过期，从 Primary 重新读取
            source = get_primary_chunk(chunk_id);
            result = source->read(offset, size);
        }
        
        // 4. 返回数据
        memcpy(buffer, result.data, size);
        return Status::OK();
    }
};
```

**一致性模型分析**：

**强一致性保证**：

1. **写入一致性**：
   - 所有写入必须达到 Quorum 才返回成功
   - 保证多数副本已持久化数据
   - 即使部分副本故障，数据也不会丢失

2. **读取一致性**：
   - 读取时检查数据版本
   - 如果数据过期，从 Primary 重新读取
   - 保证读取到最新数据

3. **版本管理**：
   - 每个写入操作都有唯一版本号
   - 版本号单调递增
   - 通过版本号判断数据新旧

**一致性 vs 性能权衡**：

- **强一致性**：保证数据一致，但延迟较高（需要 Quorum）
- **最终一致性**：延迟低，但可能读到旧数据
- **PolarDB 选择**：强一致性，因为数据库需要 ACID 保证

## 5. 计算层设计

### 5.1 读写节点

PolarDB 的计算层包含多个节点：

**节点类型**：

- **Primary Node**：主节点，处理所有写入和部分读取
- **Read Replicas**：只读副本，处理读请求

**节点架构**：

```
Primary Node:
┌─────────────────┐
│  SQL Parser     │
│  Query Optimizer│
│  Transaction    │
│  Buffer Pool    │
│  PolarFS Client │
└─────────────────┘

Read Replica:
┌─────────────────┐
│  SQL Parser     │
│  Query Optimizer│
│  Read Only      │
│  Buffer Pool    │
│  PolarFS Client │
└─────────────────┘
```

### 5.2 事务处理

PolarDB 支持完整的 ACID 事务：

**事务流程**：

```
1. Begin Transaction
   └─> 分配事务 ID
   
2. Execute Operations
   └─> 写入 Buffer Pool
   └─> 记录 Redo Log
   
3. Commit
   └─> 刷新 Redo Log 到 PolarFS
   └─> 等待存储确认
   └─> 返回成功
   
4. Rollback (if needed)
   └─> 撤销 Buffer Pool 中的修改
```

**Redo Log 处理**：

- **本地 Buffer**：Redo Log 先写入本地 Buffer
- **批量刷新**：定期批量刷新到 PolarFS
- **同步保证**：Commit 时强制刷新，保证持久性

### 5.3 Buffer Pool 管理

PolarDB 的 Buffer Pool 管理：

**设计特点**：

- **本地缓存**：缓存热点数据，减少远程访问
- **预取策略**：预测性预取，提高命中率
- **淘汰策略**：LRU 或其他策略管理缓存

**Buffer Pool 架构**：

```
Buffer Pool:
┌─────────────┐
│  Hot Pages  │  ← 频繁访问
├─────────────┤
│  Warm Pages │  ← 偶尔访问
├─────────────┤
│  Cold Pages │  ← 很少访问
└─────────────┘
     │
     ▼
  PolarFS
```

## 6. 高可用设计

### 6.1 故障检测与恢复

PolarDB 的高可用机制：

**故障检测**：

- **心跳机制**：计算节点和存储节点定期发送心跳
- **超时检测**：超时未收到心跳，判定为故障
- **快速切换**：检测到故障后，快速切换到备用节点

**故障恢复流程**：

```
1. 故障检测
   └─> 心跳超时
   └─> 判定 Primary 故障
   
2. 选举新 Primary
   └─> 从 Read Replicas 中选择
   └─> 检查数据一致性
   └─> 提升为新 Primary
   
3. 存储层切换
   └─> 更新元数据
   └─> 重新路由请求
   
4. 恢复完成
   └─> RTO < 30s
```

### 6.2 数据一致性保证

故障恢复时的数据一致性：

**一致性检查**：

- **LSN 检查**：检查日志序列号（Log Sequence Number）
- **数据校验**：校验数据完整性
- **回放日志**：回放未提交的日志

**恢复策略**：

```
故障场景 1：Primary 故障
└─> Read Replica 提升为 Primary
└─> 检查 LSN，确保数据最新
└─> 继续服务

故障场景 2：存储节点故障
└─> 使用其他副本
└─> 后台重建故障副本
└─> 保证多副本一致性
```

## 7. 性能优化

### 7.1 写入优化

PolarDB 的写入优化策略：

**批量写入**：

- **日志合并**：合并多个小事务的日志
- **批量刷新**：批量刷新到 PolarFS
- **异步提交**：异步提交，提高吞吐

**写入流程优化**：

```
传统方式：
Transaction 1 → Flush → Storage
Transaction 2 → Flush → Storage
Transaction 3 → Flush → Storage
问题：每次都要刷新，性能差

优化方式：
Transaction 1 ┐
Transaction 2 ├─> Batch Flush → Storage
Transaction 3 ┘
优势：批量刷新，提高吞吐
```

### 7.2 读取优化

PolarDB 的读取优化策略：

**缓存策略**：

- **多级缓存**：本地 Buffer Pool + 存储层缓存
- **预取策略**：预测性预取，减少延迟
- **并行读取**：并行读取多个 Chunk

**读取优化**：

```
读取请求：
1. 检查本地 Buffer Pool
   └─> 命中：直接返回
   
2. 未命中：从 PolarFS 读取
   └─> 并行读取多个 Chunk
   └─> 预取相邻数据
   └─> 更新 Buffer Pool
   
3. 返回数据
```

### 7.3 网络优化

PolarDB 的网络优化：

**RDMA 优化**：

- **零拷贝**：直接内存访问，减少拷贝
- **批量操作**：批量 RDMA 操作，提高效率
- **连接池**：复用 RDMA 连接，减少开销

## 8. 弹性扩展

### 8.1 计算节点扩展

PolarDB 支持计算节点的弹性扩展：

**扩展流程**：

```
1. 创建新的计算节点
   └─> 启动 PolarDB 实例
   └─> 连接到 PolarFS
   
2. 同步元数据
   └─> 同步 Schema
   └─> 同步事务状态
   
3. 加入集群
   └─> 注册为 Read Replica
   └─> 开始服务读请求
   
4. 扩展完成
   └─> 新节点可以处理请求
```

### 8.2 存储容量扩展

PolarDB 支持存储容量的弹性扩展：

**扩展机制**：

- **动态添加 Chunk**：添加新的 Chunk 到存储集群
- **数据重分布**：后台重分布数据，平衡负载
- **在线扩展**：扩展过程中不影响服务

**扩展流程**：

```
1. 添加存储节点
   └─> 新节点加入集群
   
2. 创建新 Chunk
   └─> 在新节点上创建 Chunk
   └─> 设置多副本
   
3. 数据迁移（可选）
   └─> 后台迁移数据
   └─> 平衡负载
   
4. 扩展完成
   └─> 存储容量增加
```

## 9. 兼容性与生态

### 9.1 MySQL/PostgreSQL 兼容

PolarDB 兼容 MySQL 和 PostgreSQL：

**兼容性保证**：

- **协议兼容**：支持 MySQL/PostgreSQL 协议
- **SQL 兼容**：支持标准 SQL 和扩展语法
- **工具兼容**：兼容现有数据库工具

**迁移优势**：

- **零代码修改**：现有应用无需修改代码
- **平滑迁移**：支持在线迁移
- **工具支持**：兼容现有数据库工具链

### 9.2 云原生特性

PolarDB 的云原生特性：

- **按需付费**：根据实际使用量付费
- **自动运维**：自动备份、监控、告警
- **多租户**：支持多租户隔离
- **API 集成**：提供丰富的 API 接口

## 10. 工程实践与经验

### 10.1 性能调优

PolarDB 的性能调优经验：

**关键参数**：

- **Buffer Pool 大小**：根据内存容量调整
- **并发连接数**：根据负载调整
- **网络带宽**：确保足够的网络带宽

**调优建议**：

1. **Buffer Pool**：设置足够大的 Buffer Pool，提高缓存命中率
2. **网络**：使用高速网络（RDMA），减少延迟
3. **并发**：合理设置并发连接数，避免资源竞争

### 10.2 故障处理

PolarDB 的故障处理经验：

**常见故障**：

- **网络分区**：使用 Quorum 机制保证一致性
- **节点故障**：快速切换，保证服务可用
- **数据损坏**：使用多副本恢复数据

**故障预防**：

- **监控告警**：实时监控系统状态
- **定期演练**：定期进行故障演练
- **自动化恢复**：自动化故障恢复流程

## 11. PolarDB 的影响与意义

### 11.1 对云数据库的影响

PolarDB 的设计影响了云数据库的发展：

**设计模式**：

- **存储计算分离**：成为云数据库的标准架构
- **RDMA 网络**：高性能网络在数据库中的应用
- **日志结构存储**：优化写入性能

**行业影响**：

- **AWS Aurora**：类似的存储计算分离架构
- **Azure Database**：采用类似的设计理念
- **其他云数据库**：参考 PolarDB 的设计

### 11.2 技术贡献

PolarDB 的技术贡献：

1. **存储计算分离架构**：证明了在云环境下的可行性
2. **RDMA 优化**：展示了 RDMA 在数据库中的应用
3. **高可用设计**：实现了快速故障恢复
4. **弹性扩展**：实现了计算和存储的独立扩展

## 12. 性能基准测试

### 12.1 性能指标

PolarDB 的性能指标：

**延迟指标**：
- **写入延迟**：P99 < 1ms（本地 Buffer Pool）
- **读取延迟**：P99 < 1ms（缓存命中）
- **网络延迟**：RDMA < 10μs

**吞吐指标**：
- **写入吞吐**：单节点 100K+ TPS
- **读取吞吐**：单节点 500K+ QPS
- **网络吞吐**：100Gbps+

**可用性指标**：
- **RTO**：< 30s（故障恢复时间）
- **RPO**：< 1s（数据恢复点）
- **可用性**：99.99%+

### 12.2 性能对比

PolarDB vs 传统数据库：

| 指标 | 传统数据库 | PolarDB |
|------|-----------|---------|
| 扩展性 | 计算存储耦合 | 计算存储分离 |
| 写入延迟 | 1-5ms | < 1ms |
| 读取延迟 | 0.5-2ms | < 1ms |
| 故障恢复 | 分钟级 | 秒级 |
| 成本 | 固定成本 | 按需付费 |

### 12.3 性能优化实践

**写入性能优化**：

1. **批量写入**：
   - 合并多个小事务
   - 减少网络往返
   - 提高吞吐

2. **异步刷新**：
   - 日志异步刷新到存储
   - 减少写入延迟
   - 提高响应速度

3. **本地缓存**：
   - Buffer Pool 缓存热点数据
   - 减少远程访问
   - 提高命中率

**读取性能优化**：

1. **多级缓存**：
   - 本地 Buffer Pool
   - 存储层缓存
   - 提高缓存命中率

2. **预取策略**：
   - 预测性预取
   - 减少延迟
   - 提高吞吐

3. **并行读取**：
   - 并行读取多个 Chunk
   - 充分利用网络带宽
   - 提高读取速度

## 13. 工程实践与经验

### 13.1 部署实践

PolarDB 的部署实践：

**计算节点部署**：

1. **节点配置**：
   - CPU：16+ 核心
   - 内存：64GB+
   - 网络：25Gbps+（支持 RDMA）

2. **节点数量**：
   - Primary：1 个
   - Read Replicas：2-5 个（根据读负载）

3. **负载均衡**：
   - 读请求分发到多个 Replicas
   - 写请求只到 Primary
   - 动态调整负载

**存储节点部署**：

1. **节点配置**：
   - 存储：10TB+ SSD
   - 网络：25Gbps+（支持 RDMA）
   - 内存：32GB+（用于缓存）

2. **副本配置**：
   - 每个 Chunk 3 个副本
   - 副本分布在不同机架
   - 保证容错能力

### 13.2 监控与运维

PolarDB 的监控指标：

**关键指标**：

1. **性能指标**：
   - QPS/TPS
   - 延迟分布（P50/P99/P999）
   - 吞吐量

2. **资源指标**：
   - CPU 使用率
   - 内存使用率
   - 网络带宽
   - 磁盘 I/O

3. **可用性指标**：
   - 故障次数
   - 故障恢复时间
   - 数据一致性

**告警策略**：

- **延迟告警**：P99 延迟 > 阈值
- **错误率告警**：错误率 > 阈值
- **资源告警**：资源使用率 > 阈值
- **故障告警**：节点故障或网络分区

### 13.3 故障处理经验

**常见故障及处理**：

1. **计算节点故障**：
   - **现象**：节点无响应，心跳超时
   - **处理**：自动切换到 Read Replica
   - **时间**：< 30s

2. **存储节点故障**：
   - **现象**：Chunk 副本不可用
   - **处理**：使用其他副本，后台重建
   - **时间**：立即切换，重建时间取决于数据量

3. **网络分区**：
   - **现象**：节点间无法通信
   - **处理**：使用 Quorum 机制保证一致性
   - **时间**：自动处理，无需人工干预

## 14. 与其他系统的对比

### 14.1 PolarDB vs AWS Aurora

**相似点**：
- 存储计算分离架构
- 多副本存储
- 快速故障恢复

**差异点**：

| 特性 | PolarDB | AWS Aurora |
|------|---------|------------|
| 网络 | RDMA | 传统网络 |
| 延迟 | < 1ms | 1-2ms |
| 存储 | 日志结构 | 日志结构 |
| 兼容性 | MySQL/PostgreSQL | MySQL/PostgreSQL |

### 14.2 PolarDB vs 传统数据库

**优势**：
- 弹性扩展
- 高可用性
- 成本优化

**适用场景**：
- 云原生应用
- 大规模数据
- 高可用要求

## 15. 小结

PolarDB 是云原生数据库的典型代表，通过存储计算分离架构实现了高性能、高可用和弹性扩展。

**核心要点**：

- **存储计算分离**：计算节点和存储集群解耦，独立扩展
- **PolarFS**：基于 RDMA 的分布式文件系统，提供低延迟访问（< 10μs）
- **PolarStore**：日志结构存储，优化写入性能，多副本保证高可用
- **高可用**：快速故障恢复，RTO < 30s，RPO < 1s
- **弹性扩展**：计算和存储独立扩展，按需付费
- **兼容性**：兼容 MySQL/PostgreSQL，便于迁移
- **性能**：低延迟（< 1ms），高吞吐（100K+ TPS）

**技术贡献**：

1. **存储计算分离架构**：证明了在云环境下的可行性
2. **RDMA 优化**：展示了 RDMA 在数据库中的应用，实现 < 10μs 网络延迟
3. **高可用设计**：实现了快速故障恢复，RTO < 30s
4. **弹性扩展**：实现了计算和存储的独立扩展

PolarDB 的设计展示了云原生数据库的发展方向，为后续的云数据库系统提供了重要参考。其存储计算分离架构、RDMA 网络优化、日志结构存储等技术已成为云数据库的标准设计模式。
