---
layout: single
title: "C++ Core Guidelines 阅读笔记（2）：函数与类设计"
series: cpp
permalink: /cpp-guidelines-002-functions-classes/
tags: [C++, 编程语言, C++ Core Guidelines]
---

## 前言

本文是 C++ Core Guidelines 阅读笔记的第二篇，重点讨论函数设计和类设计的规范。良好的函数和类设计是写出高质量 C++ 代码的基础。

## 1. 函数设计规范

函数是程序的基本构建块，良好的函数设计是高质量代码的基础。

### 1.1 函数应该简短

函数应该足够短，能够一眼理解其功能：

```cpp
// 好的：简短函数
bool is_valid_email(const std::string& email) {
    return email.find('@') != std::string::npos &&
           email.find('.') != std::string::npos;
}

// 不好：过长函数（超过 50 行）
void process_order(Order& order) {
    // 100+ 行代码，难以理解和维护
    // 包含多个职责，难以测试
}
```

### 1.2 函数应该做一件事

单一职责原则适用于函数设计：

```cpp
// 好的：单一职责
void validate_user(const User& user);
void save_user(const User& user);
void notify_user(const User& user);

// 不好：做多件事
void validate_and_save_user(User& user) {
    validate_user(user);  // 职责 1
    save_user(user);      // 职责 2
    notify_user(user);    // 职责 3
    // 违反单一职责，难以测试和维护
}
```

### 1.3 函数参数数量

函数参数应该尽可能少，通常不超过 3 个：

```cpp
// 好的：参数少（1-3 个）
void draw_circle(const Point& center, double radius);
void process(int x, int y, int z);  // 3 个参数，可接受

// 不好：参数太多
void draw_shape(double x, double y, double w, double h, 
                Color c, Style s, int z);  // 7 个参数，太多
```

### 1.4 使用结构体传递多个参数

当参数较多时，使用结构体封装：

```cpp
// 好的：使用结构体
struct DrawParams {
    Point center;
    double radius;
    Color color;
    Style style;
    int z_order;
};

void draw_circle(const DrawParams& params);
// 使用：DrawParams params{center, 10.0, Color::Red, Style::Solid, 0};
//       draw_circle(params);

// 不好：多个参数
void draw_circle(double x, double y, double r, Color c, Style s, int z);
// 使用：draw_circle(10, 20, 5.0, Color::Red, Style::Solid, 0);
//      容易传错参数顺序
```

## 2. 函数参数传递

### 2.1 参数传递规则

```cpp
// 小对象（< 3 words）：值传递
void process(int x, double y);

// 大对象：const 引用传递
void process(const std::vector<int>& vec);

// 需要修改：非 const 引用传递
void modify(std::vector<int>& vec);

// 移动语义：右值引用传递
void take_ownership(std::vector<int>&& vec);
```

### 2.2 避免输出参数

```cpp
// 好的：返回值
std::vector<int> compute_result();

// 不好：输出参数
void compute_result(std::vector<int>& out);
```

### 2.3 使用默认参数

```cpp
// 好的：默认参数
void draw_circle(const Point& center, double radius = 1.0,
                 Color color = Color::Black);

// 不好：函数重载（如果只是参数不同）
void draw_circle(const Point& center);
void draw_circle(const Point& center, double radius);
void draw_circle(const Point& center, double radius, Color color);
```

## 3. 类设计原则

类是面向对象编程的核心，良好的类设计遵循特定的原则。

### 3.1 类应该表示一个概念

类应该表示一个清晰的概念或实体：

```cpp
// 好的：表示一个概念
class Circle {
private:
    Point center_;
    double radius_;
public:
    void draw() const;
    double area() const;
    double circumference() const;
    // 所有操作都与 Circle 概念相关
};

// 不好：不表示一个概念
class Utility {  // 工具类，没有明确概念
public:
    static void func1();  // 功能 1
    static void func2();  // 功能 2
    static void func3();  // 功能 3
    // 没有统一的概念，只是函数的集合
};
```

### 3.2 保持类小而专注

类应该小而专注，遵循单一职责原则：

```cpp
// 好的：小而专注
class FileReader {
public:
    std::string read(const std::string& path);
    // 只负责读取文件
};

class FileWriter {
public:
    void write(const std::string& path, const std::string& content);
    // 只负责写入文件
};

// 不好：类太大
class FileManager {  // 包含太多功能
public:
    void read();      // 职责 1：读取
    void write();     // 职责 2：写入
    void compress();  // 职责 3：压缩
    void encrypt();   // 职责 4：加密
    void delete_file();  // 职责 5：删除
    // 违反单一职责原则
};
```

### 3.3 使用组合而非继承

优先使用组合而非继承，除非是真正的 is-a 关系：

```cpp
// 好的：组合
class Car {
private:
    Engine engine_;      // 组合：Car has an Engine
    Wheel wheels_[4];    // 组合：Car has Wheels
    Transmission transmission_;  // 组合：Car has a Transmission
};

// 不好：不必要的继承
class Car : public Vehicle {  // 如果不是真正的 is-a 关系
    // 继承会带来不必要的耦合
};
```

### 3.4 类的职责划分


## 4. 数据封装

### 4.1 数据应该是私有的

```cpp
// 好的：数据私有
class Point {
private:
    double x_, y_;
public:
    double x() const { return x_; }
    double y() const { return y_; }
    void set_x(double x) { x_ = x; }
    void set_y(double y) { y_ = y; }
};

// 不好：数据公有
class Point {
public:
    double x, y;  // 公有数据
};
```

### 4.2 提供访问器

```cpp
// 好的：提供访问器
class User {
private:
    std::string name_;
public:
    const std::string& name() const { return name_; }
    void set_name(const std::string& name) { name_ = name; }
};
```

## 5. 构造函数

### 5.1 使用构造函数初始化列表

```cpp
// 好的：初始化列表
class MyClass {
private:
    int value_;
    std::string name_;
public:
    MyClass(int v, const std::string& n) 
        : value_(v), name_(n) {}
};

// 不好：在构造函数体内赋值
MyClass(int v, const std::string& n) {
    value_ = v;  // 先默认构造，再赋值
    name_ = n;
}
```

### 5.2 使用 = default 和 = delete

```cpp
class MyClass {
public:
    MyClass() = default;  // 使用默认构造函数
    MyClass(const MyClass&) = delete;  // 禁止拷贝
    MyClass& operator=(const MyClass&) = delete;
    MyClass(MyClass&&) = default;  // 允许移动
    MyClass& operator=(MyClass&&) = default;
};
```

## 6. 析构函数

### 6.1 基类应该有虚析构函数

```cpp
// 好的：虚析构函数
class Base {
public:
    virtual ~Base() = default;
};

// 不好：非虚析构函数
class Base {
public:
    ~Base() {}  // 如果 Base 会被继承，应该是虚的
};
```

### 6.2 析构函数应该简单

```cpp
// 好的：简单析构函数
class MyClass {
    std::unique_ptr<Resource> resource_;
public:
    ~MyClass() = default;  // 自动清理
};

// 不好：复杂析构函数
~MyClass() {
    // 大量清理逻辑
    // 可能抛出异常
}
```

## 7. 运算符重载

### 7.1 保持语义一致性

```cpp
// 好的：语义一致
class Complex {
public:
    Complex operator+(const Complex& other) const;
    Complex& operator+=(const Complex& other);
};

// 通常实现为：
Complex operator+(const Complex& a, const Complex& b) {
    Complex result = a;
    result += b;  // 复用 +=
    return result;
}
```

### 7.2 避免过度重载

```cpp
// 好的：只重载有意义的运算符
class Vector {
public:
    Vector operator+(const Vector& other) const;
    Vector& operator+=(const Vector& other);
};

// 不好：重载不常用的运算符
Vector operator%(const Vector& other) const;  // % 对向量没有意义
```

## 8. 继承设计

### 8.1 使用 public 继承表示 is-a 关系

```cpp
// 好的：is-a 关系
class Circle : public Shape {
    // Circle is a Shape
};

// 不好：不是 is-a 关系
class Stack : public std::vector<int> {  // Stack is not a vector
};
```

### 8.2 避免深继承层次

```cpp
// 好的：浅继承层次
class Base {};
class Derived : public Base {};

// 不好：深继承层次
class Base {};
class Derived1 : public Base {};
class Derived2 : public Derived1 {};
class Derived3 : public Derived2 {};  // 太深
```

## 9. 接口设计

### 9.1 接口应该稳定

```cpp
// 好的：稳定接口
class Database {
public:
    virtual void connect() = 0;
    virtual void disconnect() = 0;
    virtual ~Database() = default;
};

// 不好：频繁变化的接口
class Database {
public:
    virtual void connect_v2() = 0;  // 版本号在接口中
};
```

### 9.2 使用抽象接口

```cpp
// 好的：抽象接口
class Drawable {
public:
    virtual void draw() const = 0;
    virtual ~Drawable() = default;
};

// 不好：具体实现
class Circle {
public:
    void draw() const {
        // 具体实现
    }
};
```

## 11. 实际工程案例

### 11.1 案例：函数重构

**问题**：函数过长，难以维护

```cpp
// 原始代码：100+ 行
void process_order(Order& order) {
    // 验证订单
    if (order.items.empty()) {
        // ...
    }
    // 计算价格
    // 应用折扣
    // 更新库存
    // 发送通知
    // ...
}
```

**改进**：拆分为多个小函数

```cpp
// 改进代码：每个函数职责单一
void validate_order(const Order& order);
Price calculate_price(const Order& order);
void apply_discount(Order& order);
void update_inventory(const Order& order);
void send_notification(const Order& order);

void process_order(Order& order) {
    validate_order(order);
    calculate_price(order);
    apply_discount(order);
    update_inventory(order);
    send_notification(order);
}
```

### 11.2 案例：类设计改进

**问题**：类太大，职责不清

```cpp
// 原始设计：God Object
class UserManager {
    // 用户管理
    // 权限管理
    // 通知管理
    // 日志管理
    // ...
};
```

**改进**：拆分为多个小类

```cpp
// 改进设计：职责分离
class User {
    // 用户数据和行为
};

class PermissionManager {
    // 权限管理
};

class NotificationService {
    // 通知服务
};

class Logger {
    // 日志管理
};
```

## 12. 设计模式应用

### 12.1 策略模式


### 12.2 模板方法模式

```cpp
// 模板方法模式
class Algorithm {
public:
    void run() {
        step1();
        step2();  // 虚函数，子类可以重写
        step3();
    }
protected:
    virtual void step2() = 0;
private:
    void step1() {}
    void step3() {}
};
```

## 13. 性能考虑

### 13.1 函数调用开销


### 13.2 类设计对性能的影响

```cpp
// 好的：数据局部性好
class Point {
    double x_, y_;  // 数据紧凑
};

// 不好：数据分散
class Point {
    std::unique_ptr<double> x_;  // 间接访问
    std::unique_ptr<double> y_;
};
```

## 14. 最佳实践检查清单

### 14.1 函数设计检查清单

1. **函数简短**：< 50 行
2. **单一职责**：只做一件事
3. **参数少**：< 4 个参数
4. **命名清晰**：表达意图
5. **无副作用**：纯函数更好
6. **异常安全**：正确处理异常

### 14.2 类设计检查清单

1. **表示一个概念**：有明确的语义
2. **小而专注**：< 500 行
3. **单一职责**：只负责一件事
4. **数据私有**：封装数据
5. **接口稳定**：避免频繁变化
6. **使用组合**：优先组合而非继承

## 15. 小结

函数和类的设计应该遵循单一职责、小而专注的原则。

**核心要点**：
- **函数设计**：简短、单一职责、参数少、使用结构体传递多个参数
- **参数传递**：根据对象大小和用途选择传递方式
- **类设计**：表示一个概念、小而专注、使用组合
- **数据封装**：数据私有、提供访问器
- **构造函数**：使用初始化列表、= default/= delete
- **析构函数**：基类虚析构、简单实现
- **运算符重载**：保持语义一致性、避免过度重载
- **继承设计**：public 继承表示 is-a、避免深层次
- **接口设计**：稳定、抽象接口

遵循这些规范，可以设计出更清晰、更易维护的 C++ 代码。
