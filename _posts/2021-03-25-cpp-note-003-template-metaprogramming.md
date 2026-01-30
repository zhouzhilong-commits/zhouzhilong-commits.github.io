---
layout: single
title: "C++ 笔记：模板元编程基础"
series: cpp
permalink: /cpp-note-003-template-metaprogramming/
tags: [C++, 编程语言]
---

模板元编程（Template Metaprogramming, TMP）是在编译期进行计算和类型操作的强大技术，是 C++ 最复杂也最强大的特性之一。

![模板元编程：编译期计算与类型操作](/images/diagrams/cpp-template-metaprogramming.svg)

## 1. 什么是模板元编程

### 1.1 定义与历史

模板元编程是在**编译期**执行计算和类型操作的技术，由 Erwin Unruh 在 1994 年意外发现。他发现模板实例化过程实际上是一个图灵完备的计算系统。

### 1.2 基本示例：编译期计算

```cpp
// 编译期计算阶乘
template<int N>
struct Factorial {
    static const int value = N * Factorial<N-1>::value;
};

// 特化：终止条件
template<>
struct Factorial<0> {
    static const int value = 1;
};

// 使用
constexpr int fact5 = Factorial<5>::value;  // 编译期计算，值为 120
```

**关键点**：
- 计算在编译期完成，运行时无开销
- 使用模板特化实现递归终止
- 结果在编译期已知，可以用于常量表达式

### 1.3 模板元编程 vs 运行时编程

| 特性 | 模板元编程 | 运行时编程 |
|------|-----------|-----------|
| 执行时机 | 编译期 | 运行期 |
| 性能开销 | 零开销 | 有开销 |
| 错误发现 | 编译期 | 运行期 |
| 调试难度 | 困难 | 相对容易 |
| 代码可读性 | 较差 | 较好 |

## 2. SFINAE：替换失败不是错误

### 2.1 SFINAE 的基本概念

SFINAE（Substitution Failure Is Not An Error）是模板匹配的核心机制。当模板参数替换失败时，编译器不会报错，而是尝试其他重载。

```cpp
// 版本 1：T 有 method() 时匹配
template<typename T>
auto func(T t) -> decltype(t.method(), void()) {
    t.method();
}

// 版本 2：兜底版本
template<typename T>
void func(T t) {
    // 处理没有 method() 的类型
}

struct HasMethod {
    void method() {}
};

struct NoMethod {};

func(HasMethod{});  // 调用版本 1
func(NoMethod{});   // 调用版本 2
```

### 2.2 SFINAE 的实现技巧

#### 2.2.1 使用 decltype

```cpp
template<typename T>
auto has_size(T t) -> decltype(t.size(), std::true_type{}) {
    return {};
}

template<typename T>
std::false_type has_size(...) {
    return {};
}

// 使用
static_assert(has_size(std::vector<int>{}));
static_assert(!has_size(int{}));
```

#### 2.2.2 使用 std::enable_if

```cpp
template<typename T>
typename std::enable_if<std::is_integral<T>::value, T>::type
add_one(T t) {
    return t + 1;
}

// C++14 简化
template<typename T>
std::enable_if_t<std::is_integral_v<T>, T>
add_one(T t) {
    return t + 1;
}
```

#### 2.2.3 使用 std::void_t（C++17）

```cpp
template<typename T, typename = void>
struct has_type_member : std::false_type {};

template<typename T>
struct has_type_member<T, std::void_t<typename T::type>> : std::true_type {};

// 使用
static_assert(has_type_member<std::vector<int>::value_type>::value);
```

### 2.3 SFINAE 的常见陷阱

```cpp
// 错误：所有替换都失败，没有可用版本
template<typename T>
void func(typename T::type t) {}  // 如果 T 没有 type，替换失败

// 正确：提供兜底版本
template<typename T>
void func(typename T::type t) {}

template<typename T>
void func(T t) {}  // 兜底版本
```

## 3. 类型特征（Type Traits）

### 3.1 标准库类型特征

C++11 提供了丰富的类型特征：

```cpp
#include <type_traits>

// 类型检查
static_assert(std::is_integral<int>::value);
static_assert(!std::is_pointer<int>::value);
static_assert(std::is_same<int, int>::value);

// 类型转换
using IntPtr = std::add_pointer_t<int>;  // int*
using IntRef = std::add_lvalue_reference_t<int>;  // int&
using IntNoRef = std::remove_reference_t<int&>;  // int

// 条件类型
using Result = std::conditional_t<true, int, double>;  // int
```

### 3.2 自定义类型特征

```cpp
// 检查类型是否有 size() 方法
template<typename T>
struct has_size {
private:
    template<typename U>
    static auto test(int) -> decltype(std::declval<U>().size(), std::true_type{});
    
    template<typename>
    static std::false_type test(...);
    
public:
    static const bool value = decltype(test<T>(0))::value;
};

// 使用
static_assert(has_size<std::vector<int>>::value);
static_assert(!has_size<int>::value);
```

### 3.3 类型特征的组合

```cpp
// 检查是否是整数或浮点数
template<typename T>
using is_numeric = std::disjunction<
    std::is_integral<T>,
    std::is_floating_point<T>
>;

// 检查是否可拷贝
template<typename T>
using is_copyable = std::conjunction<
    std::is_copy_constructible<T>,
    std::is_copy_assignable<T>
>;
```

## 4. constexpr 与 if constexpr

### 4.1 constexpr 函数

C++11 的 `constexpr` 允许在编译期计算：

```cpp
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

constexpr int fact5 = factorial(5);  // 编译期计算
```

### 4.2 if constexpr（C++17）

`if constexpr` 在编译期选择分支，简化了模板元编程：

```cpp
template<typename T>
constexpr auto get_value(T t) {
    if constexpr (std::is_pointer_v<T>) {
        return *t;  // 编译期选择，不会编译 else 分支
    } else {
        return t;
    }
}

// 使用
int x = 42;
int* p = &x;
auto v1 = get_value(x);  // 返回 int
auto v2 = get_value(p);  // 返回 int（解引用）
```

### 4.3 constexpr vs 模板元编程

```cpp
// 模板元编程方式（C++11）
template<int N>
struct Factorial {
    static const int value = N * Factorial<N-1>::value;
};

// constexpr 方式（C++11）
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

// constexpr 更简洁，但模板元编程更灵活
```

## 5. 模板特化与偏特化

### 5.1 完全特化

```cpp
template<typename T>
struct IsPointer {
    static const bool value = false;
};

// 完全特化
template<typename T>
struct IsPointer<T*> {
    static const bool value = true;
};

static_assert(!IsPointer<int>::value);
static_assert(IsPointer<int*>::value);
```

### 5.2 偏特化

```cpp
template<typename T, typename U>
struct IsSame {
    static const bool value = false;
};

// 偏特化：两个类型相同时
template<typename T>
struct IsSame<T, T> {
    static const bool value = true;
};

static_assert(IsSame<int, int>::value);
static_assert(!IsSame<int, double>::value);
```

### 5.3 递归模板

```cpp
// 计算类型列表的长度
template<typename... Types>
struct TypeListSize {
    static const size_t value = sizeof...(Types);
};

// 使用
static_assert(TypeListSize<int, double, char>::value == 3);
```

## 6. 模板元编程的实际应用

### 6.1 类型萃取（Type Traits）

```cpp
// 提取指针指向的类型
template<typename T>
struct RemovePointer {
    using type = T;
};

template<typename T>
struct RemovePointer<T*> {
    using type = T;
};

template<typename T>
using RemovePointer_t = typename RemovePointer<T>::type;

// 使用
using IntType = RemovePointer_t<int*>;  // int
```

### 6.2 编译期计算

```cpp
// 编译期字符串哈希
template<size_t N>
constexpr size_t hash_string(const char (&str)[N], size_t index = 0) {
    return index >= N - 1 ? 0 : 
           (hash_string(str, index + 1) * 31 + str[index]);
}

constexpr size_t hash = hash_string("hello");  // 编译期计算
```

### 6.3 条件编译

```cpp
// 根据类型选择不同的实现
template<typename T>
void process(T t) {
    if constexpr (std::is_integral_v<T>) {
        // 整数类型的处理
        std::cout << "Integer: " << t << "\n";
    } else if constexpr (std::is_floating_point_v<T>) {
        // 浮点数类型的处理
        std::cout << "Float: " << t << "\n";
    } else {
        // 其他类型
        std::cout << "Other: " << t << "\n";
    }
}
```

### 6.4 类型安全接口

```cpp
// 只接受特定类型的函数
template<typename T>
std::enable_if_t<std::is_arithmetic_v<T>, T>
safe_add(T a, T b) {
    return a + b;
}

// 使用
auto result1 = safe_add(1, 2);      // OK
auto result2 = safe_add(1.5, 2.5);  // OK
// auto result3 = safe_add("a", "b"); // 编译错误
```

## 7. 模板元编程的性能与限制

### 7.1 编译期性能

模板元编程的主要开销在**编译期**：

- **编译时间**：复杂的模板元编程会显著增加编译时间
- **代码膨胀**：每个模板实例化都会生成代码
- **错误信息**：模板错误信息通常难以理解

### 7.2 运行时性能

模板元编程的运行时性能优势：

- **零开销**：计算在编译期完成，运行时无开销
- **内联优化**：编译器可以完全内联模板代码
- **类型特化**：可以为不同类型生成最优代码

### 7.3 调试困难

模板元编程的调试挑战：

- **错误信息复杂**：模板错误信息通常很长很复杂
- **难以单步调试**：编译期计算无法在调试器中查看
- **代码可读性差**：模板元编程代码通常难以理解

## 8. 现代 C++ 的改进

### 8.1 Concepts（C++20）

Concepts 简化了模板约束：

```cpp
// C++20 之前：使用 SFINAE
template<typename T>
std::enable_if_t<std::is_integral_v<T>, T>
add_one(T t) {
    return t + 1;
}

// C++20：使用 Concepts
template<std::integral T>
T add_one(T t) {
    return t + 1;
}
```

### 8.2 变量模板（C++14）

```cpp
// C++11
template<typename T>
struct IsPointer {
    static const bool value = false;
};

// C++14
template<typename T>
constexpr bool IsPointer_v = false;

template<typename T>
constexpr bool IsPointer_v<T*> = true;
```

### 8.3 折叠表达式（C++17）

```cpp
// C++17 之前：需要递归
template<typename... Args>
struct Sum {
    static const int value = 0;
};

template<typename T, typename... Args>
struct Sum<T, Args...> {
    static const int value = T::value + Sum<Args...>::value;
};

// C++17：折叠表达式
template<typename... Args>
constexpr int sum(Args... args) {
    return (args + ...);  // 右折叠
}
```

## 9. 工程实践建议

### 9.1 何时使用模板元编程

**适合使用**：
- 需要编译期计算和类型操作
- 性能关键路径需要零开销抽象
- 需要类型安全的泛型接口

**不适合使用**：
- 简单的运行时逻辑
- 需要频繁修改的代码
- 团队对模板元编程不熟悉

### 9.2 最佳实践

1. **优先使用标准库类型特征**：不要重复造轮子
2. **使用 constexpr 替代简单模板元编程**：代码更简洁
3. **使用 Concepts（C++20）**：简化模板约束
4. **添加清晰的注释**：模板元编程代码需要详细注释
5. **编写单元测试**：确保模板元编程逻辑正确

### 9.3 调试技巧

- **使用 static_assert**：在编译期验证假设
- **简化错误信息**：使用类型别名和辅助函数
- **分步开发**：先实现简单版本，再逐步复杂化
- **使用工具**：如 cppinsights.io 查看模板实例化

## 10. 小结

模板元编程是 C++ 最强大的特性之一，它允许在编译期进行计算和类型操作，实现零开销抽象。虽然学习曲线陡峭，但能带来显著的性能和灵活性提升。

**关键要点**：
- 模板元编程在编译期执行，运行时零开销
- SFINAE 是模板匹配的核心机制
- 类型特征是模板元编程的基础工具
- `constexpr` 和 `if constexpr` 简化了模板元编程
- Concepts（C++20）进一步简化了模板约束
- 模板元编程适合性能关键路径，但会增加编译时间和代码复杂度
- 理解模板元编程是掌握现代 C++ 的关键

合理使用模板元编程，可以在保持性能的同时，实现灵活、类型安全的泛型代码。
