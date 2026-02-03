---
layout: single
title: "C++ Core Guidelines 阅读笔记（3）：资源管理"
series: cpp
permalink: /cpp-guidelines-003-resource-management/
tags: [C++, 编程语言, C++ Core Guidelines]
---

## 前言

资源管理是 C++ 编程的核心问题。本文是 C++ Core Guidelines 阅读笔记的第三篇，重点讨论内存、文件、锁等资源的正确管理方式。

## 1. 资源管理原则

资源管理是 C++ 编程的核心挑战。C++ Core Guidelines 强调使用 RAII 自动管理所有资源。

### 1.1 使用 RAII

所有资源都应该通过对象管理，利用对象的生命周期自动管理资源：

```cpp
// 好的：RAII
{
    std::lock_guard<std::mutex> lock(mtx);
    // 临界区代码
    // 即使抛出异常，锁也会自动释放
}

// 不好：手动管理
mtx.lock();
// 如果这里抛出异常，锁不会被释放
risky_operation();
mtx.unlock();  // 永远不会执行
```

### 1.2 资源获取即初始化

资源应该在构造函数中获取，在析构函数中释放：

```cpp
// 好的：在构造函数中获取资源
class FileHandle {
private:
    FILE* file_;
public:
    explicit FileHandle(const char* path) : file_(fopen(path, "r")) {
        if (!file_) {
            throw std::runtime_error("Failed to open file");
        }
    }
    ~FileHandle() noexcept {
        if (file_) {
            fclose(file_);
        }
    }
    
    // 禁止拷贝，允许移动
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
    FileHandle(FileHandle&& other) noexcept : file_(other.file_) {
        other.file_ = nullptr;
    }
};

// 不好：在构造函数外获取资源
class FileHandle {
    FILE* file_;
public:
    FileHandle() : file_(nullptr) {}
    void open(const char* path) { file_ = fopen(path, "r"); }
    // 容易忘记调用 open
    // 如果忘记调用 open，file_ 是 nullptr，使用会出错
};
```

### 1.3 RAII 的优势


## 2. 内存管理

内存是最常见的资源，C++ Core Guidelines 强烈推荐使用智能指针管理内存。

### 2.1 使用智能指针

智能指针通过 RAII 自动管理内存：

```cpp
// 好的：智能指针
std::unique_ptr<Resource> resource = create_resource();
// 自动管理，无需手动 delete

// 不好：原始指针
Resource* resource = create_resource();
// 需要手动 delete
delete resource;  // 容易忘记或重复删除
```

### 2.2 避免 new/delete

直接使用 new/delete 容易出错，应该使用 make_unique/make_shared：

```cpp
// 好的：使用 make_unique/make_shared
auto ptr1 = std::make_unique<MyClass>(args);
auto ptr2 = std::make_shared<MyClass>(args);

// 不好：直接使用 new
auto ptr1 = std::unique_ptr<MyClass>(new MyClass(args));
// 问题：如果 new 成功但 make_unique 失败，内存泄漏

auto ptr2 = std::shared_ptr<MyClass>(new MyClass(args));
// 问题：两次内存分配（对象 + 控制块）
```

### 2.3 避免内存泄漏

内存泄漏是常见问题，使用智能指针可以完全避免：

```cpp
// 好的：自动管理
void process() {
    auto data = std::make_unique<Data>();
    if (error) {
        return;  // 自动清理，无泄漏
    }
    risky_operation();  // 即使抛出异常也自动清理
    // data 自动析构
}

// 不好：可能泄漏
void process() {
    Data* data = new Data();
    if (error) {
        return;  // 泄漏：data 没有被删除
    }
    risky_operation();  // 如果抛出异常，data 泄漏
    delete data;
}
```

### 2.4 循环引用问题

使用 shared_ptr 时需要注意循环引用：

```cpp
// 问题：循环引用
struct Node {
    std::shared_ptr<Node> next;
    std::shared_ptr<Node> prev;  // 循环引用
};

auto n1 = std::make_shared<Node>();
auto n2 = std::make_shared<Node>();
n1->next = n2;
n2->prev = n1;  // 循环引用，内存泄漏

// 解决：使用 weak_ptr
struct Node {
    std::shared_ptr<Node> next;
    std::weak_ptr<Node> prev;  // 打破循环
};
```

## 3. 所有权管理

### 3.1 明确所有权

```cpp
// 好的：明确所有权
std::unique_ptr<Resource> create_resource();  // 返回所有权

void process(const Resource& r);  // 不拥有，只观察

// 不好：所有权不明确
Resource* create_resource();  // 谁负责删除？
```

### 3.2 使用 unique_ptr 表示独占所有权

```cpp
// 好的：独占所有权
class Container {
private:
    std::unique_ptr<Data> data_;
public:
    Container(std::unique_ptr<Data> data) : data_(std::move(data)) {}
};
```

### 3.3 使用 shared_ptr 表示共享所有权

```cpp
// 好的：共享所有权
class Node {
private:
    std::shared_ptr<Node> next_;
public:
    void set_next(std::shared_ptr<Node> next) {
        next_ = next;
    }
};
```

## 4. 文件管理

### 4.1 使用 RAII 管理文件

```cpp
// 好的：RAII 文件管理
{
    std::ifstream file("data.txt");
    if (file.is_open()) {
        // 使用文件
    }
    // 自动关闭
}

// 不好：手动管理
FILE* file = fopen("data.txt", "r");
// 如果忘记 fclose，文件句柄泄漏
fclose(file);
```

### 4.2 使用标准库流

```cpp
// 好的：标准库流
std::ifstream file("data.txt");
std::string line;
while (std::getline(file, line)) {
    process(line);
}

// 不好：C 风格文件操作
FILE* file = fopen("data.txt", "r");
char buffer[1024];
while (fgets(buffer, sizeof(buffer), file)) {
    process(buffer);
}
fclose(file);
```

## 5. 锁管理

### 5.1 使用 lock_guard

```cpp
// 好的：lock_guard
{
    std::lock_guard<std::mutex> lock(mtx);
    // 临界区
}

// 不好：手动锁定
mtx.lock();
// 临界区
mtx.unlock();  // 如果抛出异常，不会解锁
```

### 5.2 使用 unique_lock 需要时

```cpp
// 好的：需要条件变量时使用 unique_lock
std::unique_lock<std::mutex> lock(mtx);
cv.wait(lock, []{ return ready; });

// 简单锁定使用 lock_guard
std::lock_guard<std::mutex> lock(mtx);
```

## 6. 容器管理

### 6.1 使用标准库容器

```cpp
// 好的：标准库容器自动管理内存
std::vector<int> vec;
vec.push_back(1);

// 不好：手动管理数组
int* arr = new int[100];
// 需要手动 delete[]
delete[] arr;
```

### 6.2 预分配空间

```cpp
// 好的：预分配空间
std::vector<int> vec;
vec.reserve(1000);  // 避免多次重新分配

for (int i = 0; i < 1000; ++i) {
    vec.push_back(i);
}
```

## 7. 异常安全

### 7.1 保证基本异常安全

```cpp
// 好的：基本异常安全
class Container {
private:
    std::vector<int> data_;
public:
    void add(int value) {
        data_.push_back(value);  // 如果失败，状态不变
    }
};
```

### 7.2 保证强异常安全

```cpp
// 好的：强异常安全
void update_data(Data& data, const Data& new_data) {
    Data backup = data;  // 先备份
    try {
        data = new_data;  // 如果失败，恢复备份
    } catch (...) {
        data = backup;
        throw;
    }
}
```

## 8. 资源泄漏检查

### 8.1 使用工具检查

```cpp
// 使用 AddressSanitizer 检查内存泄漏
// 编译时添加 -fsanitize=address

// 使用 Valgrind 检查
// valgrind --leak-check=full ./program
```

### 8.2 代码审查

```cpp
// 检查清单：
// 1. 所有 new 都有对应的 delete？
// 2. 所有资源获取都有对应的释放？
// 3. 异常路径是否也释放资源？
```

## 9. 最佳实践

### 9.1 资源管理检查清单

1. **所有资源都用 RAII 管理**
2. **使用智能指针而非原始指针**
3. **避免 new/delete，使用 make_unique/make_shared**
4. **明确所有权：unique_ptr vs shared_ptr**
5. **使用标准库容器和流**

### 9.2 常见错误

```cpp
// 错误 1：忘记释放资源
void bad() {
    Resource* r = new Resource();
    // 忘记 delete
}

// 错误 2：异常时资源泄漏
void bad() {
    Resource* r = new Resource();
    risky_operation();  // 如果抛出异常，r 泄漏
    delete r;
}

// 错误 3：重复释放
void bad() {
    Resource* r = new Resource();
    delete r;
    delete r;  // 未定义行为
}
```

## 11. 实际工程案例

### 11.1 案例：内存泄漏修复

**问题**：原始指针导致内存泄漏

```cpp
// 原始代码：内存泄漏
void process_data() {
    Data* data = new Data();
    if (some_condition()) {
        return;  // 泄漏
    }
    process(data);
    delete data;
}
```

**改进**：使用智能指针

```cpp
// 改进代码：自动管理
void process_data() {
    auto data = std::make_unique<Data>();
    if (some_condition()) {
        return;  // 自动清理
    }
    process(data.get());
    // 自动清理
}
```

### 11.2 案例：文件句柄管理

**问题**：手动管理文件句柄，容易泄漏

```cpp
// 原始代码：容易出错
void read_file(const char* path) {
    FILE* f = fopen(path, "r");
    if (!f) return;
    // 如果这里抛出异常，文件不会关闭
    process_file(f);
    fclose(f);
}
```

**改进**：使用 RAII

```cpp
// 改进代码：自动管理
void read_file(const char* path) {
    FileHandle f(path);  // 自动打开
    // 即使抛出异常，文件也会自动关闭
    process_file(f.get());
    // 自动关闭
}
```

## 12. 资源管理设计模式

### 12.1 RAII 模式


### 12.2 所有权模式


## 13. 性能考虑

### 13.1 智能指针的性能

```cpp
// 性能对比
std::unique_ptr<int> p1;  // 开销：一个指针（8 字节）
std::shared_ptr<int> p2;  // 开销：两个指针 + 控制块（约 32 字节）

// unique_ptr：零开销，与原始指针性能相同
// shared_ptr：有引用计数开销，但提供共享所有权
```

### 13.2 资源管理的性能影响


## 14. 最佳实践检查清单

### 14.1 资源管理检查清单

1. **所有资源都用 RAII 管理**
2. **使用智能指针而非原始指针**
3. **避免 new/delete，使用 make_unique/make_shared**
4. **明确所有权：unique_ptr vs shared_ptr**
5. **使用标准库容器和流**
6. **使用 lock_guard 管理锁**
7. **保证异常安全**
8. **使用工具检查资源泄漏**

### 14.2 常见错误与解决方案


## 15. 小结

资源管理是 C++ 编程的核心，应该始终使用 RAII 和智能指针。

**核心要点**：
- **RAII 原则**：资源获取即初始化，资源释放即析构
- **智能指针**：使用 unique_ptr 和 shared_ptr 管理内存
- **避免 new/delete**：使用 make_unique 和 make_shared
- **明确所有权**：通过类型系统表达所有权语义
- **标准库容器**：使用 vector、string 等自动管理内存
- **锁管理**：使用 lock_guard 和 unique_lock
- **异常安全**：RAII 保证异常时资源也能释放
- **工具检查**：使用 AddressSanitizer、Valgrind 检查泄漏

遵循这些规范，可以完全避免资源泄漏和内存错误。
