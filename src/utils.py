"""Utility functions for the pipeline."""

import re
from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """Normalize text for comparison (remove punctuation, extra spaces)."""
    text = re.sub(r'[^\u4e00-\u9fff\w]', '', text)  # keep Chinese chars + alphanumeric
    return text.strip().lower()


def sanitize_tag(tag: str) -> str:
    """Sanitize a tag value so it doesn't contain spaces (genanki requirement)."""
    # Replace spaces and special chars with underscores
    tag = re.sub(r'[\s/\\:;&@#$%^*()+=<>{}|~]+', '_', tag)
    # Remove leading/trailing underscores
    tag = tag.strip('_')
    # Remove consecutive underscores
    tag = re.sub(r'_+', '_', tag)
    return tag if tag else "untagged"


def similarity(a: str, b: str) -> float:
    """Compute text similarity using difflib."""
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def clean_extracted_text(text: str) -> str:
    """Clean up extracted Markdown text from pymupdf4llm/PyMuPDF."""
    # Remove page numbers and headers (lines with only numbers)
    text = re.sub(r'\n\d+\n', '\n', text)
    # Remove reference links like [text](url)
    text = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', text)
    # Remove bold/italic markers **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    # Remove italic markers *text*
    text = re.sub(r'(?<!\w)\*(?!\*)(.*?)(?<!\*)\*(?!\w)', r'\1', text)
    # Normalize whitespace
    text = re.sub(r' {2,}', ' ', text)
    # Normalize multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove leading/trailing whitespace per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    # Remove bullet markers that got garbled
    text = text.replace('', '•')
    # Remove leading/trailing pipes and special chars
    text = re.sub(r'^[|>\s]+', '', text, flags=re.MULTILINE)
    return text.strip()


def clean_card_content(text: str) -> str:
    """Clean card content (front/back) for better display in Anki."""
    # Remove markdown table rows (lines with mostly pipes)
    text = re.sub(r'^[|\-:\s]+$', '', text, flags=re.MULTILINE)
    # Simplify table pipes in content: "| A | B | C |" -> "A: B, C"
    text = re.sub(r'\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|', r'\1: \2', text)
    # Remove standalone pipes
    text = text.replace('|', '')
    # Protect known HTML tags before escaping other angle brackets
    safe_tags = ['b', '/b', 'br', 'hr', 'i', '/i', 'u', '/u', 'div', '/div', 'span', '/span']
    placeholder = {}
    for i, tag in enumerate(safe_tags):
        key = f'__SAFE_TAG_{i}__'
        placeholder[key] = f'<{tag}>'
        text = text.replace(f'<{tag}>', key)

    # Strip any remaining backslash chars (from markdown escapes)
    text = text.replace('\\', '')
    # Escape ALL remaining < and > (safe tags are protected as placeholders)
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # Restore safe HTML tags from placeholders
    for key, tag in placeholder.items():
        text = text.replace(key, tag)
    text = re.sub(r' {2,}', ' ', text)
    # Clean leading/trailing whitespace per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip()


def extract_markdown(filepath: "Path") -> str:
    """Extract PDF as Markdown using pymupdf4llm."""
    import pymupdf4llm
    md_text = pymupdf4llm.to_markdown(str(filepath))
    return clean_extracted_text(md_text)


def is_toc_content(text: str) -> bool:
    """Detect if content looks like a Table of Contents / directory page."""
    lines = text.strip().split('\n')
    if len(lines) < 3:
        return False

    toc_line_count = 0
    detail_line_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        is_toc = bool(re.match(r'^\d+[、.．\s]', line))
        is_page_num = bool(re.match(r'^[\d\s.\-—|]+$', line))
        has_page_ref = bool(re.search(r'[\.\s]+\d+\s*$', line))
        if is_toc or is_page_num or has_page_ref:
            toc_line_count += 1
        else:
            detail_line_count += 1

    total_meaningful = toc_line_count + detail_line_count
    if total_meaningful == 0:
        return False

    toc_ratio = toc_line_count / total_meaningful
    return toc_ratio > 0.4 or (toc_line_count > 5 and detail_line_count < toc_line_count)


def extract_tech_domain(chapter: str = "", section: str = "", subsection: str = "") -> str:
    """Extract the tech domain for deck hierarchy and tags."""
    text = (chapter + " " + section + " " + subsection).lower()
    # Remove noise words that appear in all interview chapter names
    for noise in ["面试题", "面试", "（", "）", "( )", "⭐", "试题"]:
        text = text.replace(noise, "")

    # Java & JVM
    if any(kw in text for kw in ["jvm", "虚拟机", "类加载", "垃圾回收", "gc", "内存模型",
                                  "运行时数据", "字节码", "堆栈"]):
        return "Java::JVM"

    if any(kw in text for kw in ["java", "面向对象", "多态", "抽象", "接口",
                                  "内部类", "集合", "框架", "泛型", "反射",
                                  "注解", "动态代理", "单例", "设计模块",
                                  "string", "异常", "关键字", "static",
                                  "final", "引用类型"]):
        if any(kw in text for kw in ["集合", "hashmap", "concurrent", "arraylist",
                                      "linkedlist", "map"]):
            return "Java::集合"
        if any(kw in text for kw in ["反射", "动态代理", "注解"]):
            return "Java::高级特性"
        return "Java"

    # Java Concurrency
    if any(kw in text for kw in ["并发", "多线程", "线程", "锁", "synchronized",
                                  "volatile", "thread", "线程池", "aqs",
                                  "reentrantlock", "cas", "copyonwrite",
                                  "countdownlatch", "cyclicbarrier"]):
        return "Java::并发"

    # Network
    if any(kw in text for kw in ["网络", "http", "tcp", "udp", "https", "dns",
                                  "ssl", "tls", "socket", "ip地址", "抓包",
                                  "okhttp", "retrofit", "websocket",
                                  "quic", "cdn"]):
        if any(kw in text for kw in ["tcp", "udp", "三次握手", "四次挥手", "滑动窗口",
                                      "拥塞控制"]):
            return "网络::TCP"
        if any(kw in text for kw in ["http", "https", "ssl"]):
            return "网络::HTTP"
        return "网络"

    # Operating System
    if any(kw in text for kw in ["操作系统", "linux", "内存管理", "进程", "调度",
                                  "文件系统", "io模型", "select", "epoll",
                                  "用户态", "内核态", "虚拟内存"]):
        return "操作系统"

    # Database
    if any(kw in text for kw in ["数据库", "sqlite", "mysql", "sql", "事务",
                                  "索引", "curd"]):
        return "数据库"

    # Data Structures & Algorithms
    if any(kw in text for kw in ["数据结构", "算法", "排序", "二叉树", "链表",
                                  "数组", "栈", "队列", "堆", "图", "哈希",
                                  "字符串", "递归", "动态规划", "复杂度",
                                  "查找", "冒泡", "快排", "归并"]):
        return "算法与数据结构"

    # Android specific
    if any(kw in text for kw in ["android", "安卓"]):
        if any(kw in text for kw in ["binder", "aidl", "ipc", "跨进程", "进程间"]):
            return "Android::IPC"
        if any(kw in text for kw in ["handler", "looper", "message", "消息"]):
            return "Android::Handler"
        if any(kw in text for kw in ["activity", "fragment", "启动模式", "生命周期"]):
            return "Android::组件"
        if any(kw in text for kw in ["view", "布局", "绘制", "事件", "触控",
                                      "recyclerview", "listview", "webview",
                                      "动画", "自定义view"]):
            return "Android::UI"
        if any(kw in text for kw in ["优化", "性能", "内存泄漏", "anr", "卡顿",
                                      "耗电", "启动优化", "布局优化"]):
            return "Android::性能优化"
        if any(kw in text for kw in ["线程", "thread", "asynctask", "handlerthread",
                                      "intentservice", "协程"]):
            return "Android::异步"
        if any(kw in text for kw in ["service", "广播", "broadcast", "contentprovider",
                                      "manifest"]):
            return "Android::组件"
        if any(kw in text for kw in ["window", "dialog", "toast", "notification",
                                      "bitmap", "图片", "缓存", "存储",
                                      "resources"]):
            return "Android::核心机制"
        if any(kw in text for kw in ["编译", "打包", "签名", "混淆", "加固",
                                      "proguard", "multidex", "apk",
                                      "gradle", "构建", "插件化", "组件化",
                                      "热修复", "module"]):
            return "Android::工程实践"
        if any(kw in text for kw in ["四大组件", "启动过程", "aidl", "ams",
                                      "wms", "pms", "systemserver"]):
            return "Android::系统原理"
        if any(kw in text for kw in ["dalvik", "art", "虚拟机", "内存", "回收"]):
            return "Android::底层"
        return "Android"

    # Android engineering
    if any(kw in text for kw in ["工程", "架构", "mvc", "mvp", "mvvm", "clean",
                                  "组件化", "模块化", "插件化", "热修复",
                                  "gradle", "构建"]):
        return "Android::工程实践"

    # Design patterns
    if any(kw in text for kw in ["设计模式", "mvc", "mvp", "mvvm", "单例",
                                  "工厂", "建造者", "代理", "观察者"]):
        return "设计模式"

    # Kotlin
    if any(kw in text for kw in ["kotlin", "协程", "flow", "sealed", "data class",
                                  "委托", "扩展"]):
        return "Kotlin"

    # Non-technical
    if any(kw in text for kw in ["非技术", "hr", "软技能", "职业"]):
        return "综合"

    return "其他"
