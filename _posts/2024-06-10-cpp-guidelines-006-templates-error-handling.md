---
layout: single
title: "C++ Core Guidelines 阅读笔记（6）：模板与错误处理"
series: cpp
permalink: /cpp-guidelines-006-templates-error-handling/
tags: [C++, 编程语言, C++ Core Guidelines]
---

## 前言

本文是 C++ Core Guidelines 阅读笔记的第六篇，重点讨论模板编程和错误处理的规范。模板是 C++ 的强大特性，错误处理是健壮程序的基础。

## 1. 模板设计

### 1.1 使用概念约束（C++20）

```cpp
// 好的：使用概念
template<std::integral T>
void process(T value) {
    // T 必须是整数类型
}

// C++17 及之前：使用 SFINAE
template<typename T>
std::enable_if_t<std::is_integral_v<T>>
process(T value) {
    // ...
}
```

### 1.2 提供清晰的错误信息

```cpp
// 好的：清晰的错误信息
template<typename T>
void process(T value) {
    static_assert(std::is_arithmetic_v<T>, 
                  "T must be an arithmetic type");
}

// 不好：模糊的错误信息
template<typename T>
void process(T value) {
    // 如果 T 不支持某些操作，错误信息不清晰
}
```

### 1.3 避免过度泛化

```cpp
// 好的：适度的泛化
template<typename T>
void sort(std::vector<T>& vec) {
    std::sort(vec.begin(), vec.end());
}

// 不好：过度泛化
template<typename Container, typename Compare>
void sort_anything(Container& c, Compare comp) {
    // 太泛化，难以使用
}
```

## 2. 模板特化

### 2.1 使用特化优化特定类型

```cpp
// 好的：特化优化
template<typename T>
void process(T value) {
    // 通用实现
}

template<>
void process<int>(int value) {
    // int 类型的优化实现
}
```

### 2.2 避免不必要的特化

```cpp
// 好的：只在需要时特化
template<typename T>
void process(T value) {
    // 通用实现足够
}

// 不好：过度特化
template<>
void process<int>(int value) { /* ... */ }
template<>
void process<long>(long value) { /* ... */ }
template<>
void process<short>(short value) { /* ... */ }
// 太多特化，维护困难
```

## 3. 可变参数模板

### 3.1 使用折叠表达式（C++17）

```cpp
// 好的：折叠表达式
template<typename... Args>
auto sum(Args... args) {
    return (args + ...);
}

// 不好：递归展开
template<typename T>
auto sum(T t) { return t; }
template<typename T, typename... Args>
auto sum(T t, Args... args) {
    return t + sum(args...);
}
```

### 3.2 完美转发

```cpp
// 好的：完美转发
template<typename... Args>
auto make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}
```

## 4. 错误处理策略

### 4.1 使用异常表示错误

```cpp
// 好的：使用异常
void process() {
    if (error) {
        throw std::runtime_error("Error occurred");
    }
}

// 不好：使用错误码
int process() {
    if (error) {
        return -1;  // 错误码
    }
    return 0;
}
```

### 4.2 异常应该表示异常情况

```cpp
// 好的：异常情况使用异常
void open_file(const std::string& path) {
    if (!file_exists(path)) {
        throw std::runtime_error("File not found");
    }
}

// 不好：正常情况使用异常
bool file_exists(const std::string& path) {
    try {
        open_file(path);
        return true;
    } catch (...) {
        return false;
    }
}
```

### 4.3 不要忽略异常

```cpp
// 好的：处理异常
try {
    process();
} catch (const std::exception& e) {
    log_error(e);
    handle_error();
}

// 不好：忽略异常
try {
    process();
} catch (...) {
    // 忽略所有异常
}
```

## 5. 异常安全保证

### 5.1 基本保证

```cpp
// 好的：基本保证
void process(Container& c) {
    auto backup = c;  // 备份
    try {
        modify(c);
    } catch (...) {
        c = backup;  // 恢复
        throw;
    }
}
```

### 5.2 强保证

```cpp
// 好的：强保证
void process(Container& c) {
    auto backup = c;
    try {
        modify(c);
    } catch (...) {
        c = backup;  // 完全恢复
        throw;
    }
}
```

### 5.3 不抛出保证

```cpp
// 好的：不抛出保证
void swap(Container& a, Container& b) noexcept {
    // 交换操作不应该抛出异常
    std::swap(a.data_, b.data_);
}
```

## 6. 错误码 vs 异常

### 6.1 何时使用异常

```cpp
// 使用异常的情况：
// 1. 错误是异常情况
// 2. 错误需要跨函数传播
// 3. 错误处理在调用栈上层

void process() {
    if (critical_error) {
        throw std::runtime_error("Critical error");
    }
}
```

### 6.2 何时使用错误码

```cpp
// 使用错误码的情况：
// 1. 错误是正常情况的一部分
// 2. 性能关键路径
// 3. C 接口

std::error_code open_file(const std::string& path) {
    if (!file_exists(path)) {
        return std::make_error_code(std::errc::no_such_file_or_directory);
    }
    return {};
}
```

## 7. 异常规范

### 7.1 使用 noexcept

```cpp
// 好的：标记不抛出异常的函数
void swap(Container& a, Container& b) noexcept {
    std::swap(a.data_, b.data_);
}

// 不好的：不标记
void swap(Container& a, Container& b) {
    std::swap(a.data_, b.data_);  // 应该标记 noexcept
}
```

### 7.2 避免动态异常规范

```cpp
// 好的：不使用动态异常规范
void process();  // 可以抛出任何异常

// 不好：动态异常规范（已废弃）
void process() throw(std::runtime_error);  // C++11 已废弃
```

## 8. 错误处理模式

### 8.1 RAII 与异常安全

```cpp
// 好的：RAII 保证异常安全
void process() {
    std::lock_guard<std::mutex> lock(mtx);
    // 即使抛出异常，锁也会被释放
    risky_operation();
}
```

### 8.2 异常安全的赋值

```cpp
// 好的：异常安全的赋值
class Container {
private:
    std::vector<int> data_;
public:
    Container& operator=(const Container& other) {
        if (this != &other) {
            Container temp(other);  // 先构造临时对象
            swap(temp);  // 再交换（不抛出）
        }
        return *this;
    }
};
```

## 9. 最佳实践

### 9.1 错误处理检查清单

1. **使用异常表示错误**
2. **异常应该表示异常情况**
3. **不要忽略异常**
4. **提供异常安全保证**
5. **使用 noexcept 标记不抛出异常的函数**
6. **在性能关键路径考虑错误码**

### 9.2 常见错误

```cpp
// 错误 1：忽略异常
try {
    process();
} catch (...) {
    // 忽略
}

// 错误 2：正常情况使用异常
bool check() {
    try {
        process();
        return true;
    } catch (...) {
        return false;
    }
}

// 错误 3：不标记 noexcept
void swap(Container& a, Container& b) {
    std::swap(a.data_, b.data_);  // 应该标记 noexcept
}
```

## 11. 实际工程案例

### 11.1 案例：模板设计改进

**问题**：模板过度泛化，难以使用

```cpp
// 原始代码：过度泛化
template<typename Container, typename Compare, typename Transform>
void process_anything(Container& c, Compare comp, Transform trans) {
    // 太泛化，难以使用和理解
}
```

**改进**：适度泛化，提供清晰的接口

```cpp
// 改进代码：适度泛化
template<typename T>
void sort(std::vector<T>& vec) {
    std::sort(vec.begin(), vec.end());
}

template<typename T, typename Compare>
void sort(std::vector<T>& vec, Compare comp) {
    std::sort(vec.begin(), vec.end(), comp);
}
```

### 11.2 案例：错误处理改进

**问题**：使用错误码，容易忽略错误

```cpp
// 原始代码：错误码
int process() {
    if (error1) return -1;
    if (error2) return -2;
    return 0;
}

// 调用者可能忽略错误
int result = process();
// 没有检查 result
```

**改进**：使用异常

```cpp
// 改进代码：异常
void process() {
    if (error1) throw std::runtime_error("Error 1");
    if (error2) throw std::invalid_argument("Error 2");
}

// 调用者必须处理异常
try {
    process();
} catch (const std::exception& e) {
    handle_error(e);
}
```

## 12. 模板设计模式

### 12.1 SFINAE 模式


### 12.2 类型萃取模式


## 13. 异常安全保证层次

### 13.1 异常安全保证


### 13.2 异常安全实现

```cpp
// 基本保证：程序处于有效状态
void basic_guarantee(Container& c) {
    c.push_back(value);  // 如果失败，c 状态不变
}

// 强保证：完全回滚
void strong_guarantee(Container& c, const Value& v) {
    auto backup = c;  // 备份
    try {
        c.push_back(v);
    } catch (...) {
        c = backup;  // 恢复
        throw;
    }
}

// 不抛出保证：不抛出异常
void no_throw() noexcept {
    // 保证不抛出异常
}
```

## 14. 最佳实践检查清单

### 14.1 模板设计检查清单

1. **使用概念约束（C++20）**
2. **提供清晰的错误信息**
3. **避免过度泛化**
4. **使用特化优化特定类型**
5. **使用折叠表达式（C++17）**
6. **使用完美转发**

### 14.2 错误处理检查清单

1. **使用异常表示错误**
2. **异常应该表示异常情况**
3. **不要忽略异常**
4. **提供异常安全保证**
5. **使用 noexcept 标记不抛出异常的函数**
6. **在性能关键路径考虑错误码**

## 15. 小结

模板编程和错误处理需要遵循正确的原则和模式。

**核心要点**：
- **模板设计**：使用概念约束、提供清晰错误信息、避免过度泛化
- **模板特化**：优化特定类型、避免不必要的特化
- **可变参数模板**：使用折叠表达式、完美转发
- **错误处理策略**：使用异常表示错误、异常表示异常情况
- **异常安全保证**：基本保证、强保证、不抛出保证
- **异常规范**：使用 noexcept、避免动态异常规范
- **错误处理模式**：RAII 与异常安全、异常安全的赋值

遵循这些规范，可以写出更健壮、更易维护的 C++ 代码。
