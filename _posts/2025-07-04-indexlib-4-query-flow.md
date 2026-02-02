---
layout: single
title: "IndexLib（4）：查询流程：TabletReader 与 IndexReader"
series: indexlib
permalink: /indexlib-4-query-flow/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-07-04
---

在上一篇文章中，我们深入了解了索引构建的完整流程。本文将继续深入，详细解析查询流程的实现，这是理解 IndexLib 如何从索引中查询数据的关键。

![查询流程概览：从 JSON 查询到结果返回的完整过程](/images/diagrams/indexlib-query-complete-flow.svg)

**查询流程图**：

```mermaid
graph TD
    A[接收 JSON 查询] --> B[解析查询]
    B --> C[提取查询类型]
    C --> D[提取查询条件]
    D --> E[创建查询对象]
    E --> F[获取 TabletReader]
    F --> G[获取 IndexReader]
    G --> H[遍历 Segment]
    H --> I[并行查询各 Segment]
    I --> J[倒排索引查询]
    I --> K[正排索引查询]
    I --> L[主键索引查询]
    J --> M[合并查询结果]
    K --> M
    L --> M
    M --> N[去重]
    N --> O[排序]
    O --> P[分页]
    P --> Q[序列化为 JSON]
    Q --> R[返回结果]
    style B fill:#e3f2fd
    style I fill:#fff3e0
    style M fill:#f3e5f5
    style Q fill:#e8f5e9
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

![查询流程概览：TabletReader 与 IndexReader 的交互](/images/diagrams/indexlib-query-flow-overview.svg)

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
- **GetIndexReader**：根据索引类型和名称获取 IndexReader，支持缓存
- **GetSchema**：获取 Schema，用于查询验证和字段解析

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

![TabletReader 的结构：包含 Schema、IndexReaderMap、TabletData 等](/images/diagrams/indexlib-tabletreader-structure.svg)

- **Schema**：索引的 Schema 定义，用于查询验证和字段解析
- **IndexReaderMap**：IndexReader 的缓存，避免重复创建
- **TabletData**：索引数据，包含所有 Segment
- **ReadResource**：读取资源（内存配额、缓存等）

### 2.2 TabletReader::Open()

`Open()` 方法初始化 TabletReader，准备查询：

![TabletReader::Open() 流程：初始化 TabletData 和读取资源](/images/diagrams/indexlib-tabletreader-open.svg)

**Open 流程**：
1. **设置 TabletData**：保存 TabletData 的引用
2. **设置 ReadResource**：保存读取资源（内存配额、缓存等）
3. **调用 DoOpen()**：子类实现具体的打开逻辑
4. **初始化 IndexReader**：根据需要初始化 IndexReader

### 2.3 TabletReader::Search()

`Search()` 方法是查询的入口，将 JSON 查询转换为结果：

![TabletReader::Search() 流程：从 JSON 查询到结果返回](/images/diagrams/indexlib-tabletreader-search.svg)

**Search 流程**：
1. **解析查询**：将 JSON 查询解析为内部查询对象
2. **获取 IndexReader**：根据索引类型和名称获取 IndexReader
3. **遍历 Segment**：通过 `TabletData->CreateSlice(ST_BUILT)` 获取所有已构建的 Segment
4. **并行查询**：对多个 Segment 进行并行查询
5. **合并结果**：将各 Segment 的查询结果合并（去重、排序等）
6. **返回结果**：序列化为 JSON 格式返回

### 2.4 IndexReader 缓存机制

`TabletReader` 维护 IndexReader 的缓存，避免重复创建：

![TabletReader IndexReader 缓存：避免重复创建](/images/diagrams/indexlib-tabletreader-cache.svg)

**缓存机制**：
- **缓存 Key**：`(indexType, indexName)` 对
- **缓存 Value**：`IIndexReader` 指针
- **优势**：避免重复创建 IndexReader，提高查询性能

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

![IIndexReader 接口：提供索引查询的抽象](/images/diagrams/indexlib-indexreader-interface.svg)

- **Open**：初始化 IndexReader，加载索引数据
- **Search**：根据查询条件查询索引，返回查询结果
- **GetStatistics**：获取索引统计信息（文档数、term 数等）

### 3.2 不同类型的 IndexReader

IndexLib 支持多种类型的 IndexReader：

![不同类型的 IndexReader：倒排索引、正排索引、主键索引等](/images/diagrams/indexlib-indexreader-types.svg)

**IndexReader 类型**：
- **InvertedIndexReader**：倒排索引 Reader，用于全文检索
- **AttributeReader**：正排索引 Reader，用于属性查询
- **PrimaryKeyIndexReader**：主键索引 Reader，用于主键查询
- **SummaryReader**：摘要 Reader，用于获取文档摘要
- **DeletionMapReader**：删除映射 Reader，用于过滤已删除文档

### 3.3 InvertedIndexReader：倒排索引查询

`InvertedIndexReader` 是倒排索引的查询接口：

![InvertedIndexReader：倒排索引查询的实现](/images/diagrams/indexlib-inverted-indexreader.svg)

**倒排索引查询流程**：
1. **解析查询**：解析 term 查询、范围查询等
2. **查找 term**：在倒排索引中查找 term
3. **获取倒排列表**：获取 term 对应的倒排列表（DocId 列表）
4. **过滤删除文档**：通过 DeletionMap 过滤已删除文档
5. **返回结果**：返回 DocId 列表和相关性分数

### 3.4 AttributeReader：正排索引查询

`AttributeReader` 是正排索引的查询接口：

![AttributeReader：正排索引查询的实现](/images/diagrams/indexlib-attribute-reader.svg)

**正排索引查询流程**：
1. **定位 DocId**：根据全局 DocId 定位到对应的 Segment
2. **转换为局部 DocId**：将全局 DocId 转换为局部 DocId
3. **读取属性值**：从正排索引中读取属性值
4. **返回结果**：返回属性值

## 4. 查询流程详解

### 4.1 查询解析

查询解析将 JSON 格式的查询转换为内部查询对象：

![查询解析：从 JSON 到内部查询对象](/images/diagrams/indexlib-query-parsing.svg)

**查询解析流程**：
1. **解析 JSON**：解析 JSON 格式的查询字符串
2. **提取查询类型**：提取查询类型（term 查询、范围查询等）
3. **提取查询条件**：提取查询条件（term、范围等）
4. **创建查询对象**：创建内部查询对象

### 4.2 多 Segment 并行查询

查询时需要遍历多个 Segment，可以并行查询以提高性能：

![多 Segment 并行查询：提高查询性能](/images/diagrams/indexlib-multi-segment-query.svg)

**并行查询流程**：
1. **获取 Segment 列表**：`TabletData->CreateSlice(ST_BUILT)` 获取所有已构建的 Segment
2. **并行查询**：对每个 Segment 的 Indexer 进行查询（如果支持并行）
3. **合并结果**：将各 Segment 的查询结果合并（去重、排序等）

### 4.3 DocId 转换

查询时需要将全局 DocId 转换为局部 DocId：

![DocId 转换：全局 DocId 到局部 DocId 的转换过程](/images/diagrams/indexlib-docid-conversion.svg)

**DocId 转换流程**：
1. **定位 Segment**：根据全局 DocId 找到对应的 Segment
2. **计算 BaseDocId**：计算该 Segment 的基础 DocId
3. **转换为局部 DocId**：`localDocId = globalDocId - baseDocId`
4. **Segment 内查询**：使用局部 DocId 在 Segment 内查询

### 4.4 结果合并

查询结果需要合并，包括去重、排序等：

![结果合并：去重、排序、分页等处理](/images/diagrams/indexlib-query-result-merge.svg)

**结果合并流程**：
1. **去重**：根据 DocId 去重，避免重复文档
2. **排序**：按相关性分数排序，返回最相关的文档
3. **聚合统计**：计算总数、平均值等统计信息
4. **分页处理**：返回指定页的结果

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

![NormalTabletReader 的结构：包含各种 IndexReader](/images/diagrams/indexlib-normal-tabletreader-structure.svg)

- **MultiFieldIndexReader**：多字段倒排索引 Reader
- **DeletionMapReader**：删除映射 Reader
- **PrimaryKeyReader**：主键索引 Reader
- **SummaryReader**：摘要 Reader
- **AttributeReader**：属性 Reader

### 5.2 NormalTabletReader::DoOpen()

`DoOpen()` 方法初始化 NormalTabletReader：

![NormalTabletReader::DoOpen() 流程：初始化各种 IndexReader](/images/diagrams/indexlib-normal-tabletreader-open.svg)

**DoOpen 流程**：
1. **初始化 TabletData**：保存 TabletData 的引用
2. **创建 MultiFieldIndexReader**：创建多字段倒排索引 Reader
3. **创建 DeletionMapReader**：创建删除映射 Reader
4. **创建 PrimaryKeyReader**：创建主键索引 Reader
5. **创建 SummaryReader**：创建摘要 Reader
6. **创建 AttributeReader**：根据需要创建属性 Reader

### 5.3 NormalTabletReader::Search()

`Search()` 方法实现标准表的查询：

![NormalTabletReader::Search() 流程：标准表查询的实现](/images/diagrams/indexlib-normal-tabletreader-search.svg)

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

![查询剪枝：减少不必要的查询](/images/diagrams/indexlib-query-pruning.svg)

**查询剪枝策略**：
- **Locator 剪枝**：通过 Locator 判断哪些 Segment 可能包含查询结果
- **范围剪枝**：通过范围查询剪枝，减少查询范围
- **索引剪枝**：通过索引统计信息剪枝，跳过不相关的索引

### 6.2 查询缓存

查询缓存可以提高查询性能：

![查询缓存：缓存查询结果，提高查询性能](/images/diagrams/indexlib-query-cache.svg)

**查询缓存机制**：
- **结果缓存**：缓存查询结果，避免重复查询
- **索引缓存**：缓存索引数据，减少 IO 操作
- **统计缓存**：缓存统计信息，减少计算开销

### 6.3 并行查询优化

并行查询可以提高查询性能：

![并行查询优化：提高查询并发度](/images/diagrams/indexlib-query-parallel-optimization.svg)

**并行查询优化**：
- **Segment 并行**：多个 Segment 可以并行查询
- **索引并行**：多个索引可以并行查询
- **结果并行合并**：查询结果可以并行合并

## 7. 查询性能优化

### 7.1 索引加载优化

索引加载优化可以减少查询延迟：

![索引加载优化：按需加载、懒加载等](/images/diagrams/indexlib-query-index-loading.svg)

**索引加载优化**：
- **按需加载**：只加载查询需要的索引
- **懒加载**：在查询时才加载索引数据
- **预加载**：预加载常用索引，减少查询延迟

### 7.2 内存优化

内存优化可以减少内存使用：

![查询内存优化：内存池、缓存控制等](/images/diagrams/indexlib-query-memory-optimization.svg)

**内存优化策略**：
- **内存池**：使用内存池减少内存分配开销
- **缓存控制**：控制缓存大小，避免内存溢出
- **内存回收**：及时回收不再使用的内存

### 7.3 IO 优化

IO 优化可以减少 IO 操作：

![查询 IO 优化：批量读取、预读等](/images/diagrams/indexlib-query-io-optimization.svg)

**IO 优化策略**：
- **批量读取**：批量读取索引数据，减少 IO 次数
- **预读**：预读可能需要的索引数据
- **IO 合并**：合并多个 IO 操作，减少 IO 开销

## 8. 查询场景示例

### 8.1 全文检索场景

在全文检索场景中，查询流程：

![全文检索场景：从 term 查询到结果返回](/images/diagrams/indexlib-query-fulltext-scenario.svg)

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

![属性查询场景：从属性查询到结果返回](/images/diagrams/indexlib-query-attribute-scenario.svg)

**属性查询流程**：
1. **解析查询**：解析属性查询条件
2. **获取 AttributeReader**：获取属性 Reader
3. **遍历 Segment**：遍历所有已构建的 Segment
4. **查询属性**：在 Segment 内查询属性值
5. **过滤匹配**：过滤匹配查询条件的文档
6. **返回结果**：返回匹配的文档列表

## 9. 小结

查询流程是 IndexLib 的核心功能，包括 TabletReader 和 IndexReader 两个层次。通过本文的深入解析，我们了解到：

**关键要点**：
- **TabletReader**：查询入口，提供 JSON 格式的查询接口，管理 IndexReader 缓存
- **IndexReader**：索引查询接口，提供不同类型的索引查询能力
- **查询流程**：包括解析查询、获取 IndexReader、遍历 Segment、并行查询、合并结果等步骤
- **多 Segment 并行查询**：支持多个 Segment 并行查询，提高查询性能
- **结果合并**：包括去重、排序、分页等处理，保证查询结果的正确性
- **查询优化**：通过查询剪枝、查询缓存、并行查询等机制，提高查询性能

理解查询流程，是掌握 IndexLib 查询机制的关键。在下一篇文章中，我们将深入介绍版本管理和增量更新的实现细节。
