# Flutter基础100题（含详细答案）

## 一、Dart语言基础（1-15题）

### 1. Dart是强类型语言还是弱类型语言？`var`、`dynamic`、`Object`的区别？
**答案**：Dart是**强类型语言**（编译时类型检查）。
| 关键字 | 类型检查 | 特点 |
|--------|----------|------|
| `var` | 编译时推断 | 推断后类型固定，不可改变 |
| `dynamic` | 运行时 | 绕过静态检查，可调用任意方法（编译时不报错） |
| `Object` | 编译时 | 所有类型的基类，只能调用Object的方法 |

### 2. Dart中的`final`和`const`的区别？
**答案**：
| 特性 | `final` | `const` |
|------|---------|---------|
| 确定时机 | 运行时 | 编译时 |
| 赋值次数 | 只能一次 | 只能一次（隐式final） |
| 对象内容 | 引用不可变，内容可变 | 对象及内容都不可变（深不可变） |
| 内存 | 每次创建新实例 | 相同值共享实例 |
| 使用场景 | 运行时确定的值 | 固定常量、Widget |

### 3. Dart中的空安全（Null Safety）是什么？`?`、`!`、`late`的用法？
**答案**：Dart 2.12+引入，默认变量不可为空。
- `?` 标记可空类型（`String?`）
- `!` 非空断言（运行时检查，为null则抛出异常）
- `?.` 空感知访问（null则返回null）
- `??` 空值合并
- `late` 延迟初始化（首次访问前必须赋值）
- `late final` 延迟且只能赋值一次

### 4. Dart中的`??`、`??=`、`?.`、`?[]`运算符？
**答案**：
- `??` 空值合并：`a ?? b`，a为null则取b
- `??=` 为空则赋值：`c ??= 'value'`，c为null时赋值
- `?.` 空感知属性访问：`obj?.property`，obj为null则返回null
- `?[]` 空感知索引访问：`map?['key']`，map为null则返回null
- `?..` 空感知级联调用：`obj?..method1()..method2()`

### 5. Dart中的级联运算符`..`和展开运算符`...`？
**答案**：
- `..` 级联运算符：对同一对象连续操作
- `...` 展开运算符：将集合元素展开到另一个集合
- `...?` 空感知展开：集合为null时不展开

### 6. Dart中的命名参数和位置参数？`required`关键字？
**答案**：
- 位置参数：按位置传递，可选参数用`[]`包裹
- 命名参数：用`{}`包裹，调用时指定名称
- `required`：标记命名参数为必传（空安全下）

### 7. Dart中的`Future`和`Stream`的区别？
**答案**：
| 特性 | Future | Stream |
|------|--------|--------|
| 结果数量 | 单一结果 | 0个或多个事件 |
| 使用场景 | 一次性异步操作 | 持续数据流 |
| 监听方式 | await / then | listen / await for |
| 类比 | Promise | Observable |

### 8. `async`/`await`和`then`的区别？
**答案**：
- `async`/`await`：语法糖，代码更易读（类似同步），只能在`async`函数中使用
- `then`：链式回调，适合简单操作
- `await`不会阻塞UI线程（单线程事件循环）

### 9. Dart中的`Stream`单订阅流和广播流的区别？
**答案**：
- **单订阅流**（默认）：只能有一个监听者，消费后关闭，适合文件读取等
- **广播流**：可有多个监听者，不会自动关闭，适合UI事件、WebSocket等
- 转换：`stream.asBroadcastStream()`

### 10. Dart中的扩展方法（Extension Methods）？
**答案**：为现有类型添加方法，不修改原类。
```dart
extension StringExtension on String {
  String reverse() => split('').reversed.join('');
  bool get isPalindrome => this == reverse();
}
```

### 11. Dart中的`mixin`是什么？与`extends`和`implements`的区别？
**答案**：
| 特性 | extends | implements | mixin |
|------|---------|------------|-------|
| 数量 | 单继承 | 多实现 | 多混入 |
| 方法 | 获得父类实现 | 必须重写所有方法 | 获得mixin实现 |
| 关系 | is-a | can-do | with |

### 12. Dart中的工厂构造函数（factory constructor）？
**答案**：不总是创建新实例，可返回缓存实例或子类实例。
```dart
factory Singleton() => _instance;
factory Animal(String type) {
  if (type == 'dog') return Dog();
  return Animal._internal(type);
}
```

### 13. Dart中的`typedef`和函数类型？
**答案**：定义函数类型别名。Dart 2.13+支持非函数类型的typedef（类型别名）。
```dart
typedef IntCallback = void Function(int value);
typedef JsonMap = Map<String, dynamic>;
```

### 14. Dart中的`assert`断言？生产环境是否生效？
**答案**：
- 开发时检查条件，不满足则抛出AssertionError
- **只在开发模式（debug）生效**
- Profile和Release模式自动忽略
- 不要用于生产环境的输入验证！

### 15. Dart中的`enum`增强（Dart 2.17+）？
**答案**：支持字段、方法、构造函数。
```dart
enum Color {
  red('#FF0000'),
  green('#00FF00'),
  blue('#0000FF');
  final String hex;
  const Color(this.hex);
}
```

---

## 二、Flutter Widget基础（16-30题）

### 16. Flutter中Widget、Element、RenderObject的关系？
**答案**：
- **Widget**：配置描述，不可变，轻量，可复用
- **Element**：Widget的实例，可变，管理生命周期（mount、update、unmount）
- **RenderObject**：负责布局和绘制，重量级，直接对应屏幕像素

### 17. StatelessWidget和StatefulWidget的区别？
**答案**：
| 特性 | StatelessWidget | StatefulWidget |
|------|-----------------|----------------|
| 状态 | 无内部状态 | 有内部状态（State对象） |
| build | 只依赖传入参数 | 依赖参数 + State |
| 更新 | 父级重建时重建 | 调用setState()重建 |
| 场景 | 静态展示 | 交互、动画、数据变化 |

### 18. StatefulWidget的`createState()`为什么可以调用多次？
**答案**：同一个Widget配置可在不同位置（不同Element）多次实例化。每次插入到树中时都会创建新的State实例。

### 19. `setState()`的作用和原理？
**答案**：
- 作用：通知框架State对象内部状态变化
- 原理：将当前Element标记为dirty，加入调度队列，下一帧重建时调用build()
- **不会立即重建**，而是异步调度

### 20. Widget的`key`有什么作用？`LocalKey`和`GlobalKey`的区别？
**答案**：
- `key`帮助框架识别Widget，控制更新行为
- `LocalKey`：在同一父级唯一（ValueKey、ObjectKey、UniqueKey）
- `GlobalKey`：全局唯一，可跨树访问State、Widget、Context、RenderObject

### 21. `GlobalKey`的使用场景和注意事项？
**答案**：
- **场景**：跨树访问State、Form验证、获取RenderObject尺寸
- **注意事项**：
  - 创建成本高（哈希表查找）
  - 滥用影响性能
  - 避免在build方法中创建
  - 可能导致内存泄漏

### 22. Flutter中的`BuildContext`是什么？
**答案**：Widget在树中的位置句柄，提供：
- `findAncestorWidgetOfExactType`：查找祖先Widget
- `dependOnInheritedWidgetOfExactType`：获取InheritedWidget
- `findRenderObject`：获取RenderObject
- **注意**：不能跨异步间隙使用，需检查`context.mounted`

### 23. `Builder`和`LayoutBuilder`的区别？
**答案**：
- `Builder`：提供新的BuildContext，解决context层级问题
- `LayoutBuilder`：提供父级约束信息（BoxConstraints），用于响应式布局

### 24. `MediaQuery`的作用？常用属性？
**答案**：获取设备信息和屏幕参数：
- `size`：屏幕尺寸
- `padding`：安全区（刘海、底部横条）
- `viewInsets`：键盘等遮挡区域
- `orientation`：屏幕方向
- `platformBrightness`：亮度（light/dark）
- `devicePixelRatio`：设备像素比
- `textScaleFactor`：用户字体缩放

### 25. `SafeArea`的作用？与`Padding`的区别？
**答案**：
- `SafeArea`：自动避开系统UI（刘海、底部横条、状态栏），动态计算
- `Padding`：手动设置固定内边距

### 26. `GestureDetector`和`InkWell`的区别？
**答案**：
- `GestureDetector`：纯手势检测，无视觉反馈，更灵活
- `InkWell`：Material风格，有水波纹/高亮效果，必须在Material内

### 27. Flutter中的`Hero`动画原理？
**答案**：
1. 导航时框架查找匹配tag的Hero Widget
2. 创建HeroFlight，在Overlay层绘制过渡动画
3. 自动计算起始和结束位置、尺寸、形状
4. 使用Tween动画平滑过渡

### 28. `WillPopScope`的作用？
**答案**：拦截返回键（Android物理返回/导航返回），可阻止或自定义返回行为。Flutter 3.12+使用`PopScope`替代。

### 29. `Visibility`、`Offstage`、`Opacity`控制显示的区别？
**答案**：
| Widget | 构建 | 布局 | 绘制 | 场景 |
|--------|------|------|------|------|
| Visibility(visible:false) | 否 | 否 | 否 | 完全隐藏 |
| Offstage | 是 | 是 | 否 | 保留布局空间 |
| Opacity(opacity:0) | 是 | 是 | 是 | 透明但可交互 |

### 30. `IgnorePointer`和`AbsorbPointer`的区别？
**答案**：
- `IgnorePointer`：不响应事件，但事件可穿过到达下层
- `AbsorbPointer`：响应并消费事件，阻止传递到下层

---

## 三、Flutter布局（31-45题）

### 31. Flutter的布局约束（Constraints）模型？
**答案**：
1. 父Widget向子Widget传递约束（最小/最大宽高）
2. 子Widget根据约束决定自身尺寸
3. 父Widget决定子Widget位置

### 32. `Row`和`Column`的区别？`mainAxisAlignment`和`crossAxisAlignment`？
**答案**：
- `Row`：水平排列，主轴水平，交叉轴垂直
- `Column`：垂直排列，主轴垂直，交叉轴水平
- `mainAxisAlignment`：主轴对齐（start/end/center/spaceBetween/spaceAround/spaceEvenly）
- `crossAxisAlignment`：交叉轴对齐（start/end/center/stretch/baseline）

### 33. `Expanded`和`Flexible`的区别？
**答案**：
- `Expanded` = `Flexible(flex: n, fit: FlexFit.tight)`，强制填满剩余空间
- `Flexible`：允许子Widget按自身大小，`FlexFit.loose`

### 34. `Stack`和`Positioned`的用法？
**答案**：
- `Stack`：允许子Widget重叠
- `Positioned`：绝对定位（top/bottom/left/right），必须是Stack的子
- `Positioned.fill`：填满整个Stack

### 35. `Wrap`和`Flow`的区别？
**答案**：
- `Wrap`：自动换行的Row/Column，使用简单
- `Flow`：手动控制子Widget位置，性能更好，使用复杂，需自定义FlowDelegate

### 36. `ListView`和`SingleChildScrollView`的区别？
**答案**：
- `ListView`：懒加载，只构建可见项，适合长列表
- `SingleChildScrollView`：一次性构建所有子Widget，适合短内容

### 37. `ListView.builder`和`ListView.separated`的区别？
**答案**：
- `.builder`：按需构建，适合大数据量
- `.separated`：在item间添加分隔线，同样懒加载

### 38. `GridView`的常用构造方式？
**答案**：
- `GridView.count`：固定列数
- `GridView.extent`：最大宽度自适应列数
- `GridView.builder`：懒加载
- `SliverGridDelegateWithFixedCrossAxisCount` / `WithMaxCrossAxisExtent`

### 39. `CustomScrollView`和`Sliver`的作用？
**答案**：
- `CustomScrollView`：使用Sliver协议，可组合多种滚动效果
- `Sliver`：懒加载的滚动区域单位
- 常用Sliver：SliverAppBar、SliverList、SliverGrid、SliverToBoxAdapter

### 40. `SliverAppBar`的`floating`、`pinned`、`snap`属性？
**答案**：
- `floating`：向下滚动时立即显示
- `pinned`：固定顶部，不随滚动消失
- `snap`：与floating配合，滚动停止时自动展开/收缩

### 41. `LayoutBuilder`和`OrientationBuilder`的区别？
**答案**：
- `LayoutBuilder`：获取父级约束（BoxConstraints），更灵活
- `OrientationBuilder`：获取屏幕方向（portrait/landscape）

### 42. `AspectRatio`和`FittedBox`的作用？
**答案**：
- `AspectRatio`：强制子Widget保持宽高比
- `FittedBox`：根据fit模式缩放子Widget（contain/cover/fill/fitWidth/fitHeight/none/scaleDown）

### 43. `FractionallySizedBox`和`FractionalTranslation`的区别？
**答案**：
- `FractionallySizedBox`：按父级百分比设置尺寸
- `FractionalTranslation`：按百分比偏移子Widget位置

### 44. `IntrinsicWidth`和`IntrinsicHeight`的作用？
**答案**：根据子Widget的内在尺寸调整自身。性能开销大（需要额外布局遍历），应尽量避免使用。

### 45. `OverflowBox`和`SizedOverflowBox`的区别？
**答案**：
- `OverflowBox`：允许子Widget超出自身边界
- `SizedOverflowBox`：先按指定尺寸布局，再允许子Widget溢出

---

## 四、Flutter状态管理（46-60题）

### 46. Flutter中状态管理的分类？Ephemeral State和App State？
**答案**：
- **Ephemeral State**（短暂状态）：仅单个Widget使用，用`setState`
- **App State**（应用状态）：跨Widget共享，需Provider/Riverpod/Bloc/GetX等

### 47. `InheritedWidget`的作用和原理？
**答案**：
- 在Widget树中高效共享数据
- 子Widget通过BuildContext注册依赖
- 数据变化时，框架自动重建依赖的子Widget
- 非依赖的子Widget不重建

### 48. `Provider`的核心概念？`ChangeNotifierProvider`、`Consumer`、`Selector`？
**答案**：
- `ChangeNotifierProvider`：提供可通知变化的数据模型
- `Consumer`：监听并重建整个模型
- `Selector`：选择性监听部分数据变化，减少不必要的重建
- `context.read()`：不监听，只获取（事件回调中使用）
- `context.watch()`：监听变化并重建（build中使用）

### 49. `Riverpod`相比`Provider`的改进？
**答案**：
1. 编译安全（不依赖BuildContext）
2. 支持自动销毁
3. 更灵活的Provider组合
4. 更好的测试支持
5. 不依赖Flutter，可用于纯Dart

### 50. `Bloc`模式的核心思想？`Event`、`State`、`Bloc`的关系？
**答案**：
- **核心思想**：将业务逻辑与UI分离，单向数据流
- **Event**：用户操作或系统事件
- **Bloc**：处理Event，输出新State
- **State**：UI状态（不可变）
- **数据流**：Event -> Bloc -> State -> UI

### 51. `GetX`状态管理的特点？
**答案**：
- **优点**：简单、功能全面（状态管理+路由+依赖注入）、代码量少
- **缺点**：耦合度高、上下文隐式传递、不适合大型项目、测试困难
- **适用**：小型项目、快速原型、个人项目

### 52. `ValueNotifier`和`ChangeNotifier`的区别？
**答案**：
- `ValueNotifier`：管理单个值，自动通知，更轻量
- `ChangeNotifier`：手动管理多个值，手动调用`notifyListeners()`，更灵活

### 53. `setState`的性能问题？如何优化？
**答案**：
- **问题**：重建整个Widget树开销大
- **优化**：
  1. 将状态下沉到最小范围
  2. 使用`const`构造器
  3. 使用`RepaintBoundary`隔离重绘
  4. 避免在build中创建对象

### 54. `StatefulBuilder`和`ValueListenableBuilder`的作用？
**答案**：
- `StatefulBuilder`：不需要完整State类时快速使用setState
- `ValueListenableBuilder`：监听ValueNotifier，局部重建，性能更好

### 55. `AnimatedBuilder`和`TweenAnimationBuilder`的区别？
**答案**：
- `AnimatedBuilder`：监听Animation对象，需手动管理Controller
- `TweenAnimationBuilder`：内置Tween和AnimationController，使用更简单

### 56. `FutureBuilder`和`StreamBuilder`的区别？
**答案**：
- `FutureBuilder`：监听Future（一次性结果）
- `StreamBuilder`：监听Stream（持续事件流），有ConnectionState管理

### 57. `Bloc`中的`Equatable`作用？
**答案**：
- 简化相等性判断（不用手动重写==和hashCode）
- Bloc通过比较前后State是否相等决定是否重建
- 避免相同State触发不必要的UI更新

### 58. Flutter中的依赖注入（DI）方案？
**答案**：
- `Provider`/`Riverpod`：Widget树注入
- `get_it`：服务定位器
- `injectable`：代码生成
- `Bloc`的`RepositoryProvider`

### 59. 如何选择状态管理方案？
**答案**：
| 项目规模 | 推荐方案 |
|----------|----------|
| 小型/个人 | setState / GetX |
| 中型 | Provider / Riverpod |
| 大型/团队 | Bloc / Riverpod + Freezed |

### 60. `context.read()`和`context.watch()`的区别？
**答案**：
- `watch`：建立依赖关系，数据变化时重建Widget（build中使用）
- `read`：一次性获取，不建立依赖，不重建（事件回调中使用）

---

## 五、Flutter导航与路由（61-70题）

### 61. Flutter中的命名路由（Named Routes）？
**答案**：通过字符串名称定义路由，在`MaterialApp`的`routes`或`onGenerateRoute`中配置。

### 62. `Navigator 2.0`（声明式路由）相比`Navigator 1.0`的改进？
**答案**：
- 支持URL同步（深链接）
- 返回按钮处理
- 多导航栈
- 通过`Router`、`RouteInformationParser`、`RouterDelegate`实现

### 63. `GoRouter`的作用？
**答案**：声明式路由库，简化Navigator 2.0使用，支持路径参数、查询参数、重定向、嵌套路由。

### 64. `ModalRoute`、`PageRoute`、`MaterialPageRoute`的关系？
**答案**：
- `ModalRoute`：模态路由基类
- `PageRoute`：全屏替换页面，支持平台过渡动画
- `MaterialPageRoute`：Material风格（Android底部滑入）
- `CupertinoPageRoute`：iOS风格（右侧滑入）

### 65. 如何传递参数给新页面？
**答案**：
- 构造函数传参（推荐）
- 命名路由的`arguments`
- `ModalRoute.of(context)?.settings.arguments`

### 66. 如何监听路由变化？
**答案**：
- `RouteObserver` + `NavigatorObserver`
- `WidgetsBindingObserver`监听App生命周期

### 67. `WillPopScope`和`PopScope`（Flutter 3.12+）的区别？
**答案**：
- `WillPopScope`：异步判断，已废弃
- `PopScope`：API更统一，支持`canPop`直接控制是否允许返回

### 68. 如何实现底部导航栏（BottomNavigationBar）切换保持页面状态？
**答案**：
- `IndexedStack`：所有页面同时存在，只显示当前
- `PageStorageKey` + `AutomaticKeepAliveClientMixin`

### 69. `CupertinoPageRoute`和`MaterialPageRoute`的区别？
**答案**：
- `CupertinoPageRoute`：iOS风格，侧滑返回
- `MaterialPageRoute`：Android风格，从底部滑入

### 70. 深链接（Deep Linking）在Flutter中的实现？
**答案**：配置AndroidManifest和Info.plist的URL Scheme，使用`go_router`或`uni_links`插件处理URL解析和导航。

---

## 六、Flutter网络与数据（71-80题）

### 71. Flutter中常用的HTTP请求库？`http`和`dio`的区别？
**答案**：
- `http`：Dart官方，简单轻量
- `dio`：功能强大，支持拦截器、全局配置、FormData、文件下载、请求取消

### 72. 如何处理JSON序列化和反序列化？
**答案**：
- 手动解析（`jsonDecode` + 手动映射）
- `json_serializable`：代码生成（推荐）
- `freezed`：不可变数据类 + 序列化

### 73. `json_serializable`的使用步骤？
**答案**：
1. 添加依赖
2. 定义数据类 + `@JsonSerializable()`注解
3. 运行`build_runner`生成`.g.dart`文件
4. 调用`_$ClassNameFromJson` / `ToJson`

### 74. Flutter中的本地存储方案？
**答案**：
| 方案 | 特点 | 场景 |
|------|------|------|
| shared_preferences | 键值对，简单 | 简单数据 |
| hive | 轻量NoSQL，性能高 | 结构化数据 |
| sqflite | SQLite，关系型 | 复杂查询 |
| drift | 类型安全的SQLite | 类型安全需求 |

### 75. `FutureBuilder`处理异步数据的最佳实践？
**答案**：
- 缓存Future（避免重建时重新请求）
- 处理错误状态
- 显示加载指示器
- 使用`ConnectionState`判断状态

### 76. Flutter中的图片加载和缓存？`Image.network`的原理？
**答案**：`Image.network`使用`NetworkImage`，自动缓存到内存和磁盘。`CachedNetworkImage`插件提供更强大的缓存控制。

### 77. 如何处理WebSocket实时通信？
**答案**：使用`web_socket_channel`插件，创建`WebSocketChannel`，监听`stream`接收消息，通过`sink.add`发送。

### 78. Flutter中的文件操作？
**答案**：使用`path_provider`获取目录路径（临时、文档、缓存），使用`dart:io`的`File`类读写。

### 79. GraphQL在Flutter中的使用？
**答案**：`graphql_flutter`插件，配置`GraphQLClient`，使用`Query`/`Mutation` Widget或`useQuery`/`useMutation` Hook。

### 80. Flutter中的数据分页加载实现？
**答案**：`ListView` + `ScrollController`监听滚动到底部触发加载，或使用`infinite_scroll_pagination`插件。

---

## 七、Flutter动画（81-90题）

### 81. Flutter动画的分类？Tween动画和物理动画？
**答案**：
- **Tween动画**（补间动画）：线性插值
- **物理动画**：基于弹簧、摩擦力模拟
- **隐式动画**：AnimatedContainer等，属性变化自动动画
- **显式动画**：需手动控制AnimationController

### 82. `AnimationController`的作用？常用属性和方法？
**答案**：控制动画状态。
- 属性：`duration`、`value`、`status`
- 方法：`forward()`、`reverse()`、`repeat()`、`dispose()`

### 83. `Tween`的作用？
**答案**：定义动画的起止值，将Animation的0~1映射到目标范围。常用：`Tween<double>`、`ColorTween`、`SizeTween`、`BorderRadiusTween`。

### 84. 隐式动画Widget有哪些？
**答案**：`AnimatedContainer`（尺寸/颜色/圆角）、`AnimatedOpacity`（透明度）、`AnimatedPositioned`（位置）、`AnimatedDefaultTextStyle`。

### 85. 显式动画Widget有哪些？
**答案**：`RotationTransition`（旋转）、`FadeTransition`（淡入淡出）、`ScaleTransition`（缩放）、`SlideTransition`（滑动）。

### 86. `Hero`动画的实现步骤？
**答案**：
1. 两个页面的共享元素包裹`Hero`，设置相同`tag`
2. 导航时自动过渡
3. 可自定义`HeroFlightShuttleBuilder`

### 87. `AnimatedBuilder`和`AnimatedWidget`的区别？
**答案**：
- `AnimatedWidget`：将动画逻辑封装在子类中
- `AnimatedBuilder`：通过builder回调将动画与UI分离，避免重建不必要部分

### 88. Flutter中的交织动画（Staggered Animation）？
**答案**：多个动画按时间错开执行。使用一个AnimationController，多个IntervalTween控制各动画的时间区间。

### 89. `CurvedAnimation`的作用？常用曲线？
**答案**：为动画添加非线性曲线。常用：`Curves.easeIn`、`Curves.easeOut`、`Curves.bounceIn`、`Curves.elasticIn`。

### 90. Lottie动画在Flutter中的使用？
**答案**：`lottie`插件加载JSON格式的Lottie动画文件，支持网络/本地加载，可控制播放、暂停、循环。

---

## 八、Flutter性能优化与测试（91-100题）

### 91. Flutter性能优化的核心原则？
**答案**：
- 减少重建（setState范围最小化）
- 减少绘制（RepaintBoundary）
- 减少布局（避免IntrinsicHeight/Width）
- 延迟加载（ListView.builder）

### 92. `RepaintBoundary`的作用？
**答案**：创建新的绘制边界，隔离子树的重绘，避免不必要的重绘传播。适用于动画区域或频繁变化的局部。

### 93. `const`构造器对性能的影响？
**答案**：`const`对象在编译期创建，运行时复用同一实例，减少内存分配和GC压力。应尽可能使用`const`。

### 94. Flutter中的渲染流水线？
**答案**：Build（构建Widget树）-> Layout（计算布局约束和尺寸）-> Paint（绘制到图层）-> Composite（合成图层）。性能问题通常出现在Build和Layout阶段。

### 95. 如何使用DevTools分析性能？
**答案**：
- Performance视图：查看帧率
- Timeline：查看各阶段耗时
- Widget Inspector：查看树结构
- Memory视图：分析内存

### 96. Flutter中的单元测试、Widget测试、集成测试？
**答案**：
- **单元测试**：测试纯Dart逻辑，`test`包
- **Widget测试**：测试UI交互，`flutter_test`包
- **集成测试**：端到端测试，`integration_test`包

### 97. `Key`在测试中的作用？
**答案**：通过`Key`定位Widget进行测试。`find.byKey(Key('submit_button'))`，点击、读取文本、验证状态。

### 98. Flutter中的内存泄漏常见原因？
**答案**：
- AnimationController未dispose
- StreamSubscription未cancel
- Timer未cancel
- GlobalKey滥用
- 图片缓存过大

### 99. Flutter包体积优化方案？
**答案**：
- 代码混淆（`--obfuscate`）
- 资源压缩
- 移除未使用资源
- 使用`flutter_gen`管理资源
- 按需加载（deferred components）

### 100. Flutter Web、Desktop、Embedded的区别和注意事项？
**答案**：
- **Web**：单线程、SEO限制、CanvasKit vs HTML渲染器
- **Desktop**：窗口管理、菜单栏、键盘快捷键
- **Embedded**：自定义嵌入器、资源受限环境

---

> **总结**：Flutter是一个强大的跨平台UI框架，掌握Dart语言基础、Widget体系、布局约束、状态管理和性能优化是成为Flutter开发者的核心。建议结合官方文档和实际项目经验来巩固这些知识。
