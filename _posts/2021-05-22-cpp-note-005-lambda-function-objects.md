---
layout: single
title: "C++ 笔记：Lambda 表达式与函数对象"
series: cpp
permalink: /cpp-note-005-lambda-function-objects/
tags: [C++, 编程语言]
---

Lambda 表达式是 C++11 引入的匿名函数，让代码更简洁、更灵活，是现代 C++ 编程不可或缺的工具。

![Lambda 表达式：捕获、参数、函数体的完整语法](/images/diagrams/cpp-lambda-syntax.svg)

## 1. Lambda 表达式的基本语法

### 1.1 完整语法结构

Lambda 表达式的完整语法：

```cpp
[捕获列表](参数列表) mutable exception -> 返回类型 { 函数体 }
```

**各部分说明**：
- **捕获列表**：指定如何捕获外部变量
- **参数列表**：函数参数（可省略）
- **mutable**：允许修改按值捕获的变量（可省略）
- **exception**：异常规范（可省略）
- **返回类型**：返回类型（可省略，编译器自动推导）
- **函数体**：函数实现

### 1.2 简单示例

```cpp
// 最简单的 lambda
auto lambda1 = []() { return 42; };

// 带参数的 lambda
auto lambda2 = [](int x, int y) { return x + y; };

// 带返回类型的 lambda
auto lambda3 = [](int x) -> int { return x * 2; };

// 使用
int result1 = lambda1();        // 42
int result2 = lambda2(3, 4);    // 7
int result3 = lambda3(5);       // 10
```

### 1.3 Lambda 的类型

每个 lambda 表达式都有**唯一的类型**，无法直接命名：

```cpp
auto lambda1 = []() { return 1; };
auto lambda2 = []() { return 2; };

// lambda1 和 lambda2 的类型不同，即使实现相同
// decltype(lambda1) 和 decltype(lambda2) 是不同的类型
```

## 2. 捕获列表详解

### 2.1 值捕获（Capture by Value）

```cpp
int a = 10;
int b = 20;

// 值捕获：捕获时复制变量的值
auto f1 = [a, b]() {
    return a + b;  // 使用捕获的副本
};

a = 100;  // 修改原变量
int result = f1();  // 仍然是 30（使用捕获时的值）
```

**特点**：
- 捕获时复制变量的值
- Lambda 内部修改不影响外部变量
- 需要 `mutable` 关键字才能修改捕获的副本

### 2.2 引用捕获（Capture by Reference）

```cpp
int a = 10;
int b = 20;

// 引用捕获：捕获变量的引用
auto f2 = [&a, &b]() {
    a++;  // 修改外部变量
    b++;
};

f2();
// a = 11, b = 21
```

**特点**：
- 捕获变量的引用
- Lambda 内部修改会影响外部变量
- 需要确保被捕获的变量在 lambda 使用时仍然有效

### 2.3 混合捕获

```cpp
int a = 10;
int b = 20;
int c = 30;

// 混合捕获：部分值捕获，部分引用捕获
auto f = [a, &b, c]() {
    // a 和 c 是值捕获
    // b 是引用捕获
    return a + b + c;
};
```

### 2.4 隐式捕获

```cpp
int a = 10;
int b = 20;

// 捕获所有变量（值捕获）
auto f1 = [=]() {
    return a + b;  // 捕获所有外部变量（值）
};

// 捕获所有变量（引用捕获）
auto f2 = [&]() {
    a++;  // 捕获所有外部变量（引用）
    b++;
};

// 混合：部分显式，部分隐式
auto f3 = [=, &a]() {
    // a 是引用捕获，其他变量是值捕获
};

auto f4 = [&, a]() {
    // a 是值捕获，其他变量是引用捕获
};
```

### 2.5 通用捕获（C++14）

C++14 引入了通用捕获（generalized capture），允许在捕获时初始化：

```cpp
int x = 10;

// 通用捕获：在捕获时初始化
auto f1 = [x = x + 1]() {
    return x;  // x = 11
};

// 移动捕获
auto ptr = std::make_unique<int>(42);
auto f2 = [p = std::move(ptr)]() {
    return *p;  // 移动捕获 unique_ptr
};
```

### 2.6 捕获 this 指针

```cpp
class MyClass {
private:
    int value_ = 42;
    
public:
    void method() {
        // 捕获 this，访问成员变量
        auto lambda = [this]() {
            return value_;  // 通过 this 访问
        };
        
        // 或使用 [=] 隐式捕获 this（C++17 之前）
        auto lambda2 = [=]() {
            return value_;  // 隐式捕获 this
        };
        
        // C++17：[*this] 按值捕获整个对象
        auto lambda3 = [*this]() {
            return value_;  // 捕获对象的副本
        };
    }
};
```

## 3. Lambda 与 STL 算法

### 3.1 作为谓词（Predicate）

```cpp
std::vector<int> v = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

// 移除偶数
v.erase(
    std::remove_if(v.begin(), v.end(), [](int x) {
        return x % 2 == 0;
    }),
    v.end()
);

// 查找大于 5 的元素
auto it = std::find_if(v.begin(), v.end(), [](int x) {
    return x > 5;
});
```

### 3.2 作为比较函数

```cpp
std::vector<std::string> words = {"hello", "world", "cpp", "lambda"};

// 按长度排序
std::sort(words.begin(), words.end(), [](const std::string& a, const std::string& b) {
    return a.length() < b.length();
});

// 按长度降序，长度相同按字典序
std::sort(words.begin(), words.end(), [](const std::string& a, const std::string& b) {
    if (a.length() != b.length()) {
        return a.length() > b.length();
    }
    return a < b;
});
```

### 3.3 作为转换函数

```cpp
std::vector<int> numbers = {1, 2, 3, 4, 5};

// 转换为字符串
std::vector<std::string> strings;
std::transform(numbers.begin(), numbers.end(), 
               std::back_inserter(strings),
               [](int n) {
                   return std::to_string(n);
               });

// 计算平方
std::vector<int> squares;
std::transform(numbers.begin(), numbers.end(),
               std::back_inserter(squares),
               [](int n) { return n * n; });
```

### 3.4 捕获外部变量

```cpp
int threshold = 5;
std::vector<int> v = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

// 计数大于 threshold 的元素
int count = std::count_if(v.begin(), v.end(), [threshold](int x) {
    return x > threshold;
});

// 或使用引用捕获
int sum = 0;
std::for_each(v.begin(), v.end(), [&sum](int x) {
    sum += x;  // 修改外部变量
});
```

## 4. Lambda 的实现原理

### 4.1 Lambda 是函数对象

Lambda 表达式实际上是一个**函数对象**（functor）：

```cpp
// Lambda
auto lambda = [](int x, int y) { return x + y; };

// 编译器生成的等价代码
struct Lambda {
    int operator()(int x, int y) const {
        return x + y;
    }
};
```

### 4.2 捕获变量的实现

```cpp
int a = 10;
int b = 20;

// Lambda 值捕获
auto lambda = [a, b]() { return a + b; };

// 编译器生成的等价代码
struct Lambda {
    int a_;  // 值捕获的变量成为成员变量
    int b_;
    
    Lambda(int a, int b) : a_(a), b_(b) {}
    
    int operator()() const {
        return a_ + b_;
    }
};
```

### 4.3 引用捕获的实现

```cpp
int a = 10;

// Lambda 引用捕获
auto lambda = [&a]() { a++; };

// 编译器生成的等价代码
struct Lambda {
    int& a_;  // 引用捕获的变量成为引用成员
    
    Lambda(int& a) : a_(a) {}
    
    void operator()() {
        a_++;  // 修改引用
    }
};
```

### 4.4 mutable 关键字

```cpp
int x = 10;

// 值捕获，但需要修改捕获的副本
auto lambda = [x]() mutable {
    x++;  // 修改捕获的副本
    return x;
};

// 等价代码
struct Lambda {
    mutable int x_;  // mutable 成员
    
    Lambda(int x) : x_(x) {}
    
    int operator()() {  // 非 const operator()
        x_++;
        return x_;
    }
};
```

## 5. 函数对象（Function Object）

### 5.1 什么是函数对象

函数对象是重载了 `operator()` 的类，可以像函数一样调用：

```cpp
struct Add {
    int operator()(int a, int b) const {
        return a + b;
    }
};

Add add;
int result = add(3, 4);  // 7

// 或直接使用
int result2 = Add()(3, 4);  // 7
```

### 5.2 函数对象的优势

函数对象相比普通函数有多个优势：

1. **可以携带状态**：成员变量存储状态
2. **可以模板化**：模板函数对象更灵活
3. **可以内联**：编译器更容易内联

```cpp
// 函数对象可以携带状态
struct Counter {
    int count_ = 0;
    
    int operator()() {
        return ++count_;
    }
};

Counter counter;
counter();  // 1
counter();  // 2
counter();  // 3
```

### 5.3 标准库函数对象

标准库提供了常用的函数对象：

```cpp
#include <functional>

std::plus<int> add;
int result = add(3, 4);  // 7

std::multiplies<int> multiply;
int product = multiply(3, 4);  // 12

std::greater<int> greater;
bool is_greater = greater(5, 3);  // true

// 在算法中使用
std::vector<int> v = {1, 2, 3, 4, 5};
int sum = std::accumulate(v.begin(), v.end(), 0, std::plus<int>());
```

## 6. std::function：类型擦除的可调用对象

### 6.1 std::function 的基本使用

`std::function` 可以存储任何可调用对象：

```cpp
#include <functional>

std::function<int(int, int)> func;

// 存储 lambda
func = [](int a, int b) { return a + b; };
int result1 = func(3, 4);  // 7

// 存储函数对象
func = std::plus<int>();
int result2 = func(3, 4);  // 7

// 存储函数指针
int add_func(int a, int b) { return a + b; }
func = add_func;
int result3 = func(3, 4);  // 7
```

### 6.2 std::function 的类型擦除

`std::function` 使用类型擦除（type erasure）技术：

```cpp
// std::function 的实现原理（简化）
template<typename Signature>
class function {
private:
    // 类型擦除：不关心具体类型，只关心调用签名
    class callable_base {
    public:
        virtual ~callable_base() = default;
        virtual ReturnType invoke(Args...) = 0;
    };
    
    template<typename T>
    class callable_impl : public callable_base {
        T callable_;
    public:
        callable_impl(T c) : callable_(c) {}
        ReturnType invoke(Args... args) override {
            return callable_(args...);
        }
    };
    
    std::unique_ptr<callable_base> callable_;
    
public:
    template<typename T>
    function(T f) : callable_(new callable_impl<T>(f)) {}
    
    ReturnType operator()(Args... args) {
        return callable_->invoke(args...);
    }
};
```

### 6.3 std::function 的性能开销

`std::function` 有类型擦除的开销：

- **内存开销**：需要存储函数对象和虚函数表
- **时间开销**：虚函数调用，可能无法内联
- **分配开销**：可能需要堆分配

```cpp
// 性能对比
auto lambda = [](int x) { return x * 2; };
std::function<int(int)> func = lambda;

// lambda 可以内联，性能最优
int result1 = lambda(42);

// func 有虚函数调用开销，可能无法内联
int result2 = func(42);
```

### 6.4 何时使用 std::function

**适合使用**：
- 需要存储不同类型的可调用对象
- 需要延迟绑定函数
- 回调函数需要统一接口

**不适合使用**：
- 性能关键路径
- 可以确定具体类型时
- 需要内联优化时

## 7. Lambda 的高级特性

### 7.1 递归 Lambda（C++14）

```cpp
// 递归 lambda：需要显式指定类型
auto factorial = [](int n) {
    auto impl = [](int n, auto& self) -> int {
        return n <= 1 ? 1 : n * self(n - 1, self);
    };
    return impl(n, impl);
};

int result = factorial(5);  // 120
```

### 7.2 立即调用的 Lambda（IIFE）

```cpp
// IIFE：Immediately Invoked Function Expression
int result = [](int x, int y) {
    // 复杂计算
    int sum = x + y;
    int product = x * y;
    return sum + product;
}(3, 4);  // 立即调用

// 用途：创建作用域，避免变量污染
auto value = []() {
    int temp = compute_complex_value();
    return process(temp);
}();
```

### 7.3 Lambda 作为返回值

```cpp
// 返回 lambda
auto make_adder(int increment) {
    return [increment](int x) {
        return x + increment;
    };
}

auto add5 = make_adder(5);
int result = add5(10);  // 15
```

### 7.4 Lambda 作为模板参数

```cpp
template<typename Func>
void call_twice(Func f) {
    f();
    f();
}

call_twice([]() {
    std::cout << "Hello\n";
});
```

## 8. Lambda 的性能考虑

### 8.1 内联优化

Lambda 通常可以被完全内联：

```cpp
std::vector<int> v = {1, 2, 3, 4, 5};

// Lambda 可以内联
std::for_each(v.begin(), v.end(), [](int x) {
    std::cout << x << "\n";
});

// 等价的手写循环也可以内联
for (int x : v) {
    std::cout << x << "\n";
}
```

### 8.2 捕获开销

```cpp
// 值捕获：复制变量
int large_array[1000];
auto lambda1 = [large_array]() { /* 使用数组 */ };
// 开销：复制 1000 个元素

// 引用捕获：只复制引用
auto lambda2 = [&large_array]() { /* 使用数组 */ };
// 开销：只复制一个指针

// 移动捕获：转移所有权
auto ptr = std::make_unique<LargeObject>();
auto lambda3 = [p = std::move(ptr)]() { /* 使用对象 */ };
// 开销：只移动指针
```

### 8.3 std::function 的性能

```cpp
// 性能对比
auto lambda = [](int x) { return x * 2; };
std::function<int(int)> func = lambda;

// 热路径：避免 std::function
void hot_path() {
    for (int i = 0; i < 1000000; ++i) {
        lambda(i);  // 可以内联
        // func(i);  // 有虚函数调用开销
    }
}
```

## 9. Lambda 的常见陷阱

### 9.1 悬空引用

```cpp
// 错误：捕获悬空引用
std::function<int()> create_lambda() {
    int x = 42;
    return [&x]() { return x; };  // x 在函数返回后失效
}

auto lambda = create_lambda();
int result = lambda();  // 未定义行为
```

**解决**：使用值捕获或确保引用的生命周期

```cpp
// 正确：值捕获
std::function<int()> create_lambda() {
    int x = 42;
    return [x]() { return x; };  // 值捕获，安全
}
```

### 9.2 循环中的捕获

```cpp
// 错误：所有 lambda 捕获同一个引用
std::vector<std::function<void()>> funcs;
for (int i = 0; i < 10; ++i) {
    funcs.push_back([&i]() { std::cout << i << "\n"; });
    // 所有 lambda 都捕获 i 的引用，最终 i = 10
}

// 正确：值捕获
for (int i = 0; i < 10; ++i) {
    funcs.push_back([i]() { std::cout << i << "\n"; });
    // 每个 lambda 捕获 i 的副本
}
```

### 9.3 mutable 的误用

```cpp
int x = 10;

// mutable 只影响捕获的副本，不影响外部变量
auto lambda = [x]() mutable {
    x++;  // 只修改副本
    return x;
};

lambda();  // 返回 11
// x 仍然是 10（外部变量未改变）
```

## 10. 工程实践建议

### 10.1 Lambda 使用检查清单

1. **优先使用 Lambda**：代码更简洁，通常性能更好
2. **明确捕获方式**：值捕获 vs 引用捕获
3. **避免悬空引用**：确保捕获的引用有效
4. **避免不必要的 std::function**：在可能的情况下使用 auto
5. **注意循环中的捕获**：使用值捕获避免引用问题

### 10.2 性能优化建议

- **优先使用 Lambda**：通常可以内联，性能最优
- **避免 std::function**：在性能关键路径避免使用
- **合理选择捕获方式**：大对象使用引用或移动捕获
- **使用 constexpr lambda（C++17）**：编译期计算

### 10.3 代码可读性

- **保持 Lambda 简短**：复杂逻辑提取为函数
- **使用有意义的捕获**：显式列出捕获的变量
- **添加注释**：复杂的 Lambda 需要注释说明

## 11. 小结

Lambda 表达式是现代 C++ 编程的核心特性，它让代码更简洁、更灵活，同时保持了优秀的性能。

**关键要点**：
- Lambda 是匿名函数对象，每个 Lambda 有唯一类型
- 捕获列表控制如何访问外部变量（值捕获、引用捕获、混合捕获）
- Lambda 通常可以内联，性能与函数对象相当
- `std::function` 提供类型擦除，但有性能开销
- 避免悬空引用和循环中的捕获陷阱
- Lambda 是现代 C++ 编程不可或缺的工具

理解和正确使用 Lambda 表达式，是写出现代、高效、易维护的 C++ 代码的关键。
