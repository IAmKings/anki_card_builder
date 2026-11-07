# Kotlin 经典 100 问 - 详细答案

> 基于《Kotlin 经典 100 问》文档整理的完整面试题答案

---

## 一、Kotlin 基础 (1-20)

### 1. val 和 var 的区别是什么？

**val**（不可变引用）：声明后不可重新赋值，类似Java的`final`。指向的对象本身如果是可变的（如MutableList），其内容仍可修改。

**var**（可变引用）：声明后可以重新赋值。

```kotlin
val name = "Kotlin"      // 不可重新赋值
var age = 25             // 可以重新赋值
age = 26                 // ✓ 合法
// name = "Java"         // ✗ 编译错误

val list = mutableListOf(1, 2)
list.add(3)              // ✓ 合法，对象内容可变
```

### 2. Kotlin 为什么能有效减少NPE(空指针异常)？

Kotlin通过**类型系统**将空指针异常从运行时错误变为编译时错误：

1. **可空类型系统**：`String` vs `String?`，默认不可为空
2. **编译期检查**：编译器强制处理可能为null的情况
3. **安全调用操作符**：`?.` 避免显式null检查
4. **Elvis操作符**：`?:` 提供默认值
5. **非空断言**：`!!` 显式告知编译器（危险但可控）
6. **智能类型转换**：自动推断非空类型

### 3. 请解释Kotlin 中的安全调用操作符?.的作用

`?.` 在调用前检查对象是否为null，为null时返回null而非抛出NPE。

```kotlin
val length = str?.length      // 如果str为null，length为null
// 等价于：
val length = if (str != null) str.length else null
```

支持链式调用：`user?.address?.city?.length`

### 4. 什么是Elvis 操作符?:?

`?:` 在左侧为null时返回右侧表达式值。

```kotlin
val name = str ?: "Unknown"           // 如果str为null，使用"Unknown"
val length = str?.length ?: 0         // 安全调用+Elvis组合

// 支持return/throw
val user = getUser() ?: return        // 为null时提前返回
val user = getUser() ?: throw IllegalStateException("User not found")
```

### 5. 如何使用非空断言!!?

`!!` 将任何值转换为非空类型，为null时抛出`KotlinNullPointerException`。

```kotlin
val length = str!!.length     // 如果str为null，抛出NPE
```

**使用场景**：确定变量不可能为null但编译器无法推断时（如已做外部检查）。

**警告**：过度使用`!!`会失去Kotlin的空安全优势，应优先使用`?.`和`?:`。

### 6. 什么是data class(数据类)?它自动生成了哪些方法?

`data class` 用于只保存数据的类，自动生成样板代码：

**自动生成的方法**：
- `equals()` / `hashCode()`
- `toString()`（格式：`User(name=John, age=30)`）
- `componentN()` 函数（用于解构声明）
- `copy()` 函数

```kotlin
data class User(val name: String, val age: Int)

// 使用
val user = User("John", 30)
val copy = user.copy(age = 31)        // 修改age，其他不变
val (name, age) = user                // 解构声明
```

**限制**：主构造函数至少有一个参数；不能是abstract/open/sealed/inner。

### 7. 为什么说data class 非常适合MVVM架构?

1. **不可变性**：配合`val`使用，状态变更必须通过`copy()`，保证状态变化可追踪
2. **自动equals/hashCode**：便于DiffUtil比较列表数据变化
3. **简洁**：减少样板代码，专注业务逻辑
4. **copy()**：方便创建新状态（MVI/StateFlow中常用）
5. **toString()**：便于调试日志输出

```kotlin
// ViewModel中
data class UiState(
    val isLoading: Boolean = false,
    val data: List<Item> = emptyList(),
    val error: String? = null
)

fun updateData(newData: List<Item>) {
    _uiState.value = _uiState.value.copy(
        isLoading = false,
        data = newData
    )
}
```

### 8. lateinit 和lazy 之间有什么区别?

| 特性 | lateinit | lazy |
|------|----------|------|
| **初始化时机** | 使用前手动赋值 | 首次访问时自动初始化 |
| **适用类型** | 只能用于var | 只能用于val |
| **类型限制** | 非空类型（不能用可空类型） | 任何类型 |
| **线程安全** | 无 | 默认线程安全（可配置） |
| **检查方式** | `::var.isInitialized` | 无 |
| **使用场景** | 依赖注入、单元测试、生命周期后初始化 | 昂贵计算、延迟加载 |

```kotlin
lateinit var adapter: RecyclerView.Adapter<*>
lazy val database: AppDatabase by lazy { 
    Room.databaseBuilder(...).build() 
}
```

### 9. lateinit 适用于哪些场景?

1. **依赖注入**：Dagger/Hilt注入的依赖，构造函数无法初始化
2. **生命周期依赖**：Activity/Fragment中，需要等`onCreate`后才能初始化
3. **单元测试**：测试类中，需要`@Before`或每个测试方法中设置
4. **平台类型**：与Java互操作时，确认不会为null但编译器无法识别

```kotlin
class MainActivity : AppCompatActivity() {
    lateinit var viewModel: MainViewModel

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel = ViewModelProvider(this).get(MainViewModel::class.java)
    }
}
```

### 10. lazy 的线程安全是如何保证的?

`lazy` 默认使用**双重检查锁（Double-Checked Locking）**模式：

```kotlin
public fun <T> lazy(initializer: () -> T): Lazy<T> = SynchronizedLazyImpl(initializer)
```

**三种模式**：
1. `LazyThreadSafetyMode.SYNCHRONIZED`（默认）：线程安全，使用锁
2. `LazyThreadSafetyMode.PUBLICATION`：允许多线程同时初始化，只取第一个结果
3. `LazyThreadSafetyMode.NONE`：无线程安全保证，单线程使用性能最优

```kotlin
val value by lazy(LazyThreadSafetyMode.NONE) { expensiveOperation() }
```

### 11. inline 关键字的作用是什么?

`inline` 将函数体直接插入调用处，消除高阶函数的lambda对象创建开销：

**核心作用**：
- 消除lambda的匿名类/对象分配
- 允许在lambda中使用非局部返回（`return`）
- 结合`reified`实现泛型类型实化

```kotlin
inline fun measureTime(block: () -> Unit) {
    val start = System.currentTimeMillis()
    block()
    println("Time: ${System.currentTimeMillis() - start}ms")
}

// 调用处编译后等价于直接插入代码
measureTime { doSomething() }   // 无lambda对象创建
```

**限制**：函数体不能太大；不能递归调用；public/protected inline函数不能访问私有成员。

### 12. 什么是高阶函数?

高阶函数是**接收函数作为参数**或**返回函数**的函数。

```kotlin
// 接收函数参数
fun calculate(a: Int, b: Int, operation: (Int, Int) -> Int): Int {
    return operation(a, b)
}

// 返回函数
fun multiplier(factor: Int): (Int) -> Int {
    return { number -> number * factor }
}

// 使用
val sum = calculate(4, 5) { a, b -> a + b }     // 9
val triple = multiplier(3)
println(triple(4))                              // 12
```

**Android应用**：`let/run/with/apply/also`、集合操作（`filter/map/reduce`）、协程构建器。

### 13. 什么是扩展函数?

在不继承或使用装饰器的情况下，为现有类添加新函数。

```kotlin
fun String.addExclamation(): String = this + "!"
"Hello".addExclamation()    // "Hello!"

fun Int.dpToPx(context: Context): Int = 
    (this * context.resources.displayMetrics.density).toInt()
```

**特点**：
- 静态解析（编译时确定），不是真正的类成员
- 不能访问类的private/protected成员
- 不会覆盖父类同名函数（无多态性）

### 14. 扩展函数的本质是什么?

编译为**静态工具函数**，接收者作为第一个参数：

```kotlin
// Kotlin
fun String.lastChar(): Char = this[length - 1]

// 编译后Java等价代码
public static final char lastChar(@NotNull String $this) {
    return $this.charAt($this.length() - 1);
}
```

**关键点**：
- 不是成员函数，不修改类结构
- 调用处编译为静态调用（非虚调用）
- 无运行时开销

### 15. 扩展函数可以访问类的private成员吗?为什么?

**不可以**。因为扩展函数本质是静态函数，不在类的作用域内。

```kotlin
class Person(private val name: String)

fun Person.greet() = "Hello, $name"   // ✗ 编译错误，无法访问private name
```

**例外**：在类内部定义的扩展函数可以访问外部类的私有成员（因为编译在同一个类中）。

```kotlin
class Person(private val name: String) {
    fun String.greet() = "Hello, $name"   // ✓ 可以访问Person的private成员
}
```

### 16. 什么是密封类(sealed class)?

限制继承层次的类，所有子类必须在**同一文件**中定义（Kotlin 1.1后放宽到同一模块）。

```kotlin
sealed class Result {
    data class Success(val data: String) : Result()
    data class Error(val exception: Throwable) : Result()
    object Loading : Result()
}

// when表达式无需else分支（编译器知道所有子类）
fun handle(result: Result) = when (result) {
    is Result.Success -> println(result.data)
    is Result.Error -> println(result.exception.message)
    Result.Loading -> println("Loading...")
}
```

**优势**：
- 配合`when`使用，编译器强制处理所有情况
- 新增子类时编译器检查遗漏
- 比枚举更灵活（可携带数据）

### 17. 密封类(sealed class)与枚举(enum)的区别是什么?

| 特性 | sealed class | enum |
|------|-------------|------|
| **实例数量** | 每子类可有无限实例 | 每常量单实例 |
| **状态** | 可携带不同数据 | 所有常量同类型 |
| **继承** | 支持子类继承 | 不支持 |
| **使用场景** | 有限状态机（带数据） | 固定常量集合（如方向） |
| **when使用** | 需判断类型 | 直接判断值 |

```kotlin
// 枚举：固定状态
enum class Status { ACTIVE, INACTIVE }

// 密封类：状态+数据
sealed class ApiState {
    object Idle : ApiState()
    object Loading : ApiState()
    data class Success(val data: List<User>) : ApiState()
    data class Error(val message: String) : ApiState()
}
```

### 18. object 关键字有哪些作用?

三种用法：

1. **对象声明（单例）**：
```kotlin
object Singleton {
    fun doSomething() {}
}
// 使用：Singleton.doSomething()
```

2. **伴生对象（companion object）**：
```kotlin
class MyClass {
    companion object {
        fun create() = MyClass()
    }
}
// 使用：MyClass.create()
```

3. **匿名对象/对象表达式**：
```kotlin
val listener = object : OnClickListener {
    override fun onClick(v: View?) {}
}
```

### 19. companion object(伴生对象)是什么?

类内部的单例对象，用于替代Java的`static`成员。

```kotlin
class User(val name: String) {
    companion object Factory {
        fun create(name: String) = User(name)
        const val MAX_AGE = 150
    }
}

// 使用
User.create("John")        // 类似Java静态方法
User.MAX_AGE               // 类似Java静态常量
```

**特点**：
- 每个类只有一个伴生对象
- 可命名（默认名`Companion`）
- 可实现接口
- 编译为静态方法（`@JvmStatic`注解）或实例方法

### 20. 什么是委托(by 关键字)?

将类的实现委托给另一个对象，避免样板代码。

**类委托**：
```kotlin
interface Base {
    fun print()
}

class BaseImpl(val x: Int) : Base {
    override fun print() { println(x) }
}

class Derived(b: Base) : Base by b   // 将Base的实现委托给b
```

**属性委托**：
```kotlin
class User {
    var name: String by Delegates.observable("<no name>") { prop, old, new ->
        println("$old -> $new")
    }
}
```

**标准委托**：`lazy`、`Delegates.observable/vetoable`、`map`委托。

---

## 二、进阶语法与原理 (21-36)

### 21. by lazy 的底层原理是什么?

`by lazy` 使用**属性委托**机制：

1. 创建`Lazy<T>`实例（默认`SynchronizedLazyImpl`）
2. 首次访问时调用`getValue()`，执行初始化lambda并缓存结果
3. 后续访问直接返回缓存值

```kotlin
// 简化版实现
class SynchronizedLazyImpl<out T>(initializer: () -> T) : Lazy<T> {
    private var initializer: (() -> T)? = initializer
    private var _value: Any? = UNINITIALIZED_VALUE

    override val value: T
        get() {
            val _v1 = _value
            if (_v1 !== UNINITIALIZED_VALUE) return _v1 as T

            return synchronized(this) {
                val _v2 = _value
                if (_v2 !== UNINITIALIZED_VALUE) _v2 as T
                else {
                    val typedValue = initializer!!()
                    _value = typedValue
                    initializer = null
                    typedValue
                }
            }
        }
}
```

### 22. 为什么Kotlin 类默认是final 的?

**Effective Java原则**：设计继承或禁止继承（Design for inheritance or prohibit it）。

1. **安全性**：防止非预期的继承和重写导致脆弱基类问题
2. **性能**：final类方法可去虚拟化（devirtualization），JVM可内联优化
3. **清晰性**：显式标记`open`表示设计为可继承

```kotlin
class FinalClass              // 默认final，不可继承
open class OpenClass          // 显式允许继承
abstract class AbstractClass  // 必须继承
```

### 23. open、abstract 和final 关键字的区别?

| 关键字 | 类 | 函数/属性 | 含义 |
|--------|-----|----------|------|
| **final** | 默认 | 默认 | 不可继承/重写 |
| **open** | 可继承 | 可重写 | 显式允许继承 |
| **abstract** | 必须继承 | 必须重写 | 无实现，强制子类提供 |

```kotlin
open class Animal {
    open fun speak() {}           // 可重写
    fun move() {}                 // final，不可重写
}

abstract class Shape {
    abstract fun draw()           // 必须重写
    open fun resize() {}          // 可选重写
}
```

### 24. 什么是解构声明(Destructuring Declarations)?

将对象分解为多个变量的声明方式。

```kotlin
data class User(val name: String, val age: Int)

val (name, age) = User("John", 30)
// 等价于：
val name = user.component1()
val age = user.component2()

// 使用场景
for ((key, value) in map) { }
val (a, b) = pair
val (x, y, z) = Triple(1, 2, 3)
```

**自定义**：实现`componentN()`函数（operator修饰）。

### 25. operator 关键字的作用是什么?

标记函数为**运算符重载**，可用运算符语法调用。

```kotlin
data class Point(val x: Int, val y: Int) {
    operator fun plus(other: Point) = Point(x + other.x, y + other.y)
    operator fun get(index: Int) = when(index) { 0 -> x; 1 -> y; else -> throw IndexOutOfBoundsException() }
}

val p3 = p1 + p2          // 使用plus
val x = p1[0]             // 使用get
```

**常见运算符**：`+`(`plus`)、`-`(`minus`)、`*`(`times`)、`[]`(`get/set`)、`()`(`invoke`)、`in`(`contains`)、`..`(`rangeTo`)。

### 26. 什么是infix 中缀调用?

允许函数以**运算符风格**调用（省略点和括号）。

```kotlin
infix fun Int.toPowerOf(exponent: Int): Int = Math.pow(this.toDouble(), exponent.toDouble()).toInt()

val result = 2 toPowerOf 10    // 中缀调用，等价于 2.toPowerOf(10)
```

**要求**：
- 必须是成员函数或扩展函数
- 只能有一个参数
- 参数不能有默认值

**标准库示例**：`mapOf(1 to "one")`（`to`是中缀函数）、`apply`、`let`等。

### 27. Kotlin 相比Java 为什么更适合Android 开发?

1. **空安全**：编译期空检查，减少崩溃
2. **简洁**：减少样板代码（约40%代码量减少）
3. **扩展函数**：无需继承即可增强类
4. **函数式编程**：lambda、高阶函数简化异步和集合操作
5. **协程**：轻量级异步编程，替代回调地狱
6. **数据类**：自动生成equals/hashCode/toString/copy
7. **智能类型转换**：自动类型推断和转换
8. **默认参数**：减少重载方法
9. **命名参数**：提高可读性
10. **DSL支持**：构建简洁的API（如Gradle Kotlin DSL、Compose）

### 28. Kotlin 字节码最终运行在什么环境?

Kotlin编译为**JVM字节码**（`.class`文件），运行在JVM上。

**多平台支持**：
- **JVM**：Kotlin/JVM（Android、服务器端）
- **JavaScript**：Kotlin/JS（编译为JS）
- **Native**：Kotlin/Native（编译为LLVM IR，支持iOS、嵌入式等）

**Android特殊处理**：通过R8/ProGuard进一步优化，或使用Jetpack Compose Compiler进行特殊编译。

### 29. 什么是内联类(value class)?

Kotlin 1.5+引入，基于值的类，编译为底层类型，无运行时包装开销。

```kotlin
@JvmInline
value class Password(val value: String)

fun authenticate(password: Password) { }
authenticate(Password("secret"))   // 编译后直接使用String
```

**优势**：
- 类型安全（编译时区分，运行时无开销）
- 无额外内存分配
- 可定义方法和属性

**限制**：只能有一个属性；不能继承类；不能作为其他类的基类。

### 30. reified 关键字的作用是什么?

在**内联函数**中保留泛型类型信息（突破泛型擦除）。

```kotlin
inline fun <reified T> Gson.fromJson(json: String): T {
    return fromJson(json, object : TypeToken<T>() {}.type)
}

// 使用
val user: User = gson.fromJson(jsonString)   // 无需传递Class参数
```

**原理**：内联后编译器知道具体类型，生成类型检查代码。

### 31. Kotlin 的泛型擦除是什么?

与Java相同，泛型信息在编译后擦除，运行时无法区分`List<String>`和`List<Int>`。

**影响**：
- 无法使用`is List<String>`（编译错误）
- 反射获取类型信息困难

**解决方案**：
- `reified`内联函数（编译期保留）
- `TypeToken`模式（Gson使用匿名子类保留泛型信息）
- `@JvmSuppressWildcards`等注解

### 32. 请解释Kotlin 中out(协变)的含义

`out` 表示**只输出（生产者）**，泛型参数作为返回类型使用。

```kotlin
interface Producer<out T> {
    fun produce(): T          // 返回T，安全
    // fun consume(item: T)   // 编译错误，不能作为参数
}

val producer: Producer<Number> = Producer<Int>()   // ✓ 协变允许
```

**子类型关系**：`Producer<Int>` 是 `Producer<Number>` 的子类型（因为Int是Number子类型）。

### 33. 请解释Kotlin 中in(逆变)的含义

`in` 表示**只输入（消费者）**，泛型参数作为参数类型使用。

```kotlin
interface Consumer<in T> {
    fun consume(item: T)      // 接收T，安全
    // fun produce(): T       // 编译错误，不能作为返回
}

val consumer: Consumer<Int> = Consumer<Number>()   // ✓ 逆变允许
```

**子类型关系**：`Consumer<Number>` 是 `Consumer<Int>` 的子类型（反过来的）。

### 34. 什么是协变?

**协变（Covariance）**：保留子类型关系。如果`A`是`B`的子类型，则`Producer<A>`是`Producer<B>`的子类型。

**标记**：`out`
**场景**：只读集合（`List<out E>`）、生产者

```kotlin
val numbers: List<Number> = listOf<Int>(1, 2, 3)   // ✓ 协变
```

### 35. 什么是逆变?

**逆变（Contravariance）**：反转子类型关系。如果`A`是`B`的子类型，则`Consumer<B>`是`Consumer<A>`的子类型。

**标记**：`in`
**场景**：比较器、回调、消费者

```kotlin
val intComparator: Comparator<Int> = Comparator<Number> { a, b -> a.toInt().compareTo(b.toInt()) }
```

### 36. Kotlin 如何实现DSL(领域特定语言)?

通过**高阶函数+lambda+扩展函数+中缀调用**构建类型安全的DSL。

```kotlin
// HTML DSL示例
fun html(init: HTML.() -> Unit): HTML {
    val html = HTML()
    html.init()
    return html
}

class HTML {
    fun body(init: Body.() -> Unit) { /*...*/ }
}

// 使用
html {
    body {
        h1 { +"Hello" }
    }
}
```

**Android应用**：Gradle Kotlin DSL、Jetpack Compose UI、Anko（已弃用）。

---

## 三、协程与并发 (37-65)

### 37. 什么是协程(Coroutine)?

**轻量级线程**，由Kotlin标准库实现，可在单线程上通过挂起/恢复实现并发。

**特点**：
- 非阻塞（挂起时不占用线程）
- 极低开销（可创建数百万协程）
- 结构化并发（父子关系自动管理）

```kotlin
import kotlinx.coroutines.*

fun main() = runBlocking {
    launch {
        delay(1000L)
        println("World!")
    }
    println("Hello,")
}
```

### 38. suspend 关键字的作用是什么?

标记函数可在执行过程中**挂起**（暂停执行，释放线程），稍后恢复。

```kotlin
suspend fun fetchData(): String {
    delay(1000)          // 挂起函数，只能在协程或挂起函数中调用
    return "Data"
}
```

**特点**：
- 挂起函数不会阻塞线程
- 编译后添加`Continuation`参数（回调转换）
- 只能在协程或另一个挂起函数中调用

### 39. 协程的调度器(Dispatchers)有哪些?

| 调度器 | 用途 | 线程 |
|--------|------|------|
| **Dispatchers.Default** | CPU密集型任务 | 线程数=CPU核心数 |
| **Dispatchers.IO** | IO密集型（网络/文件） | 64或核心数取大者 |
| **Dispatchers.Main** | UI操作（Android/iOS） | 主线程 |
| **Dispatchers.Unconfined** | 不指定线程 | 调用处线程，挂起后恢复线程不确定 |

```kotlin
launch(Dispatchers.IO) { networkRequest() }
withContext(Dispatchers.Main) { updateUI() }
```

### 40. launch 和 async 的区别是什么?

| 特性 | launch | async |
|------|--------|-------|
| **返回类型** | `Job`（无结果） | `Deferred<T>`（有结果） |
| **异常处理** | 立即抛出（未捕获则崩溃） | 等待`await()`时抛出 |
| **用途** |  fire-and-forget | 需要返回值的并发任务 |
| **启动模式** | 立即启动 | 立即启动 |

```kotlin
val job = launch { doSomething() }
val deferred = async { fetchData() }
val result = deferred.await()   // 等待结果
```

### 41. 什么是Job 和Deferred?

**Job**：协程的句柄，用于生命周期管理。

```kotlin
val job = launch {
    delay(1000)
}
job.cancel()           // 取消协程
job.join()             // 等待完成
job.isActive           // 是否活跃
```

**Deferred**：Job的子类，带有结果。

```kotlin
val deferred = async { "Result" }
val result = deferred.await()   // 挂起等待结果
deferred.cancel()               // 取消（如果已开始）
```

### 42. 协程的取消是如何工作的?

**协作式取消**：协程必须检查取消状态并配合。

```kotlin
val job = launch {
    while (isActive) {           // 检查取消状态
        doWork()
        yield()                    // 检查取消并出让线程
    }
}
job.cancelAndJoin()               // 取消并等待

// 取消时抛出CancellationException（正常取消，非异常）
```

**不可取消的代码**：`withContext(NonCancellable) { }`

### 43. 什么是结构化并发?

协程的父子关系形成**作用域树**，子协程生命周期受父协程约束：

1. 父协程等待所有子协程完成
2. 父协程取消时，所有子协程取消
3. 子协程异常会取消父协程（默认）

```kotlin
coroutineScope {
    launch { task1() }      // 子协程1
    launch { task2() }      // 子协程2
}                           // 等待所有子协程完成后才返回
```

### 44. SupervisorJob 的作用是什么?

**监督作业**：子协程失败不影响其他子协程和父协程。

```kotlin
supervisorScope {
    launch { task1() }      // 失败不影响
    launch { task2() }      // 继续运行
}
```

**使用场景**：独立运行的子任务（如服务器处理多个客户端连接）。

### 45. 什么是Flow?

**冷流（Cold Stream）**：基于协程的响应式数据流，按需生产数据。

```kotlin
val flow = flow {
    for (i in 1..3) {
        delay(100)
        emit(i)             // 发射数据
    }
}

flow.collect { value ->     // 收集数据（终端操作）
    println(value)
}
```

**特点**：
- 冷流：每次collect独立执行
- 挂起式：使用挂起函数而非回调
- 背压：自动处理（挂起生产者）

### 46. Flow 和LiveData 的区别是什么?

| 特性 | Flow | LiveData |
|------|------|----------|
| **生命周期感知** | 需配合`lifecycleScope`/`repeatOnLifecycle` | 自动感知 |
| **线程** | 灵活控制（flowOn） | 主线程观察 |
| **冷/热** | 冷流（按需生产） | 热流（始终持有最新值） |
| **数据转换** | 丰富操作符（map/filter等） | 简单转换 |
| **使用场景** | 数据层、复杂流处理 | UI层简单状态观察 |

**推荐**：新项目推荐Flow + `repeatOnLifecycle`，LiveData逐步被替代。

### 47. StateFlow 和SharedFlow 的区别是什么?

| 特性 | StateFlow | SharedFlow |
|------|-----------|------------|
| **类型** | 热流，状态持有 | 热流，事件广播 |
| **初始值** | 必须有 | 可无 |
| **缓存** | 总是缓存最新值 | 可配置replay缓存 |
| **重复值** | 相同值不重新发射（distinctUntilChanged） | 重复发射 |
| **使用场景** | UI状态（如Loading/Success/Error） | 一次性事件（如Toast/导航） |

```kotlin
// StateFlow
private val _uiState = MutableStateFlow(UiState())
val uiState: StateFlow<UiState> = _uiState.asStateFlow()

// SharedFlow
private val _events = MutableSharedFlow<Event>()
val events: SharedFlow<Event> = _events.asSharedFlow()
```

### 48. 什么是热流(Hot Flow)和冷流(Cold Flow)?

**冷流（Cold Flow）**：每次收集时独立生产数据，无收集者时不生产。

```kotlin
val coldFlow = flow { emit(1) }    // 每次collect都重新执行
```

**热流（Hot Flow）**：独立于收集者存在，有缓存值。

```kotlin
val hotFlow = MutableStateFlow(0)  // 始终存在，多个收集者共享
```

**对比**：
- 冷流：如网络请求（每个用户独立）
- 热流：如UI状态（共享当前状态）

### 49. Flow 的背压(Backpressure)如何处理?

Flow使用**挂起**处理背压：生产者挂起直到消费者准备好。

```kotlin
flow {
    emit(1)           // 如果消费者慢，挂起等待
}.collect { value ->
    delay(100)        // 模拟慢消费
}
```

**缓冲策略**：
- `buffer()`：允许生产者预缓冲
- `conflate()`：只保留最新值，丢弃中间值
- `collectLatest()`：新值到达时取消旧值处理

```kotlin
flow.interval(100).conflate().collect { }   // 只处理最新值
```

### 50. 什么是Channel?

协程间通信的**队列**，用于发送和接收数据。

```kotlin
val channel = Channel<Int>()

launch {
    for (x in 1..5) channel.send(x)
    channel.close()
}

launch {
    for (value in channel) println(value)
}
```

**类型**：
- `RendezvousChannel`（默认）：无缓冲，发送和接收配对
- `BufferedChannel`：有固定缓冲
- `ConflatedChannel`：只保留最新值
- `UnlimitedChannel`：无限缓冲

### 51. select 表达式的作用是什么?

在多个挂起操作中选择**第一个可用**的。

```kotlin
select<Unit> {
    channelA.onReceive { value -> println("A: $value") }
    channelB.onReceive { value -> println("B: $value") }
    delay(1000).onAwait { println("Timeout") }
}
```

**使用场景**：多路复用、超时处理、竞争条件。

### 52. 协程的异常处理机制是怎样的?

**异常传播**：
- `launch`：异常立即传播到父协程（默认）
- `async`：异常延迟到`await()`时抛出

**处理方式**：
```kotlin
// 1. try-catch
launch {
    try { riskyOperation() } catch(e: Exception) { }
}

// 2. CoroutineExceptionHandler（顶层处理）
val handler = CoroutineExceptionHandler { _, exception -> 
    println("Caught $exception") 
}
val scope = CoroutineScope(Job() + handler)

// 3. SupervisorJob + try-catch（子协程独立处理）
supervisorScope {
    launch { try { risky() } catch(e: Exception) { } }
}
```

### 53. withContext 和runBlocking 的区别是什么?

| 特性 | withContext | runBlocking |
|------|-------------|-------------|
| **用途** | 切换上下文（线程） | 桥接阻塞和非阻塞世界 |
| **阻塞** | 挂起（非阻塞） | 阻塞当前线程 |
| **使用场景** | 协程内切换线程 | 测试、main函数 |
| **返回值** | 有 | 有 |

```kotlin
suspend fun fetchData() = withContext(Dispatchers.IO) {
    networkRequest()          // 挂起，不阻塞
}

fun main() = runBlocking {    // 阻塞主线程直到完成
    launch { delay(1000) }
}
```

**警告**：`runBlocking` 不要在协程中使用（会阻塞协程线程）。

### 54. 什么是CoroutineScope?

协程的**作用域**，定义协程的生命周期边界。

```kotlin
// 自定义Scope
val scope = CoroutineScope(Job() + Dispatchers.Main)

// Android预定义Scope
lifecycleScope          // 绑定Lifecycle
viewModelScope          // 绑定ViewModel
GlobalScope             // 全局（不推荐，生命周期不可控）
```

**最佳实践**：使用结构化并发，避免`GlobalScope`。

### 55. viewModelScope 的生命周期是怎样的?

绑定**ViewModel生命周期**，ViewModel `onCleared()`时自动取消所有协程。

```kotlin
class MyViewModel : ViewModel() {
    fun loadData() {
        viewModelScope.launch {
            // 自动在ViewModel销毁时取消
            val data = repository.fetchData()
            _uiState.value = data
        }
    }
}
```

**实现**：内部使用`CloseableCoroutineScope`，在`onCleared()`中调用`cancel()`。

### 56. lifecycleScope 和viewModelScope 的区别是什么?

| 特性 | lifecycleScope | viewModelScope |
|------|---------------|----------------|
| **绑定对象** | LifecycleOwner（Activity/Fragment） | ViewModel |
| **生命周期** | DESTROYED时取消 | onCleared()时取消 |
| **使用场景** | UI层操作（如动画、点击） | 业务逻辑、数据加载 |
| **配置变更** | Activity重建时取消 | 配置变更后保留（ViewModel存活） |

### 57. 什么是非阻塞式挂起?

挂起函数暂停协程执行但**不阻塞线程**，线程可执行其他协程。

```kotlin
suspend fun fetchData() {
    delay(1000)           // 挂起1秒，线程去执行其他协程
    // 1秒后恢复执行
}
```

**实现原理**：编译为状态机（Continuation-passing style），通过`resumeWith`恢复。

### 58. suspend 函数编译后的原理是什么?

CPS（Continuation Passing Style）转换：

```kotlin
// Kotlin
suspend fun fetchData(): String {
    val user = fetchUser()
    return user.name
}

// 编译后伪代码
fun fetchData(continuation: Continuation<String>): Any {
    val sm = continuation as? ThisSM ?: FetchDataSM(continuation)
    when (sm.label) {
        0 -> {
            sm.label = 1
            fetchUser(sm)          // 挂起点
            return COROUTINE_SUSPENDED
        }
        1 -> {
            val user = sm.result as User
            return user.name
        }
    }
}
```

### 59. 什么是Continuation?

表示协程**挂起点的回调**，包含恢复协程所需的所有信息。

```kotlin
interface Continuation<in T> {
    val context: CoroutineContext
    fun resumeWith(result: Result<T>)
}
```

**使用**：`suspendCoroutine` / `suspendCancellableCoroutine` 与回调API互操作。

```kotlin
suspend fun fetchData() = suspendCoroutine<String> { continuation ->
    api.fetch(object : Callback {
        override fun onSuccess(data: String) {
            continuation.resume(data)
        }
        override fun onError(e: Exception) {
            continuation.resumeWithException(e)
        }
    })
}
```

### 60. 协程和线程的关系是什么?

**一对多关系**：
- 一个线程可运行多个协程（通过调度器）
- 一个协程可在多个线程间切换（挂起恢复）

**类比**：
- 线程 = 工人
- 协程 = 任务
- 调度器 = 任务分配器

```kotlin
withContext(Dispatchers.IO) { }    // 切换到IO线程
withContext(Dispatchers.Main) { }  // 切回主线程
// 同一个协程在不同线程执行
```

### 61. 什么是CoroutineContext?

协程的**上下文**，包含协程运行所需的所有元素：

- `Job`：生命周期
- `CoroutineDispatcher`：调度器
- `CoroutineName`：名称（调试）
- `CoroutineExceptionHandler`：异常处理
- `ContinuationInterceptor`：拦截器

```kotlin
launch(Dispatchers.IO + CoroutineName("MyCoroutine") + exceptionHandler) { }
```

**组合**：使用`+`组合多个元素，相同类型后者覆盖前者。

### 62. 如何取消一个协程?

```kotlin
val job = launch { 
    while (isActive) {          // 检查取消状态
        doWork()
    }
}

job.cancel()                     // 发送取消信号
job.cancelAndJoin()            // 取消并等待完成
job.cancel(CancellationException("Custom reason"))
```

**不可取消代码**：
```kotlin
withContext(NonCancellable) {
    cleanup()                    // 即使取消也执行清理
}
```

### 63. 什么是协程的启动模式?

| 模式 | 说明 |
|------|------|
| **DEFAULT** | 立即调度，根据调度器决定执行时机 |
| **LAZY** | 延迟启动，调用`start()`或`await()`时启动 |
| **ATOMIC** | 原子启动，取消前必须开始执行（已弃用） |
| **UNDISPATCHED** | 立即在当前线程执行，直到第一个挂起点 |

```kotlin
val job = launch(start = CoroutineStart.LAZY) { }
job.start()    // 手动启动
```

### 64. Flow 的collectLatest 和collect 的区别是什么?

**collect**：顺序处理每个值，处理完再接收下一个。

**collectLatest**：新值到达时**取消**旧值的处理。

```kotlin
flow {
    emit(1); delay(100)
    emit(2); delay(100)
    emit(3)
}.collectLatest { value ->
    delay(200)           // 处理慢
    println(value)       // 只打印3（1和2被取消）
}
```

**使用场景**：搜索建议（只关心最新输入）。

### 65. 如何处理协程中的超时?

```kotlin
// 1. withTimeout
withTimeout(1000L) {
    doSomething()        // 超时抛出TimeoutCancellationException
}

// 2. withTimeoutOrNull
val result = withTimeoutOrNull(1000L) {
    doSomething()        // 超时返回null
}

// 3. Flow超时
flow.timeout(1000)       // Kotlin 1.7+
```

---

## 四、Android 性能与架构 (66-90)

### 66. MVVM 架构的核心思想是什么?

**Model-View-ViewModel**：
- **Model**：数据层（Repository、数据源）
- **View**：UI层（Activity/Fragment/Compose），观察ViewModel
- **ViewModel**：业务逻辑持有者，独立于View生命周期

**核心原则**：
- 单向数据流：ViewModel → View
- View不直接操作Model
- ViewModel不引用View

```kotlin
class MyViewModel(private val repository: UserRepository) : ViewModel() {
    private val _users = MutableLiveData<List<User>>()
    val users: LiveData<List<User>> = _users

    fun loadUsers() {
        viewModelScope.launch {
            _users.value = repository.getUsers()
        }
    }
}
```

### 67. Jetpack ViewModel 的生命周期是怎样的?

- 创建：首次访问时（通过`ViewModelProvider`）
- 存活：配置变更（旋转屏幕）后保留
- 销毁：所属`ViewModelStoreOwner`（Activity/Fragment）销毁时调用`onCleared()`

**原理**：通过`ViewModelStore`存储，配置变更时由系统保留Store。

### 68. LiveData 和Flow 如何选择?

| 场景 | 推荐 |
|------|------|
| 简单UI状态观察 | LiveData（自动生命周期感知） |
| 数据层、复杂流处理 | Flow |
| 需要操作符转换 | Flow |
| 跨平台代码 | Flow |
| 与DataBinding配合 | LiveData |

**趋势**：新项目推荐Flow + `repeatOnLifecycle`，LiveData逐步被替代。

### 69. DataBinding 和ViewBinding 的区别是什么?

| 特性 | ViewBinding | DataBinding |
|------|-------------|-------------|
| **功能** | 类型安全的视图引用 | 双向绑定+表达式 |
| **编译** | 更快（无生成表达式代码） | 较慢 |
| **学习曲线** | 低 | 高 |
| **XML支持** | 无特殊要求 | 需`<layout>`根标签 |
| **双向绑定** | 不支持 | 支持 |
| **推荐** | 是（Google推荐） | 复杂场景 |

```kotlin
// ViewBinding
val binding = ActivityMainBinding.inflate(layoutInflater)
binding.textView.text = "Hello"

// DataBinding
binding.user = user
binding.lifecycleOwner = this
```

### 70. Repository 模式的作用是什么?

**数据层抽象**，统一数据来源（网络、数据库、缓存），向上层提供干净API。

```kotlin
class UserRepository(
    private val remote: UserRemoteDataSource,
    private val local: UserLocalDataSource
) {
    suspend fun getUsers(): List<User> {
        return try {
            val users = remote.fetchUsers()
            local.saveUsers(users)
            users
        } catch (e: Exception) {
            local.getUsers()          // 降级到本地缓存
        }
    }
}
```

**优势**：单一数据源、易于测试、解耦业务逻辑和数据获取。

### 71. Room 数据库的优势是什么?

1. **编译时SQL检查**：注解处理器验证SQL语法
2. **减少样板代码**：自动生成DAO实现
3. **LiveData/Flow支持**：自动观察数据变化
4. **迁移支持**：`Migration` API处理数据库升级
5. **与协程集成**：支持挂起函数
6. **事务支持**：`@Transaction`注解

```kotlin
@Dao
interface UserDao {
    @Query("SELECT * FROM user")
    fun getAll(): Flow<List<User>>    // 自动观察变化

    @Insert
    suspend fun insert(user: User)    // 挂起函数
}
```

### 72. WorkManager 的使用场景是什么?

**可延迟、有保证的后台任务**：
- 需要保证执行（即使App关闭）
- 不立即需要结果
- 约束条件（网络、电量、充电状态）

```kotlin
val workRequest = OneTimeWorkRequestBuilder<UploadWorker>()
    .setConstraints(Constraints.Builder()
        .setRequiredNetworkType(NetworkType.UNMETERED)
        .build())
    .build()

WorkManager.getInstance(context).enqueue(workRequest)
```

**不适用**：即时任务（用协程）、需要精确时间（用AlarmManager）。

### 73. Hilt 相比Dagger 简化了什么?

1. **自动组件管理**：预定义`ApplicationComponent`、`ActivityComponent`等
2. **自动绑定**：`@AndroidEntryPoint`自动生成组件
3. **简化Module**：无需手动定义`@BindsInstance`
4. **ViewModel支持**：`@HiltViewModel`自动生成工厂
5. **减少样板代码**：无需`AppComponent`接口

```kotlin
@HiltAndroidApp
class MyApp : Application()

@AndroidEntryPoint
class MainActivity : AppCompatActivity()

@HiltViewModel
class MainViewModel @Inject constructor(
    private val repository: UserRepository
) : ViewModel()
```

### 74. 依赖注入(DI)的好处是什么?

1. **解耦**：组件不直接创建依赖
2. **可测试**：轻松替换Mock对象
3. **可维护**：依赖关系集中管理
4. **生命周期管理**：框架自动处理作用域
5. **单例管理**：自动实现单例模式

### 75. 什么是单一职责原则(SRP)?

**一个类只有一个引起变化的原因**（只负责一件事）。

**违反示例**：
```kotlin
class UserManager {           // 违反SRP
    fun fetchFromNetwork() {} // 网络
    fun saveToDatabase() {}   // 数据库
    fun displayUI() {}        // UI
}
```

**正确拆分**：
- `UserRemoteDataSource`：网络
- `UserLocalDataSource`：数据库
- `UserRepository`：协调
- `UserViewModel`：UI逻辑

### 76. Clean Architecture(整洁架构)通常分为哪几层?

1. **Domain层（核心）**：实体、用例、Repository接口（不依赖任何框架）
2. **Data层**：Repository实现、数据源（网络、数据库）
3. **Presentation层**：ViewModel、UI逻辑
4. **Framework层**：Android框架、第三方库

**依赖规则**：内层不依赖外层（依赖指向中心）。

### 77. UseCase 在架构中为什么重要?

1. **封装业务逻辑**：单一用例一个类
2. **可复用**：多个ViewModel可共享
3. **可测试**：纯Kotlin代码，无Android依赖
4. **表达意图**：类名即业务操作（如`GetUserUseCase`）

```kotlin
class GetUserUseCase(private val repository: UserRepository) {
    suspend operator fun invoke(userId: String): Result<User> {
        return try {
            Result.Success(repository.getUser(userId))
        } catch (e: Exception) {
            Result.Error(e)
        }
    }
}
```

### 78. MVI(Model-View-Intent)架构的特点是什么?

- **单向数据流**：Intent → Model → View
- **单一状态对象**：所有UI状态在一个data class中
- **不可变状态**：状态变更通过copy
- **事件驱动**：用户操作作为Intent发送

```kotlin
// 状态
data class UiState(
    val isLoading: Boolean = false,
    val data: List<Item> = emptyList(),
    val error: String? = null
)

// Intent
sealed class UiIntent {
    object LoadData : UiIntent()
    data class ClickItem(val id: String) : UiIntent()
}
```

### 79. MVI 架构的优缺点各有哪些?

**优点**：
- 状态可预测、可追踪
- 易于调试（时间旅行调试）
- 防止状态不一致
- 易于测试

**缺点**：
- 样板代码多（每个状态变更需copy）
- 小变更也需更新整个状态对象
- 学习曲线陡峭
- 过度设计风险（简单页面不需要）

### 80. Android 开发中为什么容易出现内存泄漏?

1. **长生命周期引用短生命周期**：如单例持有Activity引用
2. **匿名内部类**：持有外部类引用（如Handler、AsyncTask）
3. **未取消的订阅**：RxJava/协程/监听器未清理
4. **静态变量**：持有Context或View
5. **Bitmap未回收**：大图片占用内存
6. **WebView**：释放不及时

### 81. 列举常见的Android 内存泄漏场景

1. **单例持有Context**：
```kotlin
object Singleton {
    lateinit var context: Context   // 持有Activity引用！
}
```

2. **Handler延迟消息**：
```kotlin
Handler(Looper.getMainLooper()).postDelayed({ }, 10000)  // 持有外部类
```

3. **匿名线程**：
```kotlin
Thread { /* 长期运行，持有Activity */ }.start()
```

4. **资源未关闭**：Cursor、File、Stream未关闭
5. **Bitmap未回收**：`bitmap.recycle()`（API 10前需要，现在GC处理）
6. **WebView**：销毁不彻底

### 82. LeakCanary 的工作原理是什么?

1. **监听生命周期**：注册`ActivityLifecycleCallbacks`
2. **弱引用监控**：Activity销毁后创建弱引用
3. **GC触发**：手动触发GC
4. **引用检查**：检查弱引用是否进入引用队列
5. **堆转储分析**：如果未回收，dump hprof文件
6. **路径分析**：使用Shark库分析最短强引用路径
7. **通知**：显示泄漏信息和引用链

### 83. 导致ANR(Application Not Responding)的根本原因是什么?

**主线程阻塞超过5秒**（Activity）或**10秒**（BroadcastReceiver）：

1. **IO操作**：主线程网络/数据库/文件操作
2. **复杂计算**：主线程大量计算
3. **锁竞争**：主线程等待锁
4. **Binder调用**：跨进程调用阻塞
5. **UI过度绘制**：复杂布局渲染
6. **死锁**：线程间互相等待

### 84. 如何有效避免ANR?

1. **所有IO放子线程**：使用协程/RxJava/AsyncTask
2. **复杂计算异步化**：`withContext(Dispatchers.Default)`
3. **避免主线程锁**：使用无锁数据结构
4. **优化布局**：减少层级、避免过度绘制
5. **使用StrictMode**：检测主线程违规
6. **懒加载**：延迟初始化非必要资源

```kotlin
lifecycleScope.launch {
    val data = withContext(Dispatchers.IO) { database.query() }
    updateUI(data)
}
```

### 85. OOM(内存溢出)的常见原因有哪些?

1. **内存泄漏累积**：泄漏对象占用内存持续增长
2. **大图片加载**：未压缩的Bitmap（如12MB原图）
3. **内存缓存过大**：LruCache设置不合理
4. **大量对象创建**：列表滑动时创建过多对象
5. **线程过多**：每个线程1MB栈空间
6. **Native内存泄漏**：JNI层内存未释放
7. **内存碎片**：频繁分配释放导致无法分配大对象

### 86. 如何对Bitmap 进行内存优化?

1. **尺寸压缩**：按View大小加载
```kotlin
val options = BitmapFactory.Options().apply {
    inJustDecodeBounds = true
    BitmapFactory.decodeResource(resources, R.id.image, this)
    inSampleSize = calculateInSampleSize(this, reqWidth, reqHeight)
    inJustDecodeBounds = false
}
```

2. **格式优化**：使用`RGB_565`（无透明）替代`ARGB_8888`
3. **复用内存**：`inBitmap`复用旧Bitmap内存
4. **及时回收**：`bitmap.recycle()`（低版本）
5. **使用Glide/Coil**：自动处理上述优化

### 87. RecyclerView 的性能优化方案有哪些?

1. **固定高度**：`setHasFixedSize(true)`
2. **ViewHolder复用**：正确实现`onCreateViewHolder`/`onBindViewHolder`
3. **异步差分计算**：`AsyncListDiffer`后台计算Diff
4. **图片加载优化**：滑动时暂停加载，停止后恢复
5. **减少嵌套**：避免过度布局
6. **局部刷新**：`notifyItemChanged()`而非`notifyDataSetChanged()`
7. **预加载**：`GapWorker`预加载相邻项
8. **缓存优化**：`setItemViewCacheSize()`调整缓存数

### 88. DiffUtil 的算法原理是什么?

**Myers差分算法**：计算两个列表的最短编辑脚本（SES）。

**步骤**：
1. 计算最长公共子序列（LCS）
2. 确定插入、删除、移动操作
3. 在后台线程计算Diff
4. 主线程应用更新（`dispatchUpdatesTo(adapter)`）

**复杂度**：O(N*D)，N为列表长度，D为差异数。

### 89. 什么是冷启动优化?

**冷启动**：App进程不存在时的启动（需创建进程、初始化Application）。

**优化方向**：
- **减少Application初始化**：延迟非必要初始化
- **异步初始化**：子线程初始化SDK
- **懒加载**：按需初始化
- **减少布局层级**：首个Activity布局优化
- **SplashScreen API**：系统级启动画面
- **Baseline Profiles**：预编译常用代码路径

### 90. 请列举常见的App 启动优化手段

1. **延迟初始化**：`Lazy`或`Provider`模式
2. **异步加载**：`Coroutine`/`AsyncTask`初始化非关键SDK
3. **按需加载**：使用时不初始化
4. **Multidex优化**：避免启动时dex加载
5. **布局优化**：`ConstraintLayout`减少层级
6. **Window背景**：设置`windowBackground`避免白屏
7. **预加载**：`ContentProvider`自动初始化（慎用）
8. **Baseline Profiles**：Android 13+预编译

---

## 五、Jetpack Compose (91-100)

### 91. Compose 为什么比传统的XML UI 响应速度快?

1. **声明式UI**：状态变化自动重组，无需手动findViewById/setText
2. **智能重组**：只重组变化的部分，跳过未变化的组件
3. **布局优化**：无测量/布局两次遍历（ConstraintLayout需要）
4. **编译优化**：Compose Compiler优化可跳过函数
5. **无反射**：编译期生成代码，无运行时反射
6. **并行重组**：多核并行处理独立组件

### 92. remember 的作用是什么?

在重组过程中**保持状态**，避免状态重置。

```kotlin
@Composable
fun Counter() {
    var count by remember { mutableStateOf(0) }   // 重组时保持count值
    Button(onClick = { count++ }) {
        Text("Count: $count")
    }
}
```

**原理**：以Composition为作用域存储值，键为调用位置。

### 93. rememberSaveable 和remember 有什么区别?

| 特性 | remember | rememberSaveable |
|------|----------|------------------|
| **生命周期** | Composition | Composition + 配置变更 |
| **数据保存** | 内存 | Bundle（通过Saver） |
| **使用场景** | 临时计算 | UI状态（如输入框内容、滚动位置） |
| **数据类型** | 任意 | 可序列化/自定义Saver |

```kotlin
var text by rememberSaveable { mutableStateOf("") }   // 旋转屏幕后保留
```

### 94. mutableStateOf 的底层原理是什么?

基于**观察者模式**的状态系统：

1. 创建`MutableState<T>`对象
2. 读取时：记录到当前重组作用域（作为依赖）
3. 写入时：通知所有依赖的作用域进行重组
4. 使用`Snapshot`系统保证线程安全

```kotlin
// 简化版
interface MutableState<T> : State<T> {
    override var value: T
        get() = stateRecord.value
        set(value) {
            if (stateRecord.value != value) {
                stateRecord.value = value
                notifyReaders()        // 通知重组
            }
        }
}
```

### 95. 什么是"重组"(Recomposition)?

**状态变化时重新执行Composable函数**，更新UI。

**特点**：
- 可重复、可中断：无副作用
- 乐观执行：假设状态不变，提前计算
- 智能跳过：输入未变的Composable跳过执行

```kotlin
@Composable
fun Greeting(name: String) {
    Text("Hello, $name")      // name变化时重组
}
```

### 96. Compose 如何减少不必要的重组?

1. **使用稳定类型**：`@Stable`/`@Immutable`注解
2. **Lambda记忆化**：`remember`缓存lambda
3. **键控重组**：`key(key) { }`控制重组粒度
4. **派生状态**：`derivedStateOf`减少频繁重组
5. **条件重组**：将变化隔离到最小范围
6. **避免不稳定类型**：如`List`改为`ImmutableList`

```kotlin
val derived by remember { derivedStateOf { expensiveComputation(state) } }
```

### 97. 什么是"副作用"(Side Effects)?

**Composable函数执行期间对外部世界的修改**（Composable应纯函数，无副作用）。

**常见副作用**：
- 修改全局变量
- 操作SharedPreferences
- 启动协程
- 注册监听器

**处理**：使用Effect API将副作用隔离到特定生命周期。

### 98. LaunchedEffect 的作用是什么?

在Composable进入Composition时**启动协程**，键变化时取消并重启。

```kotlin
@Composable
fun UserProfile(userId: String) {
    LaunchedEffect(userId) {          // userId变化时重启
        val user = fetchUser(userId)  // 挂起函数
        updateUI(user)
    }
}
```

**使用场景**：根据参数加载数据、执行一次性异步操作。

### 99. SideEffect 的使用场景是什么?

**每次成功重组后**执行副作用（不依赖键，每次重组都执行）。

```kotlin
@Composable
fun AnalyticsScreen(screenName: String) {
    SideEffect {
        analytics.sendScreenView(screenName)    // 每次重组发送
    }
}
```

**对比**：
- `LaunchedEffect`：键变化时执行
- `SideEffect`：每次重组都执行
- `DisposableEffect`：需要清理的副作用

### 100. DisposableEffect 的作用是什么?

**需要清理的副作用**，离开Composition时自动清理。

```kotlin
@Composable
fun BackHandler(onBack: () -> Unit) {
    val dispatcher = LocalOnBackPressedDispatcherOwner.current.onBackPressedDispatcher

    DisposableEffect(dispatcher) {    // dispatcher变化时重启
        val callback = object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() { onBack() }
        }
        dispatcher.addCallback(callback)

        onDispose {                     // 清理
            callback.remove()
        }
    }
}
```

**使用场景**：注册监听器、绑定服务、资源分配。

---

## 总结建议

这100个问题涵盖了Kotlin从基础语法到Android高级架构的完整知识体系。面试准备建议：

1. **动手实践**：在IDE中编写Demo验证每个知识点
2. **理解原理**：不仅记住答案，更要理解底层实现（如协程CPS转换、Compose重组机制）
3. **结合项目**：准备实际项目中的应用案例
4. **关注最新**：Kotlin 2.0、Compose Multiplatform等新特性

祝您面试顺利！
