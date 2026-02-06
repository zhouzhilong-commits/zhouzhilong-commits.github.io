---
layout: single
title: "IndexLib（4）：查询流程：TabletReader 与 IndexReader"
series: indexlib
permalink: /indexlib-4-query-flow/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-06-11
---

在上一篇文章中，我们深入了解了索引构建的完整流程。本文将继续深入，详细解析查询流程的实现，这是理解 IndexLib 如何从索引中查询数据的关键。

**查询流程图**：

```mermaid
flowchart TD
    Start[接收JSON查询请求] --> ParseGroup
    
    subgraph ParseGroup["1. 查询解析层：解析查询请求"]
        direction TB
        P1[接收JSON查询]
        P2[解析JSON格式]
        P3[提取查询类型<br/>TermQuery/RangeQuery/BooleanQuery]
        P4[提取查询条件<br/>字段名/字段值/范围]
        P5[创建Query对象<br/>内部查询对象]
        P1 --> P2
        P2 --> P3
        P3 --> P4
        P4 --> P5
    end
    
    ParseGroup --> PrepareGroup
    
    subgraph PrepareGroup["2. 索引准备层：准备查询资源"]
        direction TB
        PR1[获取TabletReader<br/>从Tablet获取Reader实例]
        PR2[获取IndexReader<br/>根据索引类型和名称获取]
        PR3[遍历Segment列表<br/>获取所有ST_BUILT状态的Segment]
        PR4[准备QueryContext<br/>查询上下文和参数]
        PR1 --> PR2
        PR2 --> PR3
        PR3 --> PR4
    end
    
    PrepareGroup --> QueryGroup
    
    subgraph QueryGroup["3. 并行查询层：多Segment并行查询"]
        direction TB
        Q1[启动并行查询<br/>多线程并行执行]
        Q2[Segment1查询<br/>使用LocalDocId]
        Q3[Segment2查询<br/>使用LocalDocId]
        Q4[SegmentN查询<br/>使用LocalDocId]
        Q5[倒排索引查询<br/>InvertedIndexReader.Search]
        Q6[正排索引查询<br/>AttributeIndexReader.Read]
        Q7[主键索引查询<br/>PrimaryKeyIndexReader.Lookup]
        Q8[收集各Segment结果<br/>包含LocalDocId和分数]
        Q1 --> Q2
        Q1 --> Q3
        Q1 --> Q4
        Q2 --> Q5
        Q2 --> Q6
        Q2 --> Q7
        Q3 --> Q5
        Q3 --> Q6
        Q3 --> Q7
        Q4 --> Q5
        Q4 --> Q6
        Q4 --> Q7
        Q5 --> Q8
        Q6 --> Q8
        Q7 --> Q8
    end
    
    QueryGroup --> ProcessGroup
    
    subgraph ProcessGroup["4. 结果处理层：合并和处理结果"]
        direction TB
        PS1[合并各Segment结果<br/>收集所有查询结果]
        PS2[DocId转换<br/>LocalDocId转GlobalDocId]
        PS3[DocId去重<br/>去除重复的DocId]
        PS4[按相关性排序<br/>按分数或指定字段排序]
        PS5[分页处理<br/>offset和limit截取]
        PS1 --> PS2
        PS2 --> PS3
        PS3 --> PS4
        PS4 --> PS5
    end
    
    ProcessGroup --> ReturnGroup
    
    subgraph ReturnGroup["5. 结果返回层：序列化和返回"]
        direction TB
        R1[序列化为JSON<br/>转换为JSON格式]
        R2[返回查询结果<br/>包含文档列表和总数]
    end
    
    ReturnGroup --> End[查询完成]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style ParseGroup fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style P1 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style P2 fill:#90caf9,stroke:#1976d2,stroke-width:2px
    style P3 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style P4 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style P5 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style PrepareGroup fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style PR1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style PR2 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style PR3 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style PR4 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style QueryGroup fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Q1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style Q2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style Q3 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style Q4 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style Q5 fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style Q6 fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style Q7 fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style Q8 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style ProcessGroup fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style PS1 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style PS2 fill:#ce93d8,stroke:#7b1fa2,stroke-width:2px
    style PS3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style PS4 fill:#ce93d8,stroke:#7b1fa2,stroke-width:2px
    style PS5 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style ReturnGroup fill:#fce4ec,stroke:#ef4444,stroke-width:2px
    style R1 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style R2 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style End fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
```

## 1. 查询流程概览

### 1.1 整体流程

IndexLib 的查询流程包括以下核心步骤：

1. **解析查询**：将 JSON 格式的查询解析为内部查询对象
2. **获取 IndexReader**：根据索引类型和名称获取或创建 IndexReader
3. **遍历 Segment**：遍历所有已构建的 Segment
4. **并行查询**：对多个 Segment 进行并行查询
5. **合并结果**：将各 Segment 的查询结果合并（去重、排序等）
6. **返回结果**：序列化为 JSON 格式返回

让我们先通过图来理解整个流程：

**组件交互序列图**：

```mermaid
sequenceDiagram
    participant Client
    participant TabletReader
    participant IndexReader
    participant Segment1
    participant Segment2
    participant Segment3
    
    Client->>TabletReader: JSON 查询
    TabletReader->>TabletReader: 解析查询
    TabletReader->>IndexReader: 获取 IndexReader
    IndexReader->>Segment1: 并行查询
    IndexReader->>Segment2: 并行查询
    IndexReader->>Segment3: 并行查询
    Segment1-->>IndexReader: 查询结果1
    Segment2-->>IndexReader: 查询结果2
    Segment3-->>IndexReader: 查询结果3
    IndexReader->>IndexReader: 合并结果
    IndexReader-->>TabletReader: 合并后的结果
    TabletReader->>TabletReader: 序列化为 JSON
    TabletReader-->>Client: 返回 JSON 结果
```

### 1.2 核心接口

查询的核心接口定义在 `framework/ITabletReader.h` 中：

```cpp
// framework/ITabletReader.h
class ITabletReader
{
public:
    // 搜索：JSON 格式的查询
    virtual Status Search(const std::string& jsonQuery, std::string& result) const = 0;
    
    // 获取索引 Reader：根据索引类型和名称获取
    virtual std::shared_ptr<index::IIndexReader> GetIndexReader(
        const std::string& indexType,
        const std::string& indexName) const = 0;
    
    // 获取 Schema
    virtual std::shared_ptr<config::ITabletSchema> GetSchema() const = 0;
};
```

**关键设计**：
- **Search**：提供 JSON 格式的查询接口，方便使用
  - **接口抽象**：通过 JSON 格式隐藏底层实现细节，提供统一的查询接口
  - **查询解析**：将 JSON 查询解析为内部查询对象，支持多种查询类型
  - **结果序列化**：将查询结果序列化为 JSON 格式，便于传输和展示
  
- **GetIndexReader**：根据索引类型和名称获取 IndexReader，支持缓存
  - **缓存机制**：通过 `_indexReaderMap` 缓存 IndexReader，避免重复创建
  - **延迟创建**：IndexReader 按需创建，减少初始化开销
  - **线程安全**：缓存操作是线程安全的，支持并发查询
  
- **GetSchema**：获取 Schema，用于查询验证和字段解析
  - **查询验证**：根据 Schema 验证查询条件的有效性
  - **字段解析**：根据 Schema 解析查询字段和返回字段
  - **类型转换**：根据 Schema 进行数据类型转换

## 2. TabletReader：查询入口

### 2.1 TabletReader 的实现

`TabletReader` 是查询的入口，定义在 `framework/TabletReader.h` 中：

```cpp
// framework/TabletReader.h
class TabletReader : public ITabletReader
{
public:
    explicit TabletReader(const std::shared_ptr<config::ITabletSchema>& schema);
    
    // 打开：初始化 TabletData 和读取资源
    Status Open(const std::shared_ptr<TabletData>& tabletData, 
                const framework::ReadResource& readResource);
    
    // 搜索：JSON 格式的查询
    Status Search(const std::string& jsonQuery, std::string& result) const override;
    
    // 获取索引 Reader：根据索引类型和名称获取（带缓存）
    std::shared_ptr<index::IIndexReader> GetIndexReader(
        const std::string& indexType,
        const std::string& indexName) const override;

protected:
    // 子类实现：具体的打开逻辑
    virtual Status DoOpen(const std::shared_ptr<TabletData>& tabletData, 
                          const framework::ReadResource& readResource) = 0;

protected:
    using IndexReaderMapKey = std::pair<std::string, std::string>;  // (indexType, indexName)
    
    std::shared_ptr<config::ITabletSchema> _schema;
    std::map<IndexReaderMapKey, std::shared_ptr<index::IIndexReader>> _indexReaderMap;  // 索引 Reader 缓存
    std::shared_ptr<IIndexMemoryReclaimer> _indexMemoryReclaimer;
};
```

**TabletReader 的关键组件**：

```mermaid
flowchart TD
    Start[TabletReader] --> ComponentGroup
    
    subgraph ComponentGroup["TabletReader 关键组件"]
        direction TB
        C1[TabletReader<br/>查询入口和协调器]
        C2[Schema<br/>ITabletSchema]
        C3[IndexReaderMap<br/>索引Reader缓存]
        C4[TabletData<br/>索引数据容器]
        C5[ReadResource<br/>读取资源管理]
        C1 --> C2
        C1 --> C3
        C1 --> C4
        C1 --> C5
    end
    
    subgraph SchemaGroup["Schema：索引Schema定义"]
        direction TB
        S1[索引字段定义<br/>字段类型和属性]
        S2[索引配置信息<br/>索引类型和参数]
        S3[查询验证<br/>验证查询字段有效性]
        S2 --> S1
        S1 --> S3
    end
    
    subgraph IndexReaderMapGroup["IndexReaderMap：IndexReader缓存"]
        direction TB
        I1[缓存Key<br/>indexType和indexName]
        I2[缓存Value<br/>IIndexReader实例]
        I3[避免重复创建<br/>提高查询性能]
        I1 --> I2
        I2 --> I3
    end
    
    subgraph TabletDataGroup["TabletData：索引数据容器"]
        direction TB
        T1[所有Segment列表<br/>已构建的Segment]
        T2[Version信息<br/>版本号和Locator]
        T3[ResourceMap<br/>资源映射]
        T1 --> T2
        T2 --> T3
    end
    
    subgraph ReadResourceGroup["ReadResource：读取资源管理"]
        direction TB
        R1[内存配额控制<br/>MemoryQuotaController]
        R2[缓存管理<br/>索引数据缓存]
        R3[资源回收<br/>IIndexMemoryReclaimer]
        R1 --> R2
        R2 --> R3
    end
    
    C2 --> SchemaGroup
    C3 --> IndexReaderMapGroup
    C4 --> TabletDataGroup
    C5 --> ReadResourceGroup
    
    SchemaGroup --> Function[组件功能]
    IndexReaderMapGroup --> Function
    TabletDataGroup --> Function
    ReadResourceGroup --> Function
    
    Function --> F1[查询验证和字段解析]
    Function --> F2[高效索引查询]
    Function --> F3[数据访问和遍历]
    Function --> F4[资源管理和优化]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style ComponentLayer fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style ComponentGroup fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style C1 fill:#90caf9,stroke:#1976d2,stroke-width:2px
    style C2 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C3 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C4 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C5 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style SchemaGroup fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style S1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style S2 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style S3 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style IndexReaderMapGroup fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style I1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style I2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style I3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style TabletDataGroup fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style T1 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style T2 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style T3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style ReadResourceGroup fill:#fce4ec,stroke:#ef4444,stroke-width:2px
    style R1 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style R2 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style R3 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style Function fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style F1 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F2 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F3 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F4 fill:#e0e0e0,stroke:#757575,stroke-width:1px
```

- **Schema**：索引的 Schema 定义，用于查询验证和字段解析
- **IndexReaderMap**：IndexReader 的缓存，避免重复创建
- **TabletData**：索引数据，包含所有 Segment
- **ReadResource**：读取资源（内存配额、缓存等）

### 2.2 TabletReader::Open()

`Open()` 方法初始化 TabletReader，准备查询：

**Open 流程**：

TabletReader 的 Open 流程是查询准备的关键步骤。让我们通过序列图来理解完整的 Open 流程：

```mermaid
sequenceDiagram
    participant Client
    participant TabletReader
    participant TabletData
    participant ReadResource
    participant NormalTabletReader
    participant IndexReader
    
    Client->>TabletReader: Open(TabletData, ReadResource)
    TabletReader->>TabletReader: 保存TabletData引用
    TabletReader->>TabletReader: 保存ReadResource引用
    TabletReader->>NormalTabletReader: DoOpen(TabletData, ReadResource)
    
    NormalTabletReader->>TabletData: CreateSlice(ST_BUILT)
    TabletData-->>NormalTabletReader: Segments
    
    NormalTabletReader->>IndexReader: CreateMultiFieldIndexReader()
    NormalTabletReader->>IndexReader: CreateDeletionMapReader()
    NormalTabletReader->>IndexReader: CreatePrimaryKeyReader()
    NormalTabletReader->>IndexReader: CreateSummaryReader()
    
    IndexReader-->>NormalTabletReader: Success
    NormalTabletReader-->>TabletReader: Success
    TabletReader-->>Client: Success
```

**Open 流程详解**：

1. **设置 TabletData**：保存 TabletData 的引用
   - **数据访问**：通过 TabletData 访问所有 Segment
   - **版本管理**：通过 TabletData 获取当前版本信息
   - **资源管理**：通过 TabletData 访问共享资源
   
2. **设置 ReadResource**：保存读取资源（内存配额、缓存等）
   - **内存配额**：设置查询的内存配额，避免内存溢出
   - **缓存资源**：设置查询缓存，提高查询性能
   - **IO 资源**：设置 IO 资源，控制 IO 并发度
   
3. **调用 DoOpen()**：子类实现具体的打开逻辑
   - **NormalTabletReader**：创建各种 IndexReader（倒排、正排、主键等）
   - **KKVTabletReader**：创建 KKV 特定的 IndexReader
   - **KVTabletReader**：创建 KV 特定的 IndexReader
   
4. **初始化 IndexReader**：根据需要初始化 IndexReader
   - **延迟初始化**：IndexReader 按需初始化，减少启动时间
   - **缓存管理**：将 IndexReader 缓存到 `_indexReaderMap`
   - **资源分配**：为 IndexReader 分配必要的资源

### 2.3 TabletReader::Search()

`Search()` 方法是查询的入口，将 JSON 查询转换为结果：

**Search 流程**：

Search 方法是查询的核心，负责将 JSON 查询转换为结果。让我们通过详细的序列图来理解完整的查询流程：

```mermaid
sequenceDiagram
    participant Client
    participant TabletReader
    participant QueryParser
    participant IndexReader
    participant Segment1
    participant Segment2
    participant Segment3
    participant ResultMerger
    
    Client->>TabletReader: Search(jsonQuery)
    TabletReader->>QueryParser: ParseQuery(jsonQuery)
    QueryParser->>QueryParser: 提取查询类型
    QueryParser->>QueryParser: 提取查询条件
    QueryParser-->>TabletReader: Query对象
    
    TabletReader->>IndexReader: GetIndexReader(indexType, indexName)
    IndexReader-->>TabletReader: IndexReader
    
    TabletReader->>TabletReader: CreateSlice(ST_BUILT)
    TabletReader->>Segment1: Search(query)
    TabletReader->>Segment2: Search(query)
    TabletReader->>Segment3: Search(query)
    
    Segment1-->>TabletReader: Result1
    Segment2-->>TabletReader: Result2
    Segment3-->>TabletReader: Result3
    
    TabletReader->>ResultMerger: MergeResults([Result1, Result2, Result3])
    ResultMerger->>ResultMerger: 去重
    ResultMerger->>ResultMerger: 排序
    ResultMerger->>ResultMerger: 分页
    ResultMerger-->>TabletReader: MergedResult
    
    TabletReader->>TabletReader: SerializeToJson(MergedResult)
    TabletReader-->>Client: jsonResult
```

**Search 流程详解**：

1. **解析查询**：将 JSON 查询解析为内部查询对象
   - **JSON 解析**：解析 JSON 格式的查询字符串
   - **查询类型识别**：识别查询类型（term 查询、范围查询、布尔查询等）
   - **查询条件提取**：提取查询条件（term、范围、排序字段等）
   - **查询对象创建**：创建内部查询对象，便于后续处理
   
2. **获取 IndexReader**：根据索引类型和名称获取 IndexReader
   - **缓存查找**：首先从 `_indexReaderMap` 查找缓存的 IndexReader
   - **创建 IndexReader**：如果缓存不存在，创建新的 IndexReader
   - **缓存 IndexReader**：将新创建的 IndexReader 缓存起来
   
3. **遍历 Segment**：通过 `TabletData->CreateSlice(ST_BUILT)` 获取所有已构建的 Segment
   - **Segment 筛选**：只查询已构建的 Segment，跳过构建中的 Segment
   - **Segment 排序**：按照 SegmentId 排序，保证查询顺序
   - **Segment 过滤**：可以根据 Locator 等条件过滤 Segment
   
4. **并行查询**：对多个 Segment 进行并行查询
   - **并行执行**：多个 Segment 的查询可以并行执行
   - **结果收集**：收集各 Segment 的查询结果
   - **错误处理**：单个 Segment 查询失败不影响其他 Segment
   
5. **合并结果**：将各 Segment 的查询结果合并（去重、排序等）
   - **去重处理**：根据 DocId 去重，避免重复文档
   - **排序处理**：按相关性分数或指定字段排序
   - **分页处理**：返回指定页的结果，支持分页查询
   - **聚合统计**：计算总数、平均值等统计信息
   
6. **返回结果**：序列化为 JSON 格式返回
   - **结果序列化**：将查询结果序列化为 JSON 格式
   - **字段选择**：根据查询条件选择返回的字段
   - **格式优化**：优化 JSON 格式，减少传输大小

### 2.4 IndexReader 缓存机制

`TabletReader` 维护 IndexReader 的缓存，避免重复创建：

**缓存机制**：

IndexReader 缓存是 TabletReader 性能优化的关键设计。让我们通过流程图来理解缓存机制的工作原理：

```mermaid
flowchart TD
    Start[GetIndexReader请求] --> CheckCache{检查缓存<br/>IndexReaderMap中查找}
    
    CheckCache -->|缓存命中| ReturnCached[返回缓存的IndexReader<br/>直接返回shared_ptr]
    CheckCache -->|缓存未命中| CreateNew[创建新的IndexReader]
    
    subgraph CreateGroup["创建IndexReader流程"]
        direction TB
        C1[根据indexType创建<br/>InvertedIndexReader/AttributeIndexReader等]
        C2[初始化IndexReader<br/>设置Schema和配置]
        C3[加载索引数据<br/>从Segment加载索引文件]
        C4[缓存IndexReader<br/>存入IndexReaderMap]
        C5[返回IndexReader<br/>返回shared_ptr]
        C1 --> C2
        C2 --> C3
        C3 --> C4
        C4 --> C5
    end
    
    CreateNew --> CreateGroup
    
    CreateGroup --> End1[IndexReader就绪]
    ReturnCached --> End1
    
    End1 --> UseIndexReader[使用IndexReader查询]
    
    subgraph UpdateGroup["IndexReader更新机制"]
        direction TB
        U1[检查是否需要更新<br/>Schema变更/Version变更]
        U2{是否需要更新?}
        U3[更新缓存<br/>创建新的IndexReader]
        U4[替换旧缓存<br/>更新IndexReaderMap]
        U5[继续使用<br/>复用现有IndexReader]
        U1 --> U2
        U2 -->|是| U3
        U2 -->|否| U5
        U3 --> U4
        U4 --> U6[更新完成]
        U5 --> U6
    end
    
    UseIndexReader --> UpdateGroup
    
    subgraph CacheInfo["缓存机制特点"]
        direction TB
        CI1[缓存Key<br/>indexType和indexName对]
        CI2[缓存Value<br/>shared_ptr IIndexReader]
        CI3[性能优势<br/>避免重复创建<br/>提高查询性能]
        CI1 --> CI2
        CI2 --> CI3
    end
    
    UpdateGroup -.-> CacheInfo
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style CheckCache fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style ReturnCached fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style CreateNew fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style CreateGroup fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style C1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style C2 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style C3 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style C4 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style C5 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style End1 fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style UseIndexReader fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style UpdateGroup fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style U1 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style U2 fill:#ce93d8,stroke:#7b1fa2,stroke-width:2px
    style U3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style U4 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style U5 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style U6 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style CacheInfo fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style CI1 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style CI2 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style CI3 fill:#e0e0e0,stroke:#757575,stroke-width:1px
```

**缓存机制详解**：

- **缓存 Key**：`(indexType, indexName)` 对
  - **唯一性**：每个索引类型和名称的组合唯一标识一个 IndexReader
  - **查找效率**：使用 `std::map` 或 `std::unordered_map` 实现 O(log n) 或 O(1) 查找
  - **Key 设计**：使用 `std::pair` 作为 Key，支持多级索引
  
- **缓存 Value**：`IIndexReader` 指针
  - **生命周期**：IndexReader 的生命周期与 TabletReader 相同
  - **共享使用**：多个查询可以共享同一个 IndexReader
  - **内存管理**：通过 `shared_ptr` 管理内存，自动释放
  
- **优势**：避免重复创建 IndexReader，提高查询性能
  - **性能提升**：避免重复创建和初始化 IndexReader，显著提升查询性能
  - **内存优化**：多个查询共享 IndexReader，减少内存占用
  - **启动优化**：延迟创建 IndexReader，减少启动时间

**缓存策略**：

1. **LRU 策略**：
   - 当缓存满时，淘汰最近最少使用的 IndexReader
   - 适合内存受限的场景
   
2. **FIFO 策略**：
   - 当缓存满时，淘汰最早创建的 IndexReader
   - 实现简单，但可能淘汰常用 IndexReader
   
3. **无限制策略**：
   - 不限制缓存大小，所有 IndexReader 都缓存
   - 适合内存充足的场景，性能最好

**缓存实现**：

```cpp
// framework/TabletReader.h
std::shared_ptr<index::IIndexReader> TabletReader::GetIndexReader(
    const std::string& indexType,
    const std::string& indexName) const
{
    IndexReaderMapKey key = std::make_pair(indexType, indexName);
    auto it = _indexReaderMap.find(key);
    if (it != _indexReaderMap.end()) {
        return it->second;  // 返回缓存的 IndexReader
    }
    
    // 创建新的 IndexReader（子类实现）
    auto reader = DoGetIndexReader(indexType, indexName);
    if (reader) {
        _indexReaderMap[key] = reader;  // 缓存
    }
    return reader;
}
```

## 3. IndexReader：索引查询接口

### 3.1 IIndexReader 接口

`IIndexReader` 是索引查询的抽象接口，定义在 `index/IIndexReader.h` 中：

```cpp
// index/IIndexReader.h
class IIndexReader
{
public:
    virtual ~IIndexReader() = default;
    
    // 打开：初始化 IndexReader
    virtual Status Open(const std::shared_ptr<config::IIndexConfig>& indexConfig,
                       const IndexReaderParameter& indexReaderParam) = 0;
    
    // 查询：根据查询条件查询索引
    virtual Status Search(const std::shared_ptr<Query>& query,
                         std::shared_ptr<QueryResult>& result) = 0;
    
    // 获取索引统计信息
    virtual IndexStatistics GetStatistics() const = 0;
};
```

**IIndexReader 的关键方法**：

```mermaid
flowchart TD
    Start[IIndexReader接口] --> OpenGroup
    Start --> SearchGroup
    Start --> StatisticsGroup
    
    subgraph OpenGroup["1. Open方法：初始化IndexReader"]
        direction TB
        O1[Open调用<br/>参数: IndexConfig + IndexReaderParameter]
        O2[初始化IndexReader<br/>设置配置和参数]
        O3[加载索引数据<br/>从Segment加载索引文件到内存]
        O4[准备查询资源<br/>初始化查询所需的数据结构]
        O5[返回Status<br/>初始化成功或失败]
        O1 --> O2
        O2 --> O3
        O3 --> O4
        O4 --> O5
    end
    
    subgraph SearchGroup["2. Search方法：查询索引"]
        direction TB
        S1[Search调用<br/>参数: Query对象]
        S2[解析查询条件<br/>提取查询字段和值]
        S3[查询索引数据<br/>根据查询条件查找匹配的DocId]
        S4[计算相关性分数<br/>根据匹配度计算分数]
        S5[构建QueryResult<br/>包含DocId列表和分数]
        S6[返回Status和QueryResult<br/>查询结果或错误信息]
        S1 --> S2
        S2 --> S3
        S3 --> S4
        S4 --> S5
        S5 --> S6
    end
    
    subgraph StatisticsGroup["3. GetStatistics方法：获取统计信息"]
        direction TB
        ST1[GetStatistics调用<br/>无参数]
        ST2[统计文档数<br/>docCount]
        ST3[统计Term数<br/>termCount]
        ST4[统计索引大小<br/>indexSize]
        ST5[构建IndexStatistics<br/>包含所有统计信息]
        ST6[返回IndexStatistics<br/>统计信息对象]
        ST1 --> ST2
        ST1 --> ST3
        ST1 --> ST4
        ST2 --> ST5
        ST3 --> ST5
        ST4 --> ST5
        ST5 --> ST6
    end
    
    OpenGroup -.->|必须先调用| SearchGroup
    OpenGroup -.->|可以随时调用| StatisticsGroup
    SearchGroup -.->|可以随时调用| StatisticsGroup
    
    subgraph Lifecycle["方法调用生命周期"]
        direction LR
        L1[初始化阶段<br/>Open方法]
        L2[查询阶段<br/>Search方法可多次调用]
        L3[监控阶段<br/>GetStatistics方法]
        L1 --> L2
        L2 --> L3
        L2 --> L2
    end
    
    OpenGroup -.-> Lifecycle
    SearchGroup -.-> Lifecycle
    StatisticsGroup -.-> Lifecycle
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style OpenGroup fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style O1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style O2 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style O3 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style O4 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style O5 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style SearchGroup fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style S1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style S2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style S3 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style S4 fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style S5 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style S6 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style StatisticsGroup fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style ST1 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style ST2 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style ST3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style ST4 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style ST5 fill:#ce93d8,stroke:#7b1fa2,stroke-width:2px
    style ST6 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style Lifecycle fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style L1 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style L2 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style L3 fill:#e0e0e0,stroke:#757575,stroke-width:1px
```

- **Open**：初始化 IndexReader，加载索引数据
- **Search**：根据查询条件查询索引，返回查询结果
- **GetStatistics**：获取索引统计信息（文档数、term 数等）

### 3.2 不同类型的 IndexReader

IndexLib 支持多种类型的 IndexReader：

```mermaid
flowchart TD
    Start[IndexReader类型体系] --> InvertedGroup
    
    subgraph InvertedGroup["1. InvertedIndexReader：倒排索引Reader"]
        direction TB
        I1[实现IIndexReader接口]
        I2[全文检索功能<br/>TermQuery/RangeQuery/BooleanQuery]
        I3[返回匹配的DocId列表<br/>包含相关性分数]
        I1 --> I2
        I2 --> I3
    end
    
    subgraph AttributeGroup["2. AttributeReader：正排索引Reader"]
        direction TB
        A1[实现IIndexReader接口]
        A2[属性查询功能<br/>根据DocId读取属性值]
        A3[支持多种数据类型<br/>int/string/float等]
        A1 --> A2
        A2 --> A3
    end
    
    subgraph PrimaryKeyGroup["3. PrimaryKeyIndexReader：主键索引Reader"]
        direction TB
        P1[实现IIndexReader接口]
        P2[主键查询功能<br/>根据主键查找DocId]
        P3[支持精确匹配<br/>O1时间复杂度]
        P1 --> P2
        P2 --> P3
    end
    
    subgraph SummaryGroup["4. SummaryReader：摘要Reader"]
        direction TB
        S1[实现IIndexReader接口]
        S2[获取文档摘要<br/>根据DocId读取摘要信息]
        S3[支持字段选择<br/>按需读取字段]
        S1 --> S2
        S2 --> S3
    end
    
    subgraph DeletionMapGroup["5. DeletionMapReader：删除映射Reader"]
        direction TB
        D1[实现IIndexReader接口]
        D2[过滤删除文档<br/>检查DocId是否已删除]
        D3[支持删除标记<br/>Tombstone机制]
        D1 --> D2
        D2 --> D3
    end
    
    Start --> AttributeGroup
    Start --> PrimaryKeyGroup
    Start --> SummaryGroup
    Start --> DeletionMapGroup
    
    InvertedGroup --> Usage[使用场景]
    AttributeGroup --> Usage
    PrimaryKeyGroup --> Usage
    SummaryGroup --> Usage
    DeletionMapGroup --> Usage
    
    Usage --> U1[全文搜索场景<br/>InvertedIndexReader]
    Usage --> U2[属性过滤场景<br/>AttributeReader]
    Usage --> U3[主键查找场景<br/>PrimaryKeyIndexReader]
    Usage --> U4[文档展示场景<br/>SummaryReader]
    Usage --> U5[删除过滤场景<br/>DeletionMapReader]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style TypeLayer fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style InvertedGroup fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style I1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style I2 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style I3 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style AttributeGroup fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style A1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style A2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style A3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style PrimaryKeyGroup fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style P1 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style P2 fill:#ce93d8,stroke:#7b1fa2,stroke-width:2px
    style P3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style SummaryGroup fill:#fce4ec,stroke:#ef4444,stroke-width:2px
    style S1 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style S2 fill:#f48fb1,stroke:#ef4444,stroke-width:2px
    style S3 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style DeletionMapGroup fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style D1 fill:#fff59d,stroke:#f57f17,stroke-width:1px
    style D2 fill:#ffcc02,stroke:#f57f17,stroke-width:2px
    style D3 fill:#fff59d,stroke:#f57f17,stroke-width:1px
    style Usage fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style U1 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style U2 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style U3 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style U4 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style U5 fill:#e0e0e0,stroke:#757575,stroke-width:1px
```

**IndexReader 类型**：
- **InvertedIndexReader**：倒排索引 Reader，用于全文检索
- **AttributeReader**：正排索引 Reader，用于属性查询
- **PrimaryKeyIndexReader**：主键索引 Reader，用于主键查询
- **SummaryReader**：摘要 Reader，用于获取文档摘要
- **DeletionMapReader**：删除映射 Reader，用于过滤已删除文档

### 3.3 InvertedIndexReader：倒排索引查询

`InvertedIndexReader` 是倒排索引的查询接口：

```mermaid
flowchart TD
    A[查询请求<br/>Query对象] --> B[解析查询类型<br/>TermQuery/RangeQuery等]
    
    subgraph Parse["查询解析"]
        B1[提取查询Term<br/>分词处理]
        B2[提取查询条件<br/>范围/布尔等]
        B3[创建内部Query对象]
        B --> B1
        B1 --> B2
        B2 --> B3
    end
    
    subgraph Search["索引查找"]
        C1[在倒排索引中查找Term<br/>InvertedIndex]
        C2[获取Term的倒排列表<br/>PostingList]
        C3[DocId列表<br/>包含该Term的文档]
        C4[位置信息<br/>Term在文档中的位置]
        B3 --> C1
        C1 --> C2
        C2 --> C3
        C2 --> C4
    end
    
    subgraph Filter["过滤处理"]
        D1[通过DeletionMap过滤<br/>过滤已删除文档]
        D2[范围查询过滤<br/>如果包含范围条件]
        D3[布尔查询处理<br/>AND/OR/NOT]
        C3 --> D1
        C4 --> D1
        D1 --> D2
        D2 --> D3
    end
    
    subgraph Score["相关性计算"]
        E1[计算相关性分数<br/>TF-IDF/BM25等]
        E2[位置信息加权<br/>短语查询]
        E3[字段权重<br/>不同字段权重不同]
        D3 --> E1
        E1 --> E2
        E2 --> E3
    end
    
    subgraph Result["返回结果"]
        F1[DocId列表<br/>匹配的文档ID]
        F2[相关性分数<br/>排序依据]
        F3[位置信息<br/>用于高亮显示]
        E3 --> F1
        E3 --> F2
        E3 --> F3
    end
    
    style Parse fill:#e3f2fd
    style Search fill:#fff3e0
    style Filter fill:#e8f5e9
    style Score fill:#f3e5f5
    style Result fill:#fce4ec
```

**倒排索引查询流程**：
1. **解析查询**：解析 term 查询、范围查询等
2. **查找 term**：在倒排索引中查找 term
3. **获取倒排列表**：获取 term 对应的倒排列表（DocId 列表）
4. **过滤删除文档**：通过 DeletionMap 过滤已删除文档
5. **返回结果**：返回 DocId 列表和相关性分数

### 3.4 AttributeReader：正排索引查询

`AttributeReader` 是正排索引的查询接口：

```mermaid
flowchart TD
    A[查询请求<br/>GlobalDocId + 属性名] --> B[定位Segment<br/>根据GlobalDocId]
    
    subgraph Locate["定位阶段"]
        B1[遍历TabletData中的Segment]
        B2[计算每个Segment的BaseDocId<br/>累加前面Segment的docCount]
        B3{GlobalDocId在范围内?<br/>BaseDocId <= GlobalDocId < BaseDocId + docCount}
        B4[找到对应Segment]
        B --> B1
        B1 --> B2
        B2 --> B3
        B3 -->|是| B4
        B3 -->|否| B1
    end
    
    subgraph Convert["DocId转换"]
        C1[计算LocalDocId<br/>LocalDocId = GlobalDocId - BaseDocId]
        C2[验证LocalDocId有效性<br/>0 <= LocalDocId < docCount]
        B4 --> C1
        C1 --> C2
    end
    
    subgraph Read["读取属性"]
        D1[根据属性名获取AttributeIndexer<br/>GetAttributeReader]
        D2[定位属性数据位置<br/>根据LocalDocId]
        D3[读取属性值<br/>从磁盘或内存]
        D4[数据类型转换<br/>整数/浮点数/字符串等]
        D5[解压缩<br/>如果使用了压缩]
        C2 --> D1
        D1 --> D2
        D2 --> D3
        D3 --> D4
        D4 --> D5
    end
    
    subgraph Return["返回结果"]
        E1[返回属性值<br/>AttributeValue]
        E2[支持批量读取<br/>多个DocId一次读取]
        D5 --> E1
        E1 --> E2
    end
    
    subgraph Optimize["性能优化"]
        O1[缓存常用属性<br/>减少磁盘IO]
        O2[批量读取<br/>减少IO次数]
        O3[预读机制<br/>预读相邻数据]
        D3 -.-> O1
        D3 -.-> O2
        D3 -.-> O3
    end
    
    style Locate fill:#e3f2fd
    style Convert fill:#fff3e0
    style Read fill:#e8f5e9
    style Return fill:#f3e5f5
    style Optimize fill:#f5f5f5
```

**正排索引查询流程**：
1. **定位 DocId**：根据全局 DocId 定位到对应的 Segment
2. **转换为局部 DocId**：将全局 DocId 转换为局部 DocId
3. **读取属性值**：从正排索引中读取属性值
4. **返回结果**：返回属性值

## 4. 查询流程详解

### 4.1 查询解析

查询解析将 JSON 格式的查询转换为内部查询对象：

```mermaid
flowchart TD
    A[JSON查询字符串<br/>jsonQuery] --> B[解析JSON<br/>JsonParser]
    
    subgraph Parse["JSON解析"]
        B1[解析JSON对象<br/>提取字段]
        B2[验证JSON格式<br/>格式检查]
        B3[提取查询类型字段<br/>queryType]
        B --> B1
        B1 --> B2
        B2 --> B3
    end
    
    subgraph Extract["提取查询信息"]
        C1[提取查询类型<br/>TermQuery/RangeQuery/BoolQuery等]
        C2[提取查询条件<br/>term/范围/排序字段]
        C3[提取排序信息<br/>sortField/sortOrder]
        C4[提取分页信息<br/>offset/limit]
        C5[提取聚合信息<br/>aggregation]
        B3 --> C1
        C1 --> C2
        C1 --> C3
        C1 --> C4
        C1 --> C5
    end
    
    subgraph Create["创建查询对象"]
        D1[创建TermQuery对象<br/>term查询]
        D2[创建RangeQuery对象<br/>范围查询]
        D3[创建BoolQuery对象<br/>布尔查询]
        D4[创建Query对象<br/>组合查询]
        C2 --> D1
        C2 --> D2
        C2 --> D3
        D1 --> D4
        D2 --> D4
        D3 --> D4
    end
    
    subgraph Validate["验证查询"]
        E1[Schema验证<br/>字段是否存在]
        E2[类型验证<br/>字段类型匹配]
        E3[范围验证<br/>查询条件有效性]
        D4 --> E1
        E1 --> E2
        E2 --> E3
    end
    
    subgraph Result["查询对象"]
        F1[内部Query对象<br/>用于后续查询]
        F2[包含所有查询信息<br/>类型/条件/排序等]
        E3 --> F1
        F1 --> F2
    end
    
    style Parse fill:#e3f2fd
    style Extract fill:#fff3e0
    style Create fill:#e8f5e9
    style Validate fill:#f3e5f5
    style Result fill:#fce4ec
```

**查询解析流程**：
1. **解析 JSON**：解析 JSON 格式的查询字符串
2. **提取查询类型**：提取查询类型（term 查询、范围查询等）
3. **提取查询条件**：提取查询条件（term、范围等）
4. **创建查询对象**：创建内部查询对象

### 4.2 多 Segment 并行查询

查询时需要遍历多个 Segment，可以并行查询以提高性能：

```mermaid
flowchart TD
    A[查询请求<br/>Query对象] --> B[TabletData.CreateSlice<br/>ST_BUILT获取Segment列表]
    
    subgraph Segments["Segment列表"]
        S1[Segment1<br/>docCount=1000<br/>BaseDocId=0]
        S2[Segment2<br/>docCount=2000<br/>BaseDocId=1000]
        S3[Segment3<br/>docCount=1500<br/>BaseDocId=3000]
        B --> S1
        B --> S2
        B --> S3
    end
    
    subgraph Parallel["并行查询执行"]
        P1[Segment1查询<br/>IndexReader.Search]
        P2[Segment2查询<br/>IndexReader.Search]
        P3[Segment3查询<br/>IndexReader.Search]
        P4[线程池执行<br/>并发查询]
        P5[收集查询结果<br/>Result1, Result2, Result3]
        P6[错误处理<br/>单个Segment失败不影响其他]
        
        S1 --> P1
        S2 --> P2
        S3 --> P3
        P1 --> P4
        P2 --> P4
        P3 --> P4
        P4 --> P5
        P5 --> P6
    end
    
    subgraph Merge["结果合并"]
        M1[DocId去重<br/>避免重复文档]
        M2[按相关性分数排序<br/>或按指定字段排序]
        M3[分页处理<br/>offset/limit]
        M4[聚合统计<br/>总数/平均值等]
        P6 --> M1
        M1 --> M2
        M2 --> M3
        M3 --> M4
    end
    
    subgraph Performance["性能优化"]
        PF1[并行度控制<br/>线程池大小配置]
        PF2[结果流式合并<br/>边查询边合并]
        PF3[索引剪枝<br/>跳过不相关Segment]
        PF4[Locator剪枝<br/>判断Segment是否包含结果]
        
        P4 -.-> PF1
        M1 -.-> PF2
        B -.-> PF3
        B -.-> PF4
    end
    
    M4 --> R[返回合并结果<br/>QueryResult]
    
    style Segments fill:#e3f2fd
    style Parallel fill:#fff3e0
    style Merge fill:#f3e5f5
    style Performance fill:#f5f5f5
    style R fill:#e8f5e9
```

**并行查询流程**：
1. **获取 Segment 列表**：`TabletData->CreateSlice(ST_BUILT)` 获取所有已构建的 Segment
2. **并行查询**：对每个 Segment 的 Indexer 进行查询（如果支持并行）
3. **合并结果**：将各 Segment 的查询结果合并（去重、排序等）

### 4.3 DocId 转换

查询时需要将全局 DocId 转换为局部 DocId：

```mermaid
flowchart TD
    A[查询请求<br/>GlobalDocId] --> B[TabletData.GetSegment<br/>遍历Segment列表]
    
    subgraph Locate["定位Segment"]
        L1[遍历所有Segment<br/>按顺序查找]
        L2[计算每个Segment的BaseDocId<br/>累加前面Segment的docCount]
        L3{GlobalDocId在范围内?<br/>BaseDocId <= GlobalDocId < BaseDocId + docCount}
        L4[找到对应Segment]
        L5[继续遍历下一个Segment]
        
        B --> L1
        L1 --> L2
        L2 --> L3
        L3 -->|是| L4
        L3 -->|否| L5
        L5 --> L1
    end
    
    subgraph Convert["DocId转换"]
        C1[获取Segment的BaseDocId<br/>前面所有Segment的docCount之和]
        C2[计算LocalDocId<br/>LocalDocId = GlobalDocId - BaseDocId]
        C3[验证LocalDocId有效性<br/>0 <= LocalDocId < docCount]
        C4[验证失败处理<br/>返回错误]
        L4 --> C1
        C1 --> C2
        C2 --> C3
        C3 -->|无效| C4
    end
    
    subgraph Query["Segment内查询"]
        Q1[使用LocalDocId查询<br/>IndexReader.Get]
        Q2[倒排索引查询<br/>InvertedIndexer]
        Q3[正排索引查询<br/>AttributeIndexer]
        Q4[主键索引查询<br/>PrimaryKeyIndexer]
        Q5[返回文档数据<br/>Document]
        C3 -->|有效| Q1
        Q1 --> Q2
        Q1 --> Q3
        Q1 --> Q4
        Q2 --> Q5
        Q3 --> Q5
        Q4 --> Q5
    end
    
    subgraph Example["转换示例"]
        E1[GlobalDocId = 1500]
        E2[Segment1: BaseDocId=0, docCount=1000<br/>范围: 0-999, 不在范围内]
        E3[Segment2: BaseDocId=1000, docCount=2000<br/>范围: 1000-2999, 在范围内]
        E4[LocalDocId = 1500 - 1000 = 500]
        E5[在Segment2内使用LocalDocId=500查询]
        
        E1 --> E2
        E2 --> E3
        E3 --> E4
        E4 --> E5
    end
    
    Q5 --> R[返回查询结果]
    C4 --> R
    
    style Locate fill:#e3f2fd
    style Convert fill:#fff3e0
    style Query fill:#f3e5f5
    style Example fill:#f5f5f5
    style R fill:#e8f5e9
```

**DocId 转换流程**：
1. **定位 Segment**：根据全局 DocId 找到对应的 Segment
2. **计算 BaseDocId**：计算该 Segment 的基础 DocId
3. **转换为局部 DocId**：`localDocId = globalDocId - baseDocId`
4. **Segment 内查询**：使用局部 DocId 在 Segment 内查询

### 4.4 结果合并

查询结果需要合并，包括去重、排序等：

**结果合并流程**：

结果合并是查询流程的关键步骤，需要高效地处理大量查询结果。让我们通过流程图来理解结果合并的详细过程：

```mermaid
flowchart TD
    A["多个Segment的查询结果<br/>Result1, Result2, Result3"] --> B["结果收集<br/>收集所有Segment结果"]
    
    subgraph Collect["结果收集"]
        B1["收集DocId列表<br/>来自各Segment"]
        B2["收集相关性分数<br/>用于排序"]
        B3["收集位置信息<br/>用于高亮"]
        B --> B1
        B --> B2
        B --> B3
    end
    
    subgraph Dedup["去重处理"]
        C1["DocId去重<br/>避免重复文档"]
        C2["去重算法选择<br/>set或unordered_set或双指针"]
        C3["有序结果优化<br/>双指针算法时间复杂度O n"]
        C4["无序结果<br/>hash set时间复杂度O n"]
        B1 --> C1
        C1 --> C2
        C2 -->|有序| C3
        C2 -->|无序| C4
    end
    
    subgraph Sort["排序处理"]
        D1{"是否需要排序?"}
        D2["按相关性分数排序<br/>相关性高的在前"]
        D3["按指定字段排序<br/>时间或数值等"]
        D4["按DocId排序<br/>默认排序"]
        D5["排序算法<br/>堆排序或快速排序"]
        D6["Top-K优化<br/>只对Top-K排序"]
        C3 --> D1
        C4 --> D1
        D1 -->|是| D2
        D1 -->|是| D3
        D1 -->|否| D4
        D2 --> D5
        D3 --> D5
        D5 --> D6
    end
    
    subgraph Page["分页处理"]
        E1["计算分页范围<br/>offset到offset加limit"]
        E2["截取结果<br/>只返回需要的文档"]
        E3["分页缓存<br/>缓存分页结果"]
        D6 --> E1
        D4 --> E1
        E1 --> E2
        E2 --> E3
    end
    
    subgraph Aggregate["聚合统计"]
        F1{"是否需要聚合?"}
        F2["总数统计<br/>匹配文档总数"]
        F3["平均值统计<br/>字段平均值"]
        F4["分组统计<br/>按字段分组"]
        F5["并行计算聚合<br/>减少开销"]
        E3 --> F1
        F1 -->|是| F2
        F1 -->|是| F3
        F1 -->|是| F4
        F2 --> F5
        F3 --> F5
        F4 --> F5
    end
    
    subgraph Optimize["合并优化"]
        O1["堆合并<br/>时间复杂度O n log k适合Top-K"]
        O2["并行合并<br/>充分利用多核CPU"]
        O3["流式合并<br/>边查询边合并"]
        O4["减少内存占用<br/>提高响应速度"]
        C1 -.-> O1
        D5 -.-> O2
        B1 -.-> O3
        O3 -.-> O4
    end
    
    F1 -->|否| G["返回结果<br/>QueryResult"]
    F5 --> G
    
    style Collect fill:#e3f2fd
    style Dedup fill:#fff3e0
    style Sort fill:#e8f5e9
    style Page fill:#f3e5f5
    style Aggregate fill:#fce4ec
    style Optimize fill:#f5f5f5
```

**结果合并流程详解**：

1. **去重**：根据 DocId 去重，避免重复文档
   - **去重算法**：使用 `std::set` 或 `std::unordered_set` 实现 O(n) 去重
   - **去重时机**：在合并前或合并后去重，根据场景选择
   - **去重优化**：对于有序结果，可以使用双指针算法实现 O(n) 去重
   
2. **排序**：按相关性分数排序，返回最相关的文档
   - **排序算法**：使用堆排序或快速排序，时间复杂度 O(n log n)
   - **排序字段**：可以按相关性分数、时间、字段值等排序
   - **排序优化**：只对 Top-K 结果排序，减少排序开销
   
3. **聚合统计**：计算总数、平均值等统计信息
   - **总数统计**：统计匹配的文档总数
   - **平均值统计**：计算字段的平均值
   - **分组统计**：按字段分组统计
   - **聚合优化**：在查询过程中并行计算聚合，减少额外开销
   
4. **分页处理**：返回指定页的结果
   - **分页计算**：根据页码和每页大小计算结果范围
   - **分页优化**：只返回需要的文档，减少传输大小
   - **分页缓存**：缓存分页结果，提高重复查询性能

**结果合并的性能优化**：

1. **堆合并**：
   - 使用堆合并多个有序结果列表
   - 时间复杂度 O(n log k)，k 为结果列表数量
   - 适合 Top-K 查询场景
   
2. **并行合并**：
   - 多个结果列表可以并行合并
   - 充分利用多核 CPU，提高合并速度
   - 适合大量结果合并场景
   
3. **流式合并**：
   - 边查询边合并，不需要等待所有结果
   - 减少内存占用，提高响应速度
   - 适合实时查询场景

## 5. NormalTabletReader：标准表查询实现

### 5.1 NormalTabletReader 的实现

`NormalTabletReader` 是标准表的查询实现，定义在 `table/normal_table/NormalTabletReader.h` 中：

```cpp
// table/normal_table/NormalTabletReader.h
class NormalTabletReader : public framework::TabletReader
{
public:
    NormalTabletReader(const std::shared_ptr<config::ITabletSchema>& schema,
                       const std::shared_ptr<NormalTabletMetrics>& normalTabletMetrics);
    
    // 打开：初始化 TabletData 和读取资源
    Status DoOpen(const std::shared_ptr<framework::TabletData>& tabletData,
                  const framework::ReadResource& readResource) override;
    
    // 搜索：JSON 格式的查询
    Status Search(const std::string& jsonQuery, std::string& result) const override;
    
    // 获取各种 IndexReader
    std::shared_ptr<indexlib::index::InvertedIndexReader> GetMultiFieldIndexReader() const;
    const std::shared_ptr<index::DeletionMapIndexReader>& GetDeletionMapReader() const;
    const std::shared_ptr<indexlib::index::PrimaryKeyIndexReader>& GetPrimaryKeyReader() const;
    std::shared_ptr<index::SummaryReader> GetSummaryReader() const;
    std::shared_ptr<index::AttributeReader> GetAttributeReader(const std::string& attrName) const;
};
```

**NormalTabletReader 的关键组件**：

```mermaid
flowchart TD
    Start[NormalTabletReader] --> ComponentGroup
    
    subgraph ComponentGroup["NormalTabletReader 关键组件"]
        direction TB
        C1[NormalTabletReader<br/>普通索引表的查询入口]
        C2[MultiFieldIndexReader<br/>多字段倒排索引Reader]
        C3[DeletionMapReader<br/>删除映射Reader]
        C4[PrimaryKeyReader<br/>主键索引Reader]
        C5[SummaryReader<br/>摘要Reader]
        C6[AttributeReader<br/>属性Reader]
        C1 --> C2
        C1 --> C3
        C1 --> C4
        C1 --> C5
        C1 --> C6
    end
    
    subgraph MultiFieldGroup["MultiFieldIndexReader：多字段倒排索引"]
        direction TB
        M1[管理多个字段的倒排索引<br/>支持多字段联合查询]
        M2[全文检索功能<br/>TermQuery/RangeQuery等]
        M3[返回匹配的DocId列表<br/>包含相关性分数]
        M1 --> M2
        M2 --> M3
    end
    
    subgraph DeletionMapGroup["DeletionMapReader：删除映射"]
        direction TB
        D1[管理删除文档映射<br/>记录已删除的DocId]
        D2[过滤删除文档<br/>查询时过滤已删除文档]
        D3[支持Tombstone机制<br/>标记删除状态]
        D1 --> D2
        D2 --> D3
    end
    
    subgraph PrimaryKeyGroup["PrimaryKeyReader：主键索引"]
        direction TB
        P1[管理主键索引<br/>主键到DocId的映射]
        P2[主键查询功能<br/>根据主键查找DocId]
        P3[支持精确匹配<br/>O1时间复杂度]
        P1 --> P2
        P2 --> P3
    end
    
    subgraph SummaryGroup["SummaryReader：摘要"]
        direction TB
        S1[管理文档摘要<br/>存储文档的摘要信息]
        S2[获取文档摘要<br/>根据DocId读取摘要]
        S3[支持字段选择<br/>按需读取字段]
        S1 --> S2
        S2 --> S3
    end
    
    subgraph AttributeGroup["AttributeReader：属性"]
        direction TB
        A1[管理属性索引<br/>存储文档的属性值]
        A2[属性查询功能<br/>根据DocId读取属性值]
        A3[支持多种数据类型<br/>int/string/float等]
        A1 --> A2
        A2 --> A3
    end
    
    C2 --> MultiFieldGroup
    C3 --> DeletionMapGroup
    C4 --> PrimaryKeyGroup
    C5 --> SummaryGroup
    C6 --> AttributeGroup
    
    MultiFieldGroup --> Function[组件功能]
    DeletionMapGroup --> Function
    PrimaryKeyGroup --> Function
    SummaryGroup --> Function
    AttributeGroup --> Function
    
    Function --> F1[全文搜索<br/>MultiFieldIndexReader]
    Function --> F2[删除过滤<br/>DeletionMapReader]
    Function --> F3[主键查找<br/>PrimaryKeyReader]
    Function --> F4[文档展示<br/>SummaryReader]
    Function --> F5[属性查询<br/>AttributeReader]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style ComponentLayer fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style ComponentGroup fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style C1 fill:#90caf9,stroke:#1976d2,stroke-width:2px
    style C2 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C3 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C4 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C5 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style C6 fill:#c5e1f5,stroke:#1976d2,stroke-width:1px
    style MultiFieldGroup fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style M1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style M2 fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style M3 fill:#ffe0b2,stroke:#f57c00,stroke-width:1px
    style DeletionMapGroup fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style D1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style D2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:2px
    style D3 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style PrimaryKeyGroup fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style P1 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style P2 fill:#ce93d8,stroke:#7b1fa2,stroke-width:2px
    style P3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1px
    style SummaryGroup fill:#fce4ec,stroke:#ef4444,stroke-width:2px
    style S1 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style S2 fill:#f48fb1,stroke:#ef4444,stroke-width:2px
    style S3 fill:#f8bbd0,stroke:#ef4444,stroke-width:1px
    style AttributeGroup fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style A1 fill:#fff59d,stroke:#f57f17,stroke-width:1px
    style A2 fill:#ffcc02,stroke:#f57f17,stroke-width:2px
    style A3 fill:#fff59d,stroke:#f57f17,stroke-width:1px
    style Function fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style F1 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F2 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F3 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F4 fill:#e0e0e0,stroke:#757575,stroke-width:1px
    style F5 fill:#e0e0e0,stroke:#757575,stroke-width:1px
```

- **MultiFieldIndexReader**：多字段倒排索引 Reader
- **DeletionMapReader**：删除映射 Reader
- **PrimaryKeyReader**：主键索引 Reader
- **SummaryReader**：摘要 Reader
- **AttributeReader**：属性 Reader

### 5.2 NormalTabletReader::DoOpen()

`DoOpen()` 方法初始化 NormalTabletReader：

```mermaid
flowchart LR
    Start([DoOpen 开始]) --> Step1[1. 初始化<br/>TabletData]
    
    Step1 --> Step2[2. 创建<br/>Reader 组件]
    
    subgraph Readers["Reader 组件创建顺序"]
        direction LR
        R1["① MultiFieldIndexReader<br/>多字段倒排索引"]
        R2["② DeletionMapReader<br/>删除映射"]
        R3["③ PrimaryKeyReader<br/>主键索引"]
        R4["④ SummaryReader<br/>摘要"]
        R5["⑤ AttributeReader<br/>属性"]
        
        R1 --> R2 --> R3 --> R4 --> R5
    end
    
    Step2 --> R1
    R5 --> Complete([完成初始化])
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style Step1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Step2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Readers fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style R1 fill:#e3f2fd,stroke:#1976d2,stroke-width:1.5px
    style R2 fill:#fff3e0,stroke:#f57c00,stroke-width:1.5px
    style R3 fill:#e8f5e9,stroke:#2e7d32,stroke-width:1.5px
    style R4 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1.5px
    style R5 fill:#e0f2f1,stroke:#00695c,stroke-width:1.5px
    style Complete fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
```

**DoOpen 流程**：
1. **初始化 TabletData**：保存 TabletData 的引用
2. **创建 MultiFieldIndexReader**：创建多字段倒排索引 Reader
3. **创建 DeletionMapReader**：创建删除映射 Reader
4. **创建 PrimaryKeyReader**：创建主键索引 Reader
5. **创建 SummaryReader**：创建摘要 Reader
6. **创建 AttributeReader**：根据需要创建属性 Reader

### 5.3 NormalTabletReader::Search()

`Search()` 方法实现标准表的查询：

```mermaid
flowchart LR
    Start([Search 开始]) --> A[解析查询]
    
    A --> Prepare[准备阶段]
    
    subgraph Prepare["准备阶段"]
        direction LR
        B[获取 IndexReader]
        C[遍历 Segment]
        B --> C
    end
    
    Prepare --> B
    C --> Query[查询阶段]
    
    subgraph Query["查询阶段"]
        direction LR
        D[并行查询]
    end
    
    Query --> D
    D --> PostProcess[后处理阶段]
    
    subgraph PostProcess["后处理阶段"]
        direction LR
        E[过滤删除文档]
        F[合并结果]
        G[返回结果]
        E --> F --> G
    end
    
    PostProcess --> E
    G --> End([完成])
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style A fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Prepare fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style B fill:#c8e6c9,stroke:#2e7d32,stroke-width:1.5px
    style C fill:#a5d6a7,stroke:#2e7d32,stroke-width:1.5px
    style Query fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style D fill:#ffe0b2,stroke:#f57c00,stroke-width:1.5px
    style PostProcess fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style E fill:#e1bee7,stroke:#7b1fa2,stroke-width:1.5px
    style F fill:#ce93d8,stroke:#7b1fa2,stroke-width:1.5px
    style G fill:#ba68c8,stroke:#7b1fa2,stroke-width:1.5px
    style End fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

**Search 流程**：
1. **解析查询**：将 JSON 查询解析为内部查询对象
2. **获取 IndexReader**：获取 MultiFieldIndexReader、DeletionMapReader 等
3. **遍历 Segment**：遍历所有已构建的 Segment
4. **并行查询**：对多个 Segment 进行并行查询
5. **过滤删除文档**：通过 DeletionMapReader 过滤已删除文档
6. **合并结果**：合并各 Segment 的查询结果
7. **返回结果**：序列化为 JSON 格式返回

## 6. 查询优化

### 6.1 查询剪枝

查询剪枝可以减少不必要的查询：

```mermaid
flowchart TD
    Start([查询剪枝]) --> Strategies[剪枝策略]
    
    subgraph Strategies["三种剪枝策略"]
        direction LR
        S1[Locator 剪枝]
        S2[范围剪枝]
        S3[索引剪枝]
    end
    
    Strategies --> S1
    Strategies --> S2
    Strategies --> S3
    
    S1 --> R1[判断 Segment<br/>是否包含结果]
    S2 --> R2[减少查询范围<br/>缩小搜索空间]
    S3 --> R3[跳过不相关索引<br/>提高查询效率]
    
    R1 --> Benefit[优化效果]
    R2 --> Benefit
    R3 --> Benefit
    
    Benefit --> End([减少不必要查询<br/>提升性能])
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Strategies fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style S1 fill:#fff3e0,stroke:#f57c00,stroke-width:1.5px
    style S2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:1.5px
    style S3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1.5px
    style R1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1.5px
    style R2 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1.5px
    style R3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1.5px
    style Benefit fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    style End fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

**查询剪枝策略**：
- **Locator 剪枝**：通过 Locator 判断哪些 Segment 可能包含查询结果
- **范围剪枝**：通过范围查询剪枝，减少查询范围
- **索引剪枝**：通过索引统计信息剪枝，跳过不相关的索引

### 6.2 查询缓存

查询缓存可以提高查询性能：

```mermaid
flowchart TD
    Start([查询缓存机制]) --> CacheLayer[缓存层]
    
    subgraph CacheLayer["缓存层"]
        direction TB
        
        subgraph Cache1["结果缓存"]
            direction LR
            C1[结果缓存] --> E1[避免重复查询<br/>直接返回缓存结果]
        end
        
        subgraph Cache2["索引缓存"]
            direction LR
            C2[索引缓存] --> E2[减少 IO 操作<br/>从内存读取索引]
        end
        
        subgraph Cache3["统计缓存"]
            direction LR
            C3[统计缓存] --> E3[减少计算开销<br/>复用统计信息]
        end
    end
    
    CacheLayer --> Cache1
    CacheLayer --> Cache2
    CacheLayer --> Cache3
    
    E1 --> Benefit[综合性能提升]
    E2 --> Benefit
    E3 --> Benefit
    
    Benefit --> End([提升查询性能<br/>降低系统负载])
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style CacheLayer fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style Cache1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style C1 fill:#ffe0b2,stroke:#f57c00,stroke-width:1.5px
    style E1 fill:#fff8e1,stroke:#f57c00,stroke-width:1.5px
    style Cache2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style C2 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1.5px
    style E2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:1.5px
    style Cache3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style C3 fill:#e1bee7,stroke:#7b1fa2,stroke-width:1.5px
    style E3 fill:#ce93d8,stroke:#7b1fa2,stroke-width:1.5px
    style Benefit fill:#fff9c4,stroke:#f9a825,stroke-width:3px
    style End fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
```

**查询缓存机制**：
- **结果缓存**：缓存查询结果，避免重复查询
- **索引缓存**：缓存索引数据，减少 IO 操作
- **统计缓存**：缓存统计信息，减少计算开销

### 6.3 并行查询优化

并行查询可以提高查询性能：

```mermaid
flowchart LR
    Start[并行查询优化] --> P1[1. Segment 并行<br/>多个 Segment 并行查询]
    P1 --> P2[2. 索引并行<br/>多个索引并行查询]
    P2 --> P3[3. 结果并行合并<br/>查询结果并行合并]
    P3 --> Benefit[性能提升<br/>缩短延迟<br/>提高吞吐量]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style P1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style P2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style P3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Benefit fill:#fff9c4,stroke:#f9a825,stroke-width:3px
```

**并行查询优化**：
- **Segment 并行**：多个 Segment 可以并行查询
- **索引并行**：多个索引可以并行查询
- **结果并行合并**：查询结果可以并行合并

## 7. 查询性能优化

### 7.1 索引加载优化

索引加载优化可以减少查询延迟：

```mermaid
flowchart TD
    Start[索引加载优化] --> Strategies[优化策略]
    
    subgraph Strategies["三种优化策略"]
        direction LR
        L1[1. 按需加载<br/>只加载查询需要的索引]
        L2[2. 懒加载<br/>查询时才加载索引数据]
        L3[3. 预加载<br/>预加载常用索引减少延迟]
    end
    
    Strategies --> L1
    Strategies --> L2
    Strategies --> L3
    
    L1 --> Benefit[优化效果]
    L2 --> Benefit
    L3 --> Benefit
    
    subgraph Effects["优化效果"]
        direction LR
        E1[减少内存占用]
        E2[提升加载效率]
    end
    
    Benefit --> Effects
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style Strategies fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style L1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style L2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style L3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Benefit fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    style Effects fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style E1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1.5px
    style E2 fill:#a5d6a7,stroke:#2e7d32,stroke-width:1.5px
```

**索引加载优化**：
- **按需加载**：只加载查询需要的索引
- **懒加载**：在查询时才加载索引数据
- **预加载**：预加载常用索引，减少查询延迟

### 7.2 内存优化

内存优化可以减少内存使用：

```mermaid
flowchart LR
    Start[内存优化] --> M1[1. 内存池<br/>减少内存分配开销]
    M1 --> M2[2. 缓存控制<br/>控制缓存大小避免溢出]
    M2 --> M3[3. 内存回收<br/>及时回收不再使用的内存]
    M3 --> Benefit[优化效果<br/>降低内存占用<br/>提升系统稳定性]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style M1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style M2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style M3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Benefit fill:#fff9c4,stroke:#f9a825,stroke-width:3px
```

**内存优化策略**：
- **内存池**：使用内存池减少内存分配开销
- **缓存控制**：控制缓存大小，避免内存溢出
- **内存回收**：及时回收不再使用的内存

### 7.3 IO 优化

IO 优化可以减少 IO 操作：

```mermaid
flowchart TD
    Start[IO 优化] --> Strategy[优化策略]
    
    subgraph Strategy["三种优化策略"]
        direction LR
        I1[1. 批量读取<br/>减少 IO 次数]
        I2[2. 预读<br/>减少查询延迟]
        I3[3. IO 合并<br/>减少 IO 开销]
    end
    
    Strategy --> I1
    Strategy --> I2
    Strategy --> I3
    
    I1 --> Benefit[优化效果]
    I2 --> Benefit
    I3 --> Benefit
    
    Benefit --> E1[提升 IO 效率]
    Benefit --> E2[降低系统负载]
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style Strategy fill:#f5f5f5,stroke:#757575,stroke-width:2px
    style I1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style I2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style I3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Benefit fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    style E1 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1.5px
    style E2 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1.5px
```

**IO 优化策略**：
- **批量读取**：批量读取索引数据，减少 IO 次数
- **预读**：预读可能需要的索引数据
- **IO 合并**：合并多个 IO 操作，减少 IO 开销

## 8. 查询场景示例

### 8.1 全文检索场景

在全文检索场景中，查询流程：

```mermaid
flowchart LR
    Start([全文检索]) --> S1[解析查询]
    
    S1 --> S2[获取 InvertedIndexReader]
    S2 --> S3[查找 term]
    S3 --> S4[获取倒排列表]
    S4 --> S5[过滤删除文档]
    S5 --> S6[计算相关性]
    S6 --> End([排序返回])
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style S1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style S2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style S3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style S4 fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    style S5 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style S6 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style End fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
```

**全文检索流程**：
1. **解析查询**：解析 term 查询
2. **获取 InvertedIndexReader**：获取倒排索引 Reader
3. **查找 term**：在倒排索引中查找 term
4. **获取倒排列表**：获取 term 对应的倒排列表
5. **过滤删除文档**：通过 DeletionMap 过滤已删除文档
6. **计算相关性**：计算文档的相关性分数
7. **排序返回**：按相关性分数排序，返回结果

### 8.2 属性查询场景

在属性查询场景中，查询流程：

```mermaid
flowchart LR
    Start([属性查询]) --> A1[解析查询]
    
    A1 --> A2[获取 AttributeReader]
    A2 --> A3[遍历 Segment]
    A3 --> A4[查询属性]
    A4 --> A5[过滤匹配]
    A5 --> End([返回结果])
    
    style Start fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style A1 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style A2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style A3 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style A4 fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    style A5 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style End fill:#c8e6c9,stroke:#2e7d32,stroke-width:3px
```

**属性查询流程**：
1. **解析查询**：解析属性查询条件
2. **获取 AttributeReader**：获取属性 Reader
3. **遍历 Segment**：遍历所有已构建的 Segment
4. **查询属性**：在 Segment 内查询属性值
5. **过滤匹配**：过滤匹配查询条件的文档
6. **返回结果**：返回匹配的文档列表

## 9. 性能优化与最佳实践

### 9.1 查询性能优化

**优化策略**：

1. **IndexReader 缓存优化**：
   - **缓存预热**：系统启动时预加载常用 IndexReader
   - **缓存策略**：根据查询模式选择合适的缓存策略（LRU、FIFO 等）
   - **缓存大小**：根据内存情况调整缓存大小，平衡性能和内存
   
2. **并行查询优化**：
   - **Segment 并行度**：根据 CPU 核心数调整 Segment 并行度
   - **索引并行度**：多个索引可以并行查询，提高查询速度
   - **结果并行合并**：查询结果可以并行合并，减少合并时间
   
3. **查询剪枝优化**：
   - **Locator 剪枝**：通过 Locator 判断哪些 Segment 需要查询
   - **范围剪枝**：通过范围查询剪枝，减少查询范围
   - **索引剪枝**：通过索引统计信息剪枝，跳过不相关的索引

### 9.2 内存优化

**优化策略**：

1. **索引加载优化**：
   - **按需加载**：只加载查询需要的索引，减少内存占用
   - **懒加载**：在查询时才加载索引数据，延迟内存分配
   - **预加载**：预加载常用索引，减少查询延迟
   
2. **结果缓存优化**：
   - **结果缓存**：缓存常用查询结果，避免重复查询
   - **缓存大小**：控制缓存大小，避免内存溢出
   - **缓存策略**：使用 LRU 等策略淘汰不常用的缓存
   
3. **内存池优化**：
   - **内存池**：使用内存池减少内存分配开销
   - **内存复用**：复用查询结果的内存，减少内存分配
   - **内存回收**：及时回收不再使用的内存

### 9.3 IO 优化

**优化策略**：

1. **批量读取优化**：
   - **批量读取**：批量读取索引数据，减少 IO 次数
   - **预读**：预读可能需要的索引数据，减少查询延迟
   - **IO 合并**：合并多个 IO 操作，减少 IO 开销
   
2. **索引压缩优化**：
   - **压缩算法**：选择合适的压缩算法（LZ4、Zstd 等）
   - **压缩级别**：根据场景选择合适的压缩级别
   - **压缩缓存**：缓存解压结果，减少重复解压
   
3. **IO 并发优化**：
   - **IO 并发度**：根据 IO 能力调整 IO 并发度
   - **IO 优先级**：重要查询的 IO 优先执行
   - **IO 限流**：控制 IO 速率，避免 IO 过载

## 10. 小结

查询流程是 IndexLib 的核心功能，包括 TabletReader 和 IndexReader 两个层次。通过本文的深入解析，我们了解到：

**核心组件**：

- **TabletReader**：查询入口，提供 JSON 格式的查询接口，管理 IndexReader 缓存
  - **接口设计**：通过 JSON 格式隐藏底层实现，提供统一的查询接口
  - **缓存机制**：通过 IndexReader 缓存避免重复创建，提高查询性能
  - **资源管理**：管理查询资源（内存配额、缓存等），保证查询稳定性
  
- **IndexReader**：索引查询接口，提供不同类型的索引查询能力
  - **接口抽象**：通过接口定义统一的查询能力，支持多种索引类型
  - **类型支持**：支持倒排索引、正排索引、主键索引等多种索引类型
  - **查询优化**：通过查询剪枝、缓存等机制优化查询性能
  
- **查询流程**：包括解析查询、获取 IndexReader、遍历 Segment、并行查询、合并结果等步骤
  - **查询解析**：将 JSON 查询解析为内部查询对象，支持多种查询类型
  - **并行查询**：支持多个 Segment 并行查询，提高查询性能
  - **结果合并**：包括去重、排序、分页等处理，保证查询结果的正确性

**设计亮点**：

1. **IndexReader 缓存**：通过缓存避免重复创建，显著提升查询性能
2. **并行查询**：支持多个 Segment 并行查询，显著提升查询性能
3. **查询剪枝**：通过 Locator、范围等机制剪枝，减少不必要的查询
4. **结果合并**：使用高效的合并算法（堆合并、并行合并），提高合并性能
5. **内存优化**：通过按需加载、懒加载等机制，减少内存占用

**性能优化**：

- **查询延迟**：通过并行查询和缓存，有效降低查询延迟
- **吞吐量**：并行查询显著提高吞吐量
- **内存使用**：按需加载和懒加载有效降低内存使用
- **IO 性能**：批量读取和预读显著提高 IO 性能

理解查询流程，是掌握 IndexLib 查询机制的关键。在下一篇文章中，我们将深入介绍版本管理和增量更新的实现细节，包括 Version 结构、Locator 机制、增量更新流程等各个组件的实现原理和性能优化策略。
