---
layout: single
title: "C++ Core Guidelines 阅读笔记（4）：表达式与语句"
series: cpp
permalink: /cpp-guidelines-004-expressions-statements/
tags: [C++, 编程语言, C++ Core Guidelines]
---

## 前言

本文是 C++ Core Guidelines 阅读笔记的第四篇，重点讨论表达式和语句的使用规范。正确的表达式和语句使用可以提高代码的可读性和安全性。

## 1. 表达式设计

表达式是代码的基本单元，良好的表达式设计提高代码可读性和安全性。

### 1.1 优先使用标准库算法

标准库算法经过优化，通常比自己手写的循环更高效、更安全：

```cpp
// 好的：使用标准库算法
auto it = std::find(vec.begin(), vec.end(), value);
if (it != vec.end()) {
    process(*it);
}

// 不好：手写循环
for (auto it = vec.begin(); it != vec.end(); ++it) {
    if (*it == value) {
        process(*it);
        break;
    }
}
```

### 1.2 避免复杂的表达式

复杂表达式难以理解和维护，应该拆分为多个简单表达式：

```cpp
// 好的：简单表达式
bool condition1 = check_condition1();
bool condition2 = check_condition2();
bool is_valid = condition1 && condition2;

// 不好：复杂表达式
bool is_valid = (a > b && c < d) || (e == f && g != h) && (i > j);
// 难以理解，容易出错
```

### 1.3 使用括号明确优先级

即使运算符优先级明确，使用括号也能提高可读性：

```cpp
// 好的：使用括号
if ((a > b) && (c < d)) {
    // 优先级明确
}

// 不好：依赖运算符优先级
if (a > b && c < d) {  
    // 虽然正确，但需要记住优先级
}
```

## 2. 语句设计

### 2.1 优先使用范围 for

```cpp
// 好的：范围 for
for (const auto& item : container) {
    process(item);
}

// 不好：传统 for 循环
for (auto it = container.begin(); it != container.end(); ++it) {
    process(*it);
}
```

### 2.2 避免 goto

```cpp
// 好的：使用结构化控制流
void process() {
    if (error) {
        return;
    }
    // 继续处理
}

// 不好：使用 goto
void process() {
    if (error) {
        goto cleanup;
    }
cleanup:
    // 清理
}
```

### 2.3 使用 switch 而非长 if-else

```cpp
// 好的：switch
switch (value) {
    case 1: return "one";
    case 2: return "two";
    default: return "unknown";
}

// 不好：长 if-else
if (value == 1) return "one";
else if (value == 2) return "two";
else return "unknown";
```

## 3. 变量声明

### 3.1 在首次使用前声明

```cpp
// 好的：在使用前声明
void process() {
    // ... 其他代码
    int value = compute_value();  // 在使用前声明
    use(value);
}

// 不好：在函数开头声明所有变量
void process() {
    int value;  // 声明太早
    // ... 很多代码
    value = compute_value();
    use(value);
}
```

### 3.2 初始化变量

```cpp
// 好的：初始化变量
int count = 0;
std::string name;

// 不好：未初始化
int count;  // 未初始化
std::string name;  // 默认构造，但最好明确
```

### 3.3 使用 auto

```cpp
// 好的：使用 auto
auto value = compute_value();
auto it = vec.begin();

// 不好：显式类型（如果类型复杂）
std::vector<int>::iterator it = vec.begin();
```

## 4. 条件语句

### 4.1 使用 if constexpr（C++17）

```cpp
// 好的：if constexpr
template<typename T>
void process(T value) {
    if constexpr (std::is_integral_v<T>) {
        // 编译期分支
    } else {
        // 其他类型
    }
}
```

### 4.2 避免深层嵌套

```cpp
// 好的：早期返回
bool is_valid(const Data& data) {
    if (data.empty()) return false;
    if (data.size() > MAX_SIZE) return false;
    if (!data.check()) return false;
    return true;
}

// 不好：深层嵌套
bool is_valid(const Data& data) {
    if (!data.empty()) {
        if (data.size() <= MAX_SIZE) {
            if (data.check()) {
                return true;
            }
        }
    }
    return false;
}
```

## 5. 循环语句

### 5.1 使用范围 for

```cpp
// 好的：范围 for
for (const auto& item : items) {
    process(item);
}

// 不好：传统 for
for (size_t i = 0; i < items.size(); ++i) {
    process(items[i]);
}
```

### 5.2 避免不必要的循环

```cpp
// 好的：使用算法
bool found = std::any_of(vec.begin(), vec.end(),
                         [](int x) { return x > 10; });

// 不好：手写循环
bool found = false;
for (int x : vec) {
    if (x > 10) {
        found = true;
        break;
    }
}
```

## 6. 异常处理

### 6.1 使用异常表示错误

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

### 6.2 捕获具体异常

```cpp
// 好的：捕获具体异常
try {
    process();
} catch (const std::runtime_error& e) {
    handle_error(e);
} catch (const std::exception& e) {
    handle_generic_error(e);
}

// 不好：捕获所有异常
try {
    process();
} catch (...) {
    // 不知道是什么错误
}
```

## 7. 类型转换

### 7.1 避免 C 风格转换

```cpp
// 好的：使用 C++ 转换
int value = static_cast<int>(double_value);
Base* ptr = dynamic_cast<Derived*>(base_ptr);

// 不好：C 风格转换
int value = (int)double_value;
Base* ptr = (Derived*)base_ptr;
```

### 7.2 使用 const_cast 谨慎

```cpp
// 好的：避免 const_cast
void process(const Data& data) {
    // 不修改 data
}

// 不好：使用 const_cast
void process(const Data& data) {
    const_cast<Data&>(data).modify();  // 危险
}
```

## 8. Lambda 表达式

### 8.1 使用 Lambda 简化代码

```cpp
// 好的：使用 Lambda
std::sort(vec.begin(), vec.end(),
          [](int a, int b) { return a > b; });

// 不好：函数对象
struct Compare {
    bool operator()(int a, int b) const {
        return a > b;
    }
};
std::sort(vec.begin(), vec.end(), Compare());
```

### 8.2 避免过度捕获

```cpp
// 好的：只捕获需要的变量
int threshold = 10;
std::count_if(vec.begin(), vec.end(),
              [threshold](int x) { return x > threshold; });

// 不好：捕获所有
std::count_if(vec.begin(), vec.end(),
              [&](int x) { return x > threshold; });  // 捕获所有引用
```

## 9. 性能考虑

### 9.1 避免不必要的拷贝

```cpp
// 好的：使用引用
void process(const std::vector<int>& vec);

// 不好：值传递
void process(std::vector<int> vec);  // 拷贝开销
```

### 9.2 使用移动语义

```cpp
// 好的：移动语义
std::vector<int> create_data() {
    std::vector<int> data;
    // ...
    return data;  // 移动
}

// 不好：拷贝
std::vector<int> data = create_data();  // 可能拷贝
```

## 11. 实际工程案例

### 11.1 案例：表达式简化

**问题**：复杂表达式难以理解

```cpp
// 原始代码：复杂表达式
if ((a > b && c < d) || (e == f && g != h) && (i > j)) {
    process();
}
```

**改进**：拆分为简单表达式

```cpp
// 改进代码：简单表达式
bool condition1 = (a > b) && (c < d);
bool condition2 = (e == f) && (g != h);
bool condition3 = (i > j);
bool is_valid = condition1 || (condition2 && condition3);
if (is_valid) {
    process();
}
```

### 11.2 案例：循环优化

**问题**：手写循环容易出错

```cpp
// 原始代码：手写循环
for (size_t i = 0; i < vec.size(); ++i) {
    if (vec[i] > threshold) {
        result.push_back(vec[i]);
    }
}
```

**改进**：使用标准库算法

```cpp
// 改进代码：标准库算法
std::copy_if(vec.begin(), vec.end(), std::back_inserter(result),
             [threshold](int x) { return x > threshold; });
```

## 12. 设计模式应用

### 12.1 策略模式在表达式中的应用


## 13. 性能考虑

### 13.1 表达式求值的性能


### 13.2 循环性能对比

```cpp
// 性能测试
void benchmark() {
    std::vector<int> vec(1000000);
    
    // 范围 for
    auto start = std::chrono::high_resolution_clock::now();
    for (const auto& x : vec) {
        process(x);
    }
    auto end = std::chrono::high_resolution_clock::now();
    
    // 标准库算法
    start = std::chrono::high_resolution_clock::now();
    std::for_each(vec.begin(), vec.end(), process);
    end = std::chrono::high_resolution_clock::now();
    // 通常性能相同，但算法更安全
}
```

## 14. 最佳实践检查清单

### 14.1 表达式设计检查清单

1. **优先使用标准库算法**
2. **避免复杂表达式**
3. **使用括号明确优先级**
4. **使用范围 for 循环**
5. **避免 goto**
6. **在使用前声明变量**
7. **初始化所有变量**
8. **使用 auto 简化类型**

## 15. 小结

表达式和语句应该清晰、简洁、安全。

**核心要点**：
- **表达式设计**：优先使用标准库算法、避免复杂表达式、使用括号明确优先级
- **语句设计**：使用范围 for、避免 goto、使用 switch 而非长 if-else
- **变量声明**：在使用前声明、初始化变量、使用 auto
- **条件语句**：使用 if constexpr、避免深层嵌套
- **循环语句**：使用范围 for、避免不必要的循环
- **异常处理**：使用异常表示错误、捕获具体异常
- **类型转换**：避免 C 风格转换、使用 C++ 转换
- **Lambda 表达式**：简化代码、避免过度捕获
- **性能考虑**：避免不必要的拷贝、使用移动语义

遵循这些规范，可以写出更清晰、更安全的 C++ 代码。
