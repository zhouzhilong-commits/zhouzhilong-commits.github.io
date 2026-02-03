---
layout: single
title: "C++ Core Guidelines 阅读笔记（1）：哲学与接口设计"
series: cpp
permalink: /cpp-guidelines-001-philosophy-interfaces/
tags: [C++, 编程语言, C++ Core Guidelines]
---

## 前言

C++ Core Guidelines 是 Bjarne Stroustrup 和 Herb Sutter 等人编写的 C++ 编程最佳实践指南。本文是系列阅读笔记的第一篇，重点讨论指南的哲学原则和接口设计规范。

## 1. 核心哲学原则

C++ Core Guidelines 建立在几个核心哲学原则之上，这些原则指导着整个指南的设计。

### 1.1 表达意图

代码应该清楚地表达程序员的意图，让代码自解释：

```cpp
// 好的：意图明确
void draw_circle(const Circle& c);
void draw_rectangle(const Rectangle& r);

// 不好：意图不明确
void draw(const Shape& s);  // 不够具体，不知道画什么
```

### 1.2 使用编译期检查

尽可能在编译期捕获错误，而不是等到运行时：

```cpp
// 好的：编译期检查
template<typename T>
void process(const T& value) {
    static_assert(std::is_arithmetic_v<T>, "T must be arithmetic");
    // 编译期就能发现类型错误
}

// 不好：运行时检查
void process(const void* value) {
    if (!value) return;  // 运行时才发现错误
    // 需要运行时测试才能发现问题
}
```

### 1.3 零开销抽象

C++ 的哲学是"零开销抽象"：使用抽象不应该带来运行时开销。

```cpp
// 好的：零开销抽象
std::vector<int> vec;  // 与手动管理内存性能相同
vec.push_back(42);     // 内联，无函数调用开销

// 不好的抽象：带来不必要的开销
class Wrapper {
    std::unique_ptr<int> ptr;  // 不必要的间接访问
public:
    int get() const { return *ptr; }  // 额外的间接访问
};
```

### 1.4 类型安全

使用类型系统防止错误：

```cpp
// 好的：类型安全
using UserId = int;
using ProductId = int;

void process_order(UserId user_id, ProductId product_id);
// 类型系统防止传错参数

// 不好：弱类型
void process_order(int user_id, int product_id);
// 可能传错：process_order(product_id, user_id);
```

### 1.5 资源安全

使用 RAII 自动管理资源：

```cpp
// 好的：资源安全
{
    std::lock_guard<std::mutex> lock(mtx);
    // 自动解锁，即使抛出异常
}

// 不好：手动管理
mtx.lock();
// 如果这里抛出异常，锁不会被释放
mtx.unlock();
```

## 2. 接口设计原则

接口是代码的契约，好的接口设计是高质量代码的基础。

### 2.1 接口应该小而完整

接口应该包含完成其职责所需的所有操作，但不应包含不相关的功能。

```cpp
// 好的：接口小而完整
class File {
public:
    void open(const std::string& path);
    void close();
    bool is_open() const;
    size_t read(void* buffer, size_t size);
    size_t write(const void* buffer, size_t size);
    // 所有操作都与文件 I/O 相关
};

// 不好：接口太大，包含不相关功能
class File {
public:
    void open(const std::string& path);
    void close();
    void compress();  // 不相关：压缩不是文件 I/O 的核心功能
    void encrypt();   // 不相关：加密不是文件 I/O 的核心功能
};
```

### 2.2 优先使用抽象接口

抽象接口提供了灵活性和可测试性：

```cpp
// 好的：抽象接口
class Drawable {
public:
    virtual void draw() const = 0;
    virtual ~Drawable() = default;
};

class Circle : public Drawable {
public:
    void draw() const override {
        // 具体实现
    }
};

// 不好的：具体实现
class Circle {
public:
    void draw() const {
        // 具体实现，难以测试和扩展
    }
};
```

### 2.3 接口应该明确所有权

所有权语义应该通过类型系统明确表达：

```cpp
// 好的：明确所有权
std::unique_ptr<Resource> create_resource();  // 返回所有权
void process(const Resource& r);              // 不拥有，只观察
void take_ownership(std::unique_ptr<Resource> r);  // 接受所有权

// 不好：所有权不明确
Resource* create_resource();  // 谁负责删除？
void process(Resource* r);    // 是否拥有资源？
```

### 2.4 接口应该稳定

接口一旦发布，应该保持稳定，避免频繁变化：

```cpp
// 好的：稳定接口
class Database {
public:
    virtual void connect() = 0;
    virtual void disconnect() = 0;
    virtual ~Database() = default;
    // 接口稳定，可以添加新方法但不破坏现有代码
};

// 不好：频繁变化的接口
class Database {
public:
    virtual void connect() = 0;
    virtual void connect_v2() = 0;  // 版本号在接口中，不稳定
    virtual void disconnect() = 0;
};
```

### 2.5 接口应该易于使用

接口应该让正确的事情容易做，错误的事情难以做：

```cpp
// 好的：易于使用
class File {
public:
    explicit File(const std::string& path);  // 构造时打开
    ~File();  // 自动关闭
    // 使用简单，不容易出错
};

// 不好：容易出错
class File {
public:
    File();  // 默认构造
    void open(const std::string& path);  // 需要手动调用
    // 容易忘记调用 open
};
```

## 3. 参数传递规则

参数传递方式的选择直接影响代码的性能和可读性。

### 3.1 值传递 vs 引用传递

参数传递规则取决于对象大小和用途：

```cpp
// 小对象（< 3 words）：值传递
void process(int x, double y);  // 小对象，值传递更高效

// 大对象：const 引用传递
void process(const std::vector<int>& vec);  // 避免拷贝

// 需要修改：非 const 引用传递
void modify(std::vector<int>& vec);  // 明确表示会修改

// 移动语义：右值引用传递
void take_ownership(std::vector<int>&& vec);  // 接受所有权
```

### 3.2 参数传递的性能影响

```cpp
// 性能对比示例
void by_value(std::vector<int> vec) {
    // 拷贝整个 vector，开销大
}

void by_const_ref(const std::vector<int>& vec) {
    // 只传递引用，无拷贝开销
}

void by_rvalue_ref(std::vector<int>&& vec) {
    // 移动，开销小
}

// 使用
std::vector<int> data(1000000);
by_value(data);        // 拷贝 1000000 个元素
by_const_ref(data);    // 无拷贝
by_rvalue_ref(std::move(data));  // 移动，开销小
```

### 3.3 输出参数

优先使用返回值而非输出参数：

```cpp
// 好的：返回值
std::vector<int> compute_result() {
    std::vector<int> result;
    // 计算
    return result;  // 移动返回，高效
}

// 不好：输出参数
void compute_result(std::vector<int>& out) {
    // 不直观，需要先创建 out
    out.clear();
    // 计算
}
```

### 3.4 完美转发

使用完美转发保持参数的值类别：

```cpp
// 好的：完美转发
template<typename... Args>
auto make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}

// 使用
auto ptr1 = make_unique<MyClass>(42);           // 值传递
auto ptr2 = make_unique<MyClass>(std::move(x)); // 移动传递
```

## 4. 函数设计

### 4.1 函数应该做一件事

```cpp
// 好的：单一职责
void save_to_file(const std::string& filename, const Data& data);

// 不好：做多件事
void process_and_save(Data& data);  // 处理 + 保存
```

### 4.2 函数应该简短

```cpp
// 好的：简短函数
bool is_valid(const User& user) {
    return !user.name.empty() && user.age > 0;
}

// 不好：过长函数
void process_user(User& user) {
    // 100+ 行代码
}
```

## 5. 命名规范

### 5.1 使用有意义的名称

```cpp
// 好的：名称有意义
void calculate_total_price(const std::vector<Item>& items);

// 不好：名称无意义
void calc(const std::vector<Item>& v);
```

### 5.2 遵循命名约定

```cpp
// 类型：PascalCase
class UserAccount {};

// 函数：snake_case 或 camelCase
void get_user_name();
void getUserName();

// 常量：UPPER_CASE
const int MAX_SIZE = 100;
```

## 6. 错误处理

### 6.1 使用异常表示错误

```cpp
// 好的：使用异常
void open_file(const std::string& path) {
    if (!file_exists(path)) {
        throw std::runtime_error("File not found");
    }
}

// 不好：使用错误码
int open_file(const std::string& path) {
    if (!file_exists(path)) {
        return -1;  // 错误码
    }
    return 0;
}
```

### 6.2 不要忽略错误

```cpp
// 好的：处理错误
try {
    process_data();
} catch (const std::exception& e) {
    log_error(e);
    handle_error();
}

// 不好：忽略错误
try {
    process_data();
} catch (...) {
    // 忽略所有错误
}
```

## 7. 资源管理

### 7.1 使用 RAII

```cpp
// 好的：RAII
{
    std::lock_guard<std::mutex> lock(mtx);
    // 自动解锁
}

// 不好：手动管理
mtx.lock();
// ... 如果这里抛出异常，锁不会被释放
mtx.unlock();
```

### 7.2 使用智能指针

```cpp
// 好的：智能指针
std::unique_ptr<Resource> resource = create_resource();

// 不好：原始指针
Resource* resource = create_resource();
// 需要手动 delete
```

## 8. 类型安全

### 8.1 避免类型转换

```cpp
// 好的：类型安全
int value = get_int_value();

// 不好：类型转换
int value = (int)get_double_value();  // 不安全的转换
```

### 8.2 使用强类型

```cpp
// 好的：强类型
using UserId = int;
using ProductId = int;

void process_user(UserId id);  // 类型安全

// 不好：弱类型
void process_user(int id);  // 可能传错类型
```

## 9. 性能考虑

### 9.1 避免不必要的拷贝

```cpp
// 好的：移动语义
std::vector<int> create_data() {
    std::vector<int> data;
    // ...
    return data;  // 移动，不拷贝
}

// 不好：不必要的拷贝
std::vector<int> data = create_data();  // 可能拷贝
```

### 9.2 使用 const 引用

```cpp
// 好的：const 引用
void process(const std::string& s);

// 不好：值传递（大对象）
void process(std::string s);  // 拷贝开销
```

## 11. 实际工程案例

### 11.1 案例：接口设计改进

**问题**：原始接口设计不合理

```cpp
// 原始设计：接口混乱
class DataProcessor {
public:
    void process(Data* data, int* result, bool* success);
    // 所有权不明确，参数太多
};
```

**改进**：遵循 Core Guidelines

```cpp
// 改进设计：清晰的接口
class DataProcessor {
public:
    std::optional<ProcessedData> process(const Data& data);
    // 返回值明确，参数清晰，所有权明确
};
```

### 11.2 案例：参数传递优化

**问题**：不必要的拷贝导致性能问题

```cpp
// 原始代码：性能差
void process_data(std::vector<int> data) {  // 拷贝
    // 处理
}
```

**改进**：使用 const 引用

```cpp
// 改进代码：性能好
void process_data(const std::vector<int>& data) {  // 无拷贝
    // 处理
}
```

## 12. 设计模式与架构原则

### 12.1 接口隔离原则


### 12.2 依赖倒置原则


## 13. 性能分析与优化

### 13.1 参数传递性能测试

```cpp
// 性能测试
void benchmark() {
    std::vector<int> large_vec(1000000);
    
    // 测试值传递
    auto start = std::chrono::high_resolution_clock::now();
    process_by_value(large_vec);
    auto end = std::chrono::high_resolution_clock::now();
    // 值传递：慢（拷贝开销）
    
    // 测试引用传递
    start = std::chrono::high_resolution_clock::now();
    process_by_ref(large_vec);
    end = std::chrono::high_resolution_clock::now();
    // 引用传递：快（无拷贝）
}
```

### 13.2 接口设计对性能的影响


## 14. 常见陷阱与最佳实践

### 14.1 常见陷阱

```cpp
// 陷阱 1：接口太大
class GodObject {
    // 包含所有功能，难以维护
};

// 陷阱 2：所有权不明确
Resource* create();  // 谁负责删除？

// 陷阱 3：参数传递错误
void process(std::vector<int> vec);  // 大对象值传递，性能差
```

### 14.2 最佳实践检查清单

1. **接口小而完整**：只包含相关功能
2. **明确所有权**：使用智能指针表达所有权
3. **参数传递正确**：小对象值传递，大对象引用传递
4. **返回值优先**：使用返回值而非输出参数
5. **类型安全**：使用强类型避免错误
6. **异常安全**：使用异常表示错误
7. **性能考虑**：避免不必要的拷贝

## 15. 小结

C++ Core Guidelines 的哲学强调：表达意图、编译期检查、零开销抽象。

**核心要点**：
- **哲学原则**：表达意图、编译期检查、零开销抽象、类型安全、资源安全
- **接口设计**：小而完整、抽象接口、明确所有权、稳定、易于使用
- **参数传递**：根据对象大小和用途选择传递方式
- **函数设计**：做一件事、简短、参数少
- **命名规范**：有意义、遵循约定
- **错误处理**：使用异常、不忽略错误
- **资源管理**：RAII、智能指针
- **类型安全**：避免类型转换、使用强类型
- **性能考虑**：避免不必要的拷贝、使用移动语义

遵循这些原则，可以写出更安全、更高效、更易维护的 C++ 代码。
